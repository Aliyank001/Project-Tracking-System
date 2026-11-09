from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import ProgressUpdate, ProjectAuditEvent, WorkItem


class CompanyWorkflowTests(APITestCase):
    def test_admin_manager_and_employee_workflow(self):
        call_command("setup_company_roles", verbosity=0)
        users = get_user_model().objects
        admin = users.create_superuser(username="company-admin")
        manager = users.create_user(username="manager")
        employee = users.create_user(username="employee")
        colleague = users.create_user(username="colleague")
        manager.groups.add(Group.objects.get(name="Project Managers"))
        for user in (employee, colleague):
            user.groups.add(Group.objects.get(name="Project Officers"))
        self.client.force_login(admin)
        project = self.client.post(reverse("project-list"), {
            "title": "Road repairs", "department": "Works", "manager_id": manager.pk,
            "planned_start": "2026-11-10", "planned_end": "2026-12-10",
            "approved_budget": "1000", "currency": "NGN",
        }, format="json")
        self.assertEqual(project.status_code, 201, project.data)
        self.assertEqual(project.data["owner"], manager.pk)
        project_id = project.data["id"]
        team = reverse("project-team", args=[project_id])
        items = reverse("work-item-list", args=[project_id])
        updates = reverse("progress-update-list", args=[project_id])
        detail = reverse("project-detail", args=[project_id])

        self.client.force_login(manager)
        for user in (employee, colleague):
            self.assertEqual(self.client.post(team, {"user_id": user.pk}).status_code, 204)
        self.assertEqual(len(self.client.get(team).data["members"]), 2)
        payload = {"kind": "task", "planned_start": "2026-11-10", "planned_end": "2026-12-10"}
        private = self.client.post(items, {**payload, "title": "Peer task", "assignee": colleague.pk})
        self.assertEqual(private.status_code, 201)
        own = self.client.post(items, {
            **payload, "title": "My task", "assignee": employee.pk, "predecessor": private.data["id"],
        })
        self.assertEqual(own.status_code, 201)
        self.assertEqual(self.client.get(items).data["count"], 2)
        own_detail = reverse("work-item-detail", args=[project_id, own.data["id"]])
        peer_detail = reverse("work-item-detail", args=[project_id, private.data["id"]])

        self.client.force_login(colleague)
        peer_update = self.client.post(updates, {
            "reporting_date": "2026-11-11", "percent_complete": 50, "summary": "Peer progress",
        })
        self.assertEqual(peer_update.status_code, 201)
        self.client.force_login(employee)
        visible = self.client.get(items).data["results"]
        self.assertEqual([item["title"] for item in visible], ["My task"])
        self.assertIsNone(visible[0]["predecessor"])
        self.assertEqual(self.client.get(peer_detail).status_code, 404)
        self.assertEqual(self.client.patch(peer_detail, {"percent_complete": 100}).status_code, 404)
        completion = self.client.patch(own_detail, {"percent_complete": 100}, format="json")
        self.assertEqual(completion.status_code, 200, completion.data)
        self.assertEqual(self.client.get(updates).data["count"], 0)
        self.assertNotIn("approved_budget", self.client.get(detail).data)
        self.assertEqual(self.client.get(reverse("report")).data["count"], 0)
        self.assertEqual(self.client.get(team).status_code, 403)
        self.assertEqual(self.client.delete(team, {"user_id": colleague.pk}).status_code, 403)
        own_update = self.client.post(updates, {
            "reporting_date": "2026-11-11", "percent_complete": 100, "summary": "Completed",
        })
        self.assertEqual(own_update.status_code, 201)

        self.client.force_login(manager)
        self.assertEqual(self.client.delete(team, {"user_id": employee.pk}).status_code, 204)
        self.assertTrue(WorkItem.objects.filter(pk=own.data["id"], percent_complete=100).exists())
        self.assertTrue(ProgressUpdate.objects.filter(pk=own_update.data["id"]).exists())
        self.assertTrue(ProjectAuditEvent.objects.filter(
            project_id=project_id, action="access_revoked", actor=manager,
        ).exists())
        self.client.force_login(employee)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(own_detail).status_code, 404)
        self.assertEqual(self.client.get(updates).status_code, 404)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 200)
