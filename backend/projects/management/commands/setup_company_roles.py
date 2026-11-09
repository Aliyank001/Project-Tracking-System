from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create the default company role groups after migrating the database."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {
            "Project Managers": (
                "view_project", "add_project", "change_project", "add_workitem",
                "change_workitem", "add_progressupdate", "add_expenditure",
            ),
            "Project Officers": ("view_project", "change_workitem", "add_progressupdate"),
            "Reviewers": ("view_project", "add_progressreview"),
            "Auditors": ("view_project", "view_projectauditevent"),
        }
        for name, codenames in roles.items():
            group, created = Group.objects.get_or_create(name=name)
            if created:
                group.permissions.set(Permission.objects.filter(
                    content_type__app_label="projects", codename__in=codenames
                ))
        self.stdout.write("Company roles are available. Existing group permissions were preserved.")
