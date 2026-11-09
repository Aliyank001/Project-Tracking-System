from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse

from .models import Project, ProjectAccess, ProjectAuditEvent


class AdminAuditTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser(username="admin")
        self.member = User.objects.create_user(username="member")
        self.client.force_login(self.actor)

    def test_project_access_grant_and_revoke_enter_project_history(self):
        project = Project.objects.create(
            title="Public works", department="Works", owner=self.actor,
            planned_start="2026-11-01", planned_end="2026-12-01",
            approved_budget="1000", currency="NGN",
        )
        response = self.client.post(reverse("admin:projects_projectaccess_add"), {
            "project": project.pk, "user": self.member.pk, "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        access = ProjectAccess.objects.get(project=project, user=self.member)
        response = self.client.post(
            reverse("admin:projects_projectaccess_delete", args=[access.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 302)
        events = ProjectAuditEvent.objects.filter(project=project)
        self.assertEqual(list(events.values_list("action", flat=True)), ["access_revoked", "access_granted"])
        self.assertTrue(all(event.actor_id == self.actor.pk for event in events))

    def test_group_permission_changes_enter_admin_history(self):
        group = Group.objects.create(name="Reviewers")
        permission = Permission.objects.get(
            content_type__app_label="projects", codename="add_progressreview"
        )
        response = self.client.post(reverse("admin:auth_group_change", args=[group.pk]), {
            "name": group.name, "permissions": [permission.pk], "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        event = LogEntry.objects.get(user=self.actor, change_message__startswith="Role configuration:")
        self.assertIn("add_progressreview", event.get_change_message())
