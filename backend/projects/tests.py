from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Project, ProjectAccess, ProjectAuditEvent


class ProjectApiTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.manager = users.create_user(username="manager")
        self.other_user = users.create_user(username="other")
        self.manager.user_permissions.add(
            Permission.objects.get(content_type__app_label="projects", codename="add_project")
        )
        self.url = reverse("project-list")
        self.project = {
            "title": "Road rehabilitation",
            "department": "Public Works",
            "planned_start": "2026-11-10",
            "planned_end": "2027-01-15",
            "approved_budget": "2500000.00",
            "currency": "NGN",
        }

    def test_manager_creates_and_lists_only_owned_projects(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            self.url, {**self.project, "owner": self.other_user.pk}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.owner, self.manager)
        self.assertEqual(project.status, Project.Status.PROPOSED)
        Project.objects.create(**{**self.project, "title": "Other project"}, owner=self.other_user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(project.pk))
        self.assertEqual(self.client.get(self.url, {"search": "Public Works"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"search": "Other"}).data["count"], 0)

    def test_create_requires_permission(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.other_user)
        response = self.client.post(self.url, self.project, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Project.objects.exists())

    def test_owner_edits_project_and_history_records_changes(self):
        self.manager.user_permissions.add(
            Permission.objects.get(content_type__app_label="projects", codename="change_project")
        )
        self.client.force_login(self.manager)
        created = self.client.post(self.url, self.project, format="json")
        self.assertEqual(created.status_code, 201)
        project_id = created.data["id"]
        detail_url = reverse("project-detail", args=[project_id])
        audit_url = reverse("project-audit", args=[project_id])

        self.assertEqual(self.client.get(detail_url).status_code, 200)
        invalid = self.client.patch(detail_url, {"planned_end": "2026-11-01"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(ProjectAuditEvent.objects.filter(project_id=project_id).count(), 1)

        self.assertEqual(
            self.client.patch(detail_url, {"approved_budget": "3000000.00"}, format="json").status_code,
            400,
        )
        updated = self.client.patch(detail_url, {
            "approved_budget": "3000000.00", "budget_revision_reason": "Approved scope change",
        }, format="json")
        self.assertEqual(updated.status_code, 200)
        history = self.client.get(audit_url).data["results"]
        self.assertEqual([event["action"] for event in history], ["updated", "created"])
        self.assertEqual(history[0]["actor"], self.manager.pk)
        self.assertEqual(history[0]["changes"]["budget_revision_reason"], "Approved scope change")
        self.assertEqual(
            history[0]["changes"]["approved_budget"],
            {"before": "2500000.00", "after": "3000000.00"},
        )

    def test_assigned_user_has_scoped_read_only_access(self):
        project = Project.objects.create(**self.project, owner=self.manager)
        ProjectAccess.objects.create(project=project, user=self.other_user)
        detail_url = reverse("project-detail", args=[project.pk])
        audit_url = reverse("project-audit", args=[project.pk])
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(detail_url).status_code, 404)

        self.other_user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="projects",
                codename__in=["view_project", "change_project"],
            )
        )
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.assertEqual(self.client.patch(detail_url, {"title": "New title"}, format="json").status_code, 403)
        self.assertEqual(self.client.get(audit_url).status_code, 403)
        self.assertEqual(self.client.get(self.url, {"department": "Public Works", "status": "proposed"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"status": "completed"}).data["count"], 0)

        self.other_user.user_permissions.add(
            Permission.objects.get(content_type__app_label="projects", codename="view_projectauditevent")
        )
        self.assertEqual(self.client.get(audit_url).status_code, 200)

    def test_invalid_projects_are_rejected(self):
        self.client.force_login(self.manager)
        for field, value in (
            ("title", ""),
            ("planned_end", "2026-11-09"),
            ("approved_budget", "-1.00"),
            ("currency", "ng1"),
        ):
            with self.subTest(field=field):
                response = self.client.post(self.url, {**self.project, field: value}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertFalse(Project.objects.exists())
