from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .access import eligible_accounts, manages_project, visible_projects
from .models import Project, ProjectAccess, ProjectAuditEvent


def account_rows(accounts):
    return list(accounts.values("id", "username", "first_name", "last_name"))


class AccountSelection(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)


@api_view(["GET"])
def manager_directory(request):
    if not request.user.is_superuser:
        raise PermissionDenied()
    return Response(account_rows(eligible_accounts("change_project")))


@api_view(["POST"])
@transaction.atomic
def assign_manager(request, project_id):
    if not request.user.is_superuser:
        raise PermissionDenied()
    project = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
    if project.archived_at:
        raise ValidationError({"detail": "Restore this project before changing its manager."})
    data = AccountSelection(data=request.data)
    data.is_valid(raise_exception=True)
    manager = get_object_or_404(eligible_accounts("change_project"), pk=data.validated_data["user_id"])
    previous = project.owner_id
    if previous != manager.pk:
        project.owner = manager
        project.save(update_fields=["owner"])
        ProjectAuditEvent.objects.create(
            project=project, actor=request.user, action="manager_assigned",
            changes={"owner": {"before": previous, "after": manager.pk}},
        )
    return Response({"owner": manager.pk})


@api_view(["GET", "POST", "DELETE"])
@transaction.atomic
def project_team(request, project_id):
    projects = visible_projects(request.user)
    if request.method != "GET":
        projects = projects.select_for_update()
    project = get_object_or_404(projects, pk=project_id)
    if not manages_project(request.user, project):
        raise PermissionDenied("Only the project manager can manage this team.")
    if request.method == "GET":
        memberships = ProjectAccess.objects.filter(project=project)
        accounts = get_user_model().objects
        members = account_rows(accounts.filter(pk__in=memberships.values("user_id")).order_by("username"))
        owner = account_rows(accounts.filter(pk=project.owner_id))[0]
        candidates = [] if project.archived_at else account_rows(
            eligible_accounts("view_project").exclude(pk=project.owner_id)
            .exclude(pk__in=memberships.values("user_id"))
        )
        return Response({"owner": owner, "members": members, "candidates": candidates})
    if project.archived_at:
        raise ValidationError({"detail": "Restore this project before changing its team."})
    data = AccountSelection(data=request.data)
    data.is_valid(raise_exception=True)
    user_id = data.validated_data["user_id"]
    if request.method == "POST":
        account = get_object_or_404(eligible_accounts("view_project").exclude(pk=project.owner_id), pk=user_id)
        _, changed = ProjectAccess.objects.get_or_create(project=project, user=account)
        action = "access_granted"
    else:
        changed, _ = ProjectAccess.objects.filter(project=project, user_id=user_id).delete()
        action = "access_revoked"
    if changed:
        ProjectAuditEvent.objects.create(
            project=project, actor=request.user, action=action, changes={"user_id": user_id}
        )
    return Response(status=204)
