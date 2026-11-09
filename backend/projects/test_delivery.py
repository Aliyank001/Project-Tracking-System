import csv
from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import ProgressUpdate, Project, WorkItem


class PortfolioDeliveryTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.admin = users.create_superuser(username="admin", password="Integration-test-password-26")
        self.viewer = users.create_user(username="viewer")
        self.today = timezone.localdate()
        self.project = Project.objects.create(
            title="=Road works", department="Public Works", owner=self.admin, status="active",
            approved_budget="1000.00", currency="NGN",
            planned_start=self.today - timedelta(days=30), planned_end=self.today + timedelta(days=15),
        )
        self.client.force_login(self.admin)

    def record_expenditure(self, amount):
        return self.client.post(reverse("expenditure", args=[self.project.pk]), {
            "date": str(self.today), "amount": amount, "category": "Materials", "reference": "REF-01",
        }, format="json")

    def test_expenditure_audit_currency_and_dashboard_risks(self):
        self.assertEqual(self.record_expenditure("-1.00").status_code, 400)
        self.assertEqual(self.record_expenditure("1200.00").status_code, 201)
        expenditure = self.client.get(reverse("expenditure", args=[self.project.pk])).data
        self.assertEqual(expenditure["summary"]["remaining"], "-200.00")
        self.assertEqual(expenditure["summary"]["variance"], "200.00")
        detail = reverse("project-detail", args=[self.project.pk])
        self.assertEqual(self.client.patch(detail, {"currency": "USD"}, format="json").status_code, 400)
        history = self.client.get(reverse("project-audit", args=[self.project.pk])).data
        self.assertEqual(history["results"][0]["action"], "expenditure_added")
        WorkItem.objects.create(
            project=self.project, kind="milestone", title="Inspection",
            planned_start=self.today - timedelta(days=10), planned_end=self.today - timedelta(days=1),
        )
        dashboard = self.client.get(reverse("dashboard")).data
        self.assertEqual(dashboard["overdue_count"], 1)
        self.assertEqual({flag["type"] for flag in dashboard["flags"]}, {"overdue", "budget", "stale"})

    def test_csv_scopes_records_and_escapes_formula_fields(self):
        url = reverse("report")
        response = self.client.get(url, {"export": "csv", "department": "Public Works"})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(StringIO(response.content.decode())))
        self.assertEqual([row["title"] for row in rows], ["'=Road works"])
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).data["count"], 0)

    def test_pdf_and_excel_exports_use_report_scope(self):
        from openpyxl import load_workbook

        url = reverse("report")
        pdf = self.client.get(url, {"export": "pdf", "department": "Public Works"})
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        book = self.client.get(url, {"export": "xlsx", "department": "Public Works"})
        self.assertEqual(book.status_code, 200)
        sheet = load_workbook(BytesIO(book.content), read_only=True).active
        rows = list(sheet.rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0].value, "=Road works")
        self.assertEqual(rows[1][0].data_type, "s")
        self.client.force_login(self.viewer)
        empty = self.client.get(url, {"export": "xlsx"})
        sheet = load_workbook(BytesIO(empty.content), read_only=True).active
        self.assertEqual(len(list(sheet.rows)), 1)

    def test_report_charts_filter_totals_and_keep_currencies_separate(self):
        self.assertEqual(self.record_expenditure("250.00").status_code, 201)
        for title, department, currency in (
            ("Second works project", "Public Works", "NGN"),
            ("Other currency", "Public Works", "PKR"),
            ("Filtered out", "Health", "NGN"),
        ):
            Project.objects.create(
                title=title, department=department, owner=self.admin,
                planned_start=self.today, planned_end=self.today,
                status="planned", approved_budget="500.00", currency=currency,
            )
        url = reverse("report")
        response = self.client.get(url, {"department": "Public Works"})
        self.assertEqual(response.data["count"], 3)
        charts = response.data["charts"]
        self.assertEqual(charts["status_counts"], {"active": 1, "planned": 2})
        self.assertEqual(Decimal(charts["spending"]["NGN"]["budget"]), Decimal("1500.00"))
        self.assertEqual(Decimal(charts["spending"]["NGN"]["recorded"]), Decimal("250.00"))
        self.assertEqual(Decimal(charts["spending"]["PKR"]["budget"]), Decimal("500.00"))
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).data["charts"], {"status_counts": {}, "spending": {}})

    def test_weighted_progress_falls_back_until_all_active_items_are_weighted(self):
        ProgressUpdate.objects.create(
            project=self.project, author=self.admin, reporting_date=self.today,
            percent_complete=20, summary="Reported progress",
        )
        common = {
            "project": self.project, "kind": "milestone", "title": "Inspection",
            "planned_start": self.today, "planned_end": self.today,
        }
        WorkItem.objects.create(**common, weight=3, percent_complete=100)
        second = WorkItem.objects.create(**common, percent_complete=0)
        url = reverse("project-detail", args=[self.project.pk])
        self.assertEqual(self.client.get(url).data["progress_summary"], {
            "percent": 20, "source": "self_reported",
        })
        second.weight = 1
        second.save(update_fields=["weight"])
        self.assertEqual(self.client.get(url).data["progress_summary"], {
            "percent": 75.0, "source": "weighted",
        })
        self.assertEqual(self.client.get(reverse("report")).data["results"][0]["progress"], 75.0)

    def test_analytics_uses_forecast_and_scenarios_without_writing(self):
        url = reverse("analytics", args=[self.project.pk])
        self.assertEqual(self.client.get(url).data["forecast"]["status"], "insufficient_data")
        WorkItem.objects.create(
            project=self.project, kind="milestone", title="Inspection", percent_complete=50,
            planned_start=self.today - timedelta(days=10), planned_end=self.today - timedelta(days=1),
        )
        ProgressUpdate.objects.create(
            project=self.project, author=self.admin, reporting_date=self.today,
            percent_complete=50, summary="Half complete",
        )
        self.assertEqual(self.record_expenditure("500.00").status_code, 201)
        data = self.client.get(url, {"budget_cut": 20, "extra_days": 10, "price_increase": 10}).data
        self.assertEqual(data["evm"]["eac"], "1000.00")
        self.assertEqual(data["forecast"]["status"], "available")
        self.assertEqual([row["case"] for row in data["scenarios"]], ["best", "base", "worst"])
        self.assertEqual(data["scenarios"][1]["budget"], "800.00")
        self.project.refresh_from_db()
        self.assertEqual(str(self.project.approved_budget), "1000.00")

