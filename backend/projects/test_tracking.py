from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Project, ProjectAccess


class TrackingApiTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="owner")
        self.officer = users.create_user(username="officer")
        self.officer.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="projects",
                codename__in=["view_project", "change_workitem", "add_progressupdate"],
            )
        )
        self.owner.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="projects",
                codename__in=["add_workitem", "change_workitem"],
            )
        )
        project_fields = {
            "owner": self.owner,
            "department": "Public Works",
            "planned_start": "2026-11-10",
            "planned_end": "2027-01-15",
            "approved_budget": "1000.00",
            "currency": "NGN",
        }
        self.project = Project.objects.create(title="Road works", **project_fields)
        self.other = Project.objects.create(title="Other works", **project_fields)
        ProjectAccess.objects.create(project=self.project, user=self.officer)
        self.items_url = reverse("work-item-list", args=[self.project.pk])
        self.updates_url = reverse("progress-update-list", args=[self.project.pk])
        self.item = {
            "kind": "task",
            "title": "Inspect the site",
            "planned_start": "2026-11-12",
            "planned_end": "2026-11-15",
        }

    def test_dependencies_must_be_acyclic_and_within_project(self):
        self.client.force_login(self.owner)
        first = self.client.post(self.items_url, self.item, format="json")
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            self.items_url, {**self.item, "kind": "milestone", "predecessor": first.data["id"]},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        first_url = reverse("work-item-detail", args=[self.project.pk, first.data["id"]])
        response = self.client.patch(first_url, {"predecessor": second.data["id"]}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("work-item-list", args=[self.other.pk]),
            {**self.item, "predecessor": first.data["id"]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(self.items_url, {"kind": "milestone"}).data["count"], 1)

    def test_assigned_officer_can_report_progress_but_not_change_the_plan(self):
        self.client.force_login(self.owner)
        created = self.client.post(self.items_url, {**self.item, "assignee": self.officer.pk}, format="json")
        self.assertEqual(created.status_code, 201)
        item_url = reverse("work-item-detail", args=[self.project.pk, created.data["id"]])

        self.client.force_login(self.officer)
        self.assertEqual(self.client.patch(item_url, {"title": "Changed"}, format="json").status_code, 403)
        response = self.client.patch(item_url, {"percent_complete": 100}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")
        update = {
            "reporting_date": "2026-11-14",
            "percent_complete": 40,
            "summary": "Site inspected.",
            "author": self.owner.pk,
        }
        invalid = self.client.post(self.updates_url, {**update, "percent_complete": 101}, format="json")
        self.assertEqual(invalid.status_code, 400)
        response = self.client.post(self.updates_url, update, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["author"], self.officer.pk)
        outside_url = reverse("progress-update-list", args=[self.other.pk])
        self.assertEqual(self.client.post(outside_url, update, format="json").status_code, 404)
