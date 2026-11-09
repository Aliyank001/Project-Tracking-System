from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Notification, ProgressUpdate, Project, ProjectAccess, ProjectStatusSetting, RiskFeedback, WorkItem


class AcceptanceTests(APITestCase):
    def setUp(self):
        call_command("setup_company_roles", verbosity=0)
        users = get_user_model().objects
        self.admin = users.create_superuser(username="admin")
        self.auditor = users.create_user(username="auditor")
        self.auditor.groups.add(Group.objects.get(name="Auditors"))
        self.today = timezone.localdate()
        self.payload = {
            "title": "Road works", "department": "Works", "status": "active",
            "planned_start": self.today - timedelta(days=20),
            "planned_end": self.today + timedelta(days=20),
            "approved_budget": "1000.00", "currency": "NGN",
        }
        self.project = Project.objects.create(owner=self.admin, **self.payload)
        ProjectAccess.objects.create(project=self.project, user=self.auditor)
        self.client.force_login(self.admin)

    def submit_progress(self, project, percent):
        return self.client.post(reverse("progress-update-list", args=[project]), {
            "reporting_date": self.today, "percent_complete": percent, "summary": "Site update",
        }, format="json")

    def test_at09_core_remains_available_with_forecast_missing(self):
        with patch("projects.analytics.model_data", side_effect=FileNotFoundError):
            created = self.client.post(reverse("project-list"), self.payload, format="json")
            self.assertEqual(created.status_code, 201)
            project = created.data["id"]
            self.assertEqual(self.submit_progress(project, -1).status_code, 400)
            self.assertEqual(self.submit_progress(project, 30).status_code, 201)
            self.assertEqual(self.client.post(reverse("work-item-list", args=[project]), {
                "title": "Inspection", "kind": "milestone",
                "planned_start": self.today, "planned_end": self.today,
            }, format="json").status_code, 201)
            forecast = self.client.get(reverse("analytics", args=[project]))
            self.assertEqual(forecast.data["forecast"]["status"], "insufficient_data")
            report = self.client.get(reverse("report"), {"project_id": project})
            self.assertEqual(report.data["count"], 1)
            self.assertEqual(report.data["results"][0]["progress"], 30)

    def test_at10_schedule_alert_explanation_and_private_dismissal(self):
        self.assertEqual(self.submit_progress(self.project.pk, 20).status_code, 201)
        dashboard = reverse("dashboard")
        risk = next(flag for flag in self.client.get(dashboard).data["flags"] if flag["type"] == "schedule")
        self.assertEqual((risk["planned_percent"], risk["actual_percent"]), (50, 20))
        self.assertEqual(risk["method"], "rule")
        self.assertIn("generated_at", risk)
        self.assertIn("estimated 50%", risk["reason"])
        url = reverse("risk-response", args=[self.project.pk])
        feedback = {"signature": risk["signature"], "reason": "Baseline under review", "dismiss": True}
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.post(url, feedback, format="json").status_code, 403)
        self.assertEqual(self.client.patch(reverse("project-detail", args=[self.project.pk]), {
            "title": "Edited",
        }, format="json").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, feedback, format="json").status_code, 204)
        self.assertTrue(RiskFeedback.objects.filter(signature=risk["signature"], dismissed=True).exists())
        self.assertFalse(self.client.get(dashboard).data["flags"])
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(dashboard).data["flags"][0]["signature"], risk["signature"])
        self.client.force_login(self.admin)
        update = ProgressUpdate.objects.get(project=self.project)
        update.percent_complete = 25
        update.save(update_fields=["percent_complete"])
        self.assertNotEqual(self.client.get(dashboard).data["flags"][0]["signature"], risk["signature"])

    def test_reminder_job_and_status_config(self):
        WorkItem.objects.create(
            project=self.project, title="Inspection", kind="milestone",
            planned_start=self.today, planned_end=self.today,
        )
        for _ in range(2):
            call_command("send_deadline_reminders", verbosity=0)
        self.assertEqual(Notification.objects.filter(recipient=self.admin, kind="upcoming").count(), 1)
        ProjectStatusSetting.objects.create(status="active", label="Under delivery", enabled=False)
        options = self.client.get(reverse("project-statuses")).data
        self.assertIn({"value": "active", "label": "Under delivery", "enabled": False}, options)
        self.assertEqual(self.client.post(reverse("project-list"), self.payload, format="json").status_code, 400)
        self.assertEqual(self.client.patch(reverse("project-detail", args=[self.project.pk]), {
            "title": "Existing active project",
        }, format="json").status_code, 200)
