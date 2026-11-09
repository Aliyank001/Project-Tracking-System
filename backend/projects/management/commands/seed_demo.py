from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from projects.models import Expenditure, ProgressUpdate, Project, ProjectAuditEvent, WorkItem


class Command(BaseCommand):
    help = "Create synthetic portfolio records for an existing local user."

    def add_arguments(self, parser):
        parser.add_argument("username")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            owner = get_user_model().objects.get(username=options["username"])
        except get_user_model().DoesNotExist as error:
            raise CommandError("Create the account first with manage.py createsuperuser.") from error

        today = timezone.localdate()
        records = [
            ("Owerri Road Rehabilitation", "Public Works", "active", "48000000.00", "29000000.00", 48),
            ("Primary Health Centre Upgrade", "Health", "active", "24000000.00", "15000000.00", 72),
            ("Community Water Extension", "Water Resources", "planned", "18500000.00", "2500000.00", 15),
            ("School Roof Renewal", "Education", "completed", "12500000.00", "11800000.00", 100),
        ]
        for index, (title, department, status, budget, spend, progress) in enumerate(records, 1):
            project_id = UUID(f"20000000-0000-4000-8000-{index:012d}")
            project, created = Project.objects.get_or_create(
                pk=project_id,
                defaults={
                    "title": title, "department": department, "owner": owner, "currency": "NGN",
                    "status": status, "approved_budget": Decimal(budget),
                    "description": "Synthetic record for the University of Sindh coursework demonstration.",
                    "planned_start": today - timedelta(days=40),
                    "planned_end": today + timedelta(days=28 if status != "completed" else -1),
                },
            )
            if not created:
                continue
            for title, offset, percent in (
                ("Site assessment", -20, 100),
                ("First delivery checkpoint", -3, 35 if index == 1 else 100),
                ("Final inspection", -1 if status == "completed" else 9, 100 if status == "completed" else 0),
            ):
                WorkItem.objects.create(
                    project=project, title=title, kind=WorkItem.Kind.MILESTONE, assignee=owner,
                    planned_start=today + timedelta(days=offset - 5), planned_end=today + timedelta(days=offset),
                    percent_complete=percent,
                )
            ProgressUpdate.objects.create(
                project=project, author=owner, reporting_date=today - timedelta(days=1),
                percent_complete=progress, summary="Latest field inspection recorded.",
            )
            Expenditure.objects.create(
                project=project, entered_by=owner, date=today - timedelta(days=2),
                amount=Decimal(spend), category="Works", reference=f"DEMO-{index:03d}",
            )
            ProjectAuditEvent.objects.create(project=project, actor=owner, action="created", changes={})
        self.stdout.write(self.style.SUCCESS("Synthetic portfolio ready. Existing demo projects were preserved."))

