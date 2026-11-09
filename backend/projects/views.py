from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView, ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .access import eligible_accounts, visible_projects
from .models import Project, ProjectAuditEvent
from .progress import with_progress
from .serializers import (
    ProjectArchiveSerializer, ProjectAuditSerializer, ProjectCreateSerializer,
    ProjectRegisterFilters, ProjectSerializer,
)


class ProjectPagination(PageNumberPagination):
    page_size = 20


class ProjectListCreateView(ListCreateAPIView):
    serializer_class = ProjectSerializer
    pagination_class = ProjectPagination
    filter_backends = [SearchFilter]
    search_fields = ["title", "department"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProjectCreateSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        params = ProjectRegisterFilters(data=self.request.query_params.dict())
        params.is_valid(raise_exception=True)
        filters = params.validated_data
        projects = visible_projects(self.request.user).filter(archived_at__isnull=not filters["archived"])
        for field in ("department", "status"):
            value = self.request.query_params.get(field)
            if value:
                projects = projects.filter(**{field: value})
        for field, lookup in (
            ("project_id", "pk"), ("owner", "owner__username__icontains"),
            ("start", "planned_end__gte"), ("end", "planned_start__lte"),
        ):
            if field in filters:
                projects = projects.filter(**{lookup: filters[field]})
        return with_progress(projects)

    def create(self, request, *args, **kwargs):
        if not request.user.has_perm("projects.add_project"):
            raise PermissionDenied("You do not have permission to create projects.")
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        owner = self.request.user
        manager_id = serializer.validated_data.pop("manager_id", None)
        if manager_id is not None:
            if not owner.is_superuser:
                raise PermissionDenied("Only an administrator can appoint a different project manager.")
            owner = get_object_or_404(eligible_accounts("change_project"), pk=manager_id)
        project = serializer.save(owner=owner)
        ProjectAuditEvent.objects.create(
            project=project, actor=self.request.user, action="created", changes={"manager_id": owner.pk}
        )


class ProjectDetailView(RetrieveUpdateAPIView):
    serializer_class = ProjectSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        projects = visible_projects(self.request.user)
        if self.request.method == "PATCH":
            return projects.select_for_update()
        return projects

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def get_object(self):
        project = super().get_object()
        if self.request.method != "PATCH":
            return project
        user = self.request.user
        if not user.has_perm("projects.change_project") or (
            project.owner_id != user.pk and not user.is_superuser
        ):
            raise PermissionDenied("You do not have permission to edit this project.")
        if project.archived_at:
            raise ValidationError({"detail": "Restore this project before editing it."})
        return project

    def perform_update(self, serializer):
        before = self.get_serializer(serializer.instance).data
        reason = serializer.validated_data.pop("budget_revision_reason", "")
        serializer.save()
        after = serializer.data
        changes = {
            field: {"before": before[field], "after": after[field]}
            for field in serializer.validated_data
            if before[field] != after[field]
        }
        if changes:
            if reason and ("approved_budget" in changes or "currency" in changes):
                changes["budget_revision_reason"] = reason
            ProjectAuditEvent.objects.create(
                project=serializer.instance,
                actor=self.request.user,
                action="updated",
                changes=changes,
            )


class ProjectAuditListView(ListAPIView):
    serializer_class = ProjectAuditSerializer
    pagination_class = ProjectPagination

    def get_queryset(self):
        user = self.request.user
        project = get_object_or_404(visible_projects(user), pk=self.kwargs["pk"])
        if project.owner_id != user.pk and not user.has_perm("projects.view_projectauditevent"):
            raise PermissionDenied("You do not have permission to view this project's history.")
        return ProjectAuditEvent.objects.filter(project=project)


class ProjectArchiveView(GenericAPIView):
    serializer_class = ProjectArchiveSerializer

    @transaction.atomic
    def post(self, request, pk):
        user = request.user
        project = get_object_or_404(visible_projects(user).select_for_update(), pk=pk)
        if not user.has_perm("projects.change_project") or (
            project.owner_id != user.pk and not user.is_superuser
        ):
            raise PermissionDenied("You do not have permission to archive or restore this project.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        archive = serializer.validated_data["archived"]
        if archive and project.status not in (Project.Status.COMPLETED, Project.Status.CANCELLED):
            raise ValidationError({"detail": "Only completed or cancelled projects can be archived."})
        if archive != bool(project.archived_at):
            previous = project.archived_at
            project.archived_at = timezone.now() if archive else None
            project.save(update_fields=["archived_at"])
            ProjectAuditEvent.objects.create(
                project=project, actor=user, action="archived" if archive else "restored",
                changes={"archived_at": {
                    "before": previous.isoformat() if previous else None,
                    "after": project.archived_at.isoformat() if project.archived_at else None,
                }},
            )
        return Response(ProjectSerializer(project, context={"request": request}).data)
