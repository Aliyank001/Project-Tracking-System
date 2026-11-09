from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Notification, ProgressUpdate, Project, ProjectAccess, WorkItem


class NotificationTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.manager = users.create_superuser(username="manager")
        self.officer = users.create_user(username="officer")
        self.officer.user_permissions.add(Permission.objects.get(
            content_type__app_label="projects", codename="view_project"
        ))
        self.today = timezone.localdate()
        self.project = Project.objects.create(
            title="Road repairs", department="Public Works", owner=self.manager,
            planned_start=self.today, planned_end=self.today + timedelta(days=30),
            status="active", approved_budget="1000.00", currency="NGN",
        )
        self.access = ProjectAccess.objects.create(project=self.project, user=self.officer)

    def test_assignment_review_and_recipient_scoping(self):
        self.client.force_login(self.manager)
        created = self.client.post(reverse("work-item-list", args=[self.project.pk]), {
            "kind": "task", "title": "Inspect road", "assignee": self.officer.pk,
            "planned_start": self.today, "planned_end": self.today,
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        update = ProgressUpdate.objects.create(
            project=self.project, author=self.officer, reporting_date=self.today,
            summary="Inspection finished", percent_complete=100,
        )
        result = self.client.post(
            reverse("progress-review", args=[self.project.pk, update.pk]), {"decision": "approved"},
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(self.client.get(reverse("notifications")).data["count"], 0)
        notice = Notification.objects.get(kind="assignment")
        read_url = reverse("notification-read", args=[notice.pk])
        self.assertEqual(self.client.post(read_url).status_code, 404)

        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(reverse("notification-count")).data["unread_count"], 2)
        self.assertEqual(self.client.post(read_url).status_code, 204)
        notice.refresh_from_db()
        read_at = notice.read_at
        self.assertIsNotNone(read_at)
        self.assertEqual(self.client.post(read_url).status_code, 204)
        notice.refresh_from_db()
        self.assertEqual(notice.read_at, read_at)
        unread = self.client.get(reverse("notifications"), {"unread": "1"}).data["results"]
        self.assertEqual([item["kind"] for item in unread], ["review"])
        self.access.delete()
        self.assertEqual(self.client.get(reverse("notifications")).data["count"], 0)

    def test_deadline_reminders_are_deduplicated_and_scoped(self):
        for days, completion in ((-1, 0), (1, 0), (-2, 100), (120, 0)):
            WorkItem.objects.create(
                project=self.project, kind="milestone", title=f"Milestone {days}",
                assignee=self.officer, planned_start=self.today - timedelta(days=3),
                planned_end=self.today + timedelta(days=days), percent_complete=completion,
            )
        self.client.force_login(self.officer)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("notification-sync")).status_code, 204)
        notices = self.client.get(reverse("notifications")).data["results"]
        self.assertCountEqual([notice["kind"] for notice in notices], ["upcoming", "overdue"])
