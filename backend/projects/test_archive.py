from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Project, ProjectAccess


class ProjectArchiveTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="RoadManager")
        self.owner.user_permissions.add(Permission.objects.get(
            content_type__app_label="projects", codename="change_project"
        ))
        self.project = Project.objects.create(
            title="Road repairs", department="Public Works", owner=self.owner,
            planned_start="2026-11-10", planned_end="2026-11-30",
            status="completed", approved_budget="1000.00", currency="NGN",
        )
        self.list_url = reverse("project-list")
        self.archive_url = reverse("project-archive", args=[self.project.pk])
        self.detail_url = reverse("project-detail", args=[self.project.pk])
        self.client.force_login(self.owner)

    def test_archive_preserves_history_and_restore_returns_to_register(self):
        self.assertEqual(self.client.get(self.list_url).data["count"], 1)
        response = self.client.post(self.archive_url, {})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNotNone(response.data["archived_at"])
        self.assertEqual(self.client.post(self.archive_url, {}).data["archived_at"], response.data["archived_at"])
        self.assertEqual(self.client.get(self.list_url).data["count"], 0)
        self.assertEqual(self.client.get(self.list_url, {"archived": "true"}).data["count"], 1)
        self.assertEqual(self.client.get(reverse("dashboard")).data["project_count"], 0)
        self.assertEqual(self.client.get(reverse("report")).data["count"], 1)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        self.assertEqual(self.client.patch(self.detail_url, {"title": "Edited"}).status_code, 400)
        self.owner.user_permissions.add(Permission.objects.get(
            content_type__app_label="projects", codename="add_progressupdate"
        ))
        progress = reverse("progress-update-list", args=[self.project.pk])
        payload = {"reporting_date": "2026-11-20", "percent_complete": 100, "summary": "Finished"}
        self.assertEqual(self.client.post(progress, payload).status_code, 400)
        self.assertEqual(self.client.post(self.archive_url, {"archived": False}, format="json").status_code, 200)
        self.assertEqual(self.client.get(self.list_url).data["count"], 1)
        audit = self.client.get(reverse("project-audit", args=[self.project.pk])).data["results"]
        self.assertEqual([event["action"] for event in audit], ["restored", "archived"])

    def test_register_filters_and_archive_permissions(self):
        match = {"project_id": str(self.project.pk), "owner": "roadman", "start": "2026-11-25", "end": "2026-12-01"}
        self.assertEqual(self.client.get(self.list_url, match).data["count"], 1)
        self.assertEqual(self.client.get(self.list_url, {"start": "2026-12-01"}).data["count"], 0)
        self.assertEqual(self.client.get(self.list_url, {"start": "2026-12-01", "end": "2026-11-01"}).status_code, 400)
        self.assertEqual(self.client.get(self.list_url, {"project_id": "invalid"}).status_code, 400)
        self.project.status = "active"
        self.project.save(update_fields=["status"])
        self.assertEqual(self.client.post(self.archive_url, {}).status_code, 400)

        viewer = get_user_model().objects.create_user(username="viewer")
        viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="projects", codename__in=["view_project", "change_project"]
        ))
        ProjectAccess.objects.create(project=self.project, user=viewer)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        self.assertEqual(self.client.post(self.archive_url, {}).status_code, 403)
