from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Project, ProjectAccess


def visible_projects(user):
    projects = Project.objects.all()
    if user.is_superuser:
        return projects
    if user.has_perm("projects.view_project"):
        assigned = ProjectAccess.objects.filter(user=user).values("project_id")
        return projects.filter(Q(owner=user) | Q(pk__in=assigned))
    return projects.filter(owner=user)


def manages_project(user, project):
    return user.is_superuser or (
        project.owner_id == user.pk and user.has_perm("projects.change_project")
    )


def portfolio_projects(user):
    projects = visible_projects(user)
    if user.is_superuser or user.has_perm("projects.view_projectauditevent"):
        return projects
    return projects.filter(owner=user)


def can_view_portfolio(user, project):
    return (
        user.is_superuser or project.owner_id == user.pk
        or user.has_perm("projects.view_projectauditevent")
    )


def eligible_accounts(permission):
    match = {"content_type__app_label": "projects", "codename": permission}
    return get_user_model().objects.filter(
        Q(**{f"user_permissions__{field}": value for field, value in match.items()})
        | Q(**{f"groups__permissions__{field}": value for field, value in match.items()}),
        is_active=True, is_superuser=False,
    ).distinct().order_by("username")
