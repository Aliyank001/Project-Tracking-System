from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from projects.models import Project, WorkItem
from projects.notifications import generate_deadline_notifications


class Command(BaseCommand):
    help = "Generate in-app milestone deadline reminders without an open browser."

    def handle(self, *args, **options):
        assignees = WorkItem.objects.filter(kind=WorkItem.Kind.MILESTONE, is_active=True).values("assignee_id")
        owners = Project.objects.filter(archived_at__isnull=True).values("owner_id")
        accounts = get_user_model().objects.filter(
            Q(pk__in=assignees) | Q(pk__in=owners), is_active=True
        )
        today = timezone.localdate()
        for user in accounts.iterator():
            generate_deadline_notifications(user, today)
        self.stdout.write(self.style.SUCCESS("Deadline reminder check complete."))
