from collections.abc import Mapping

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.utils.http import content_disposition_header
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response

from .access import can_view_portfolio, visible_projects
from .models import ProgressEvidence, ProgressReview, ProgressUpdate, ProjectAuditEvent, WorkItem
from .notifications import notify_assignment, notify_review
from .tracking_serializers import ProgressReviewSerializer, ProgressUpdateSerializer, WorkItemSerializer
from .views import ProjectPagination


class ProjectTrackingMixin:
    @cached_property
    def project(self):
        projects = visible_projects(self.request.user)
        if self.request.method in ("POST", "PATCH"):
            projects = projects.select_for_update()
        project = get_object_or_404(projects, pk=self.kwargs["project_id"])
        if project.archived_at and self.request.method in ("POST", "PATCH"):
            raise ValidationError({"detail": "Restore this project before making changes."})
        return project

    def audit(self, action, changes):
        ProjectAuditEvent.objects.create(
            project=self.project,
            actor=self.request.user,
            action=action,
            changes=changes,
        )

    def visible_work_items(self):
        items = WorkItem.objects.filter(project=self.project)
        user = self.request.user
        return items if can_view_portfolio(user, self.project) else items.filter(assignee=user)

    def visible_updates(self):
        updates = ProgressUpdate.objects.filter(project=self.project)
        user = self.request.user
        if can_view_portfolio(user, self.project) or user.has_perm("projects.add_progressreview"):
            return updates
        return updates.filter(author=user)


class WorkItemListCreateView(ProjectTrackingMixin, ListCreateAPIView):
    serializer_class = WorkItemSerializer
    pagination_class = ProjectPagination

    def get_queryset(self):
        items = self.visible_work_items()
        kind = self.request.query_params.get("kind")
        return items.filter(kind=kind) if kind else items

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        user = request.user
        project = self.project
        if not user.has_perm("projects.add_workitem") or (
            project.owner_id != user.pk and not user.is_superuser
        ):
            raise PermissionDenied("Only an authorized project owner can add work items.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        item = serializer.save(project=self.project)
        notify_assignment(item)
        self.audit("work_item_created", {"work_item_id": item.pk})


class WorkItemDetailView(ProjectTrackingMixin, RetrieveUpdateAPIView):
    serializer_class = WorkItemSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return self.visible_work_items()

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def get_object(self):
        item = super().get_object()
        if self.request.method != "PATCH":
            return item

        user = self.request.user
        if not user.has_perm("projects.change_workitem"):
            raise PermissionDenied("You do not have permission to update work items.")
        if user.is_superuser or self.project.owner_id == user.pk:
            return item
        if (
            item.assignee_id == user.pk
            and item.is_active
            and isinstance(self.request.data, Mapping)
            and set(self.request.data) == {"percent_complete"}
        ):
            return item
        raise PermissionDenied("Assigned contributors can only update completion on their active work items.")

    def perform_update(self, serializer):
        before = self.get_serializer(serializer.instance).data
        item = serializer.save()
        if item.assignee_id != before["assignee"] or (item.is_active and not before["is_active"]):
            notify_assignment(item)
        after = serializer.data
        changes = {
            field: {"before": before[field], "after": after[field]}
            for field in serializer.validated_data
            if before[field] != after[field]
        }
        if changes:
            self.audit("work_item_updated", {"work_item_id": item.pk, "fields": changes})


class ProgressUpdateMixin(ProjectTrackingMixin):
    def get_queryset(self):
        return (
            self.visible_updates()
            .select_related("review", "evidence", "replacement")
            .defer("evidence__content")
        )


class ProgressUpdateListCreateView(ProgressUpdateMixin, ListCreateAPIView):
    serializer_class = ProgressUpdateSerializer
    pagination_class = ProjectPagination

    def get_queryset(self):
        updates = super().get_queryset()
        if self.request.query_params.get("review") == "pending":
            if not self.request.user.has_perm("projects.add_progressreview"):
                raise PermissionDenied("You do not have permission to review progress.")
            return updates.filter(review__isnull=True, project__archived_at__isnull=True).exclude(
                author=self.request.user
            )
        return updates

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not request.user.has_perm("projects.add_progressupdate"):
            raise PermissionDenied("You do not have permission to submit progress updates.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        update = serializer.save(project=self.project, author=self.request.user)
        self.audit("progress_submitted", {"progress_update_id": update.pk})


class ProgressReviewView(ProgressUpdateMixin, GenericAPIView):
    serializer_class = ProgressReviewSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        update = self.get_object()
        if not request.user.has_perm("projects.add_progressreview") or update.author_id == request.user.pk:
            raise PermissionDenied("A designated reviewer must be different from the author.")
        if hasattr(update, "review"):
            raise ValidationError({"detail": "This revision already has a review decision."})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save(update=update, reviewer=request.user)
        notify_review(review, update)
        self.audit("progress_reviewed", {
            "progress_update_id": update.pk, "decision": review.decision, "comment": review.comment,
        })
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProgressResubmitView(ProgressUpdateMixin, GenericAPIView):
    serializer_class = ProgressUpdateSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        original = self.get_object()
        if original.author_id != request.user.pk or not request.user.has_perm("projects.add_progressupdate"):
            raise PermissionDenied("Only the original contributor can resubmit.")
        if (
            not hasattr(original, "review")
            or original.review.decision != ProgressReview.Decision.CORRECTION
            or hasattr(original, "replacement")
        ):
            raise ValidationError({"detail": "Only a revision awaiting correction can be resubmitted."})
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update = serializer.save(project=self.project, author=request.user, replaces=original)
        self.audit("progress_resubmitted", {"progress_update_id": update.pk, "replaces": original.pk})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProgressEvidenceView(ProjectTrackingMixin, GenericAPIView):
    def get(self, request, *args, **kwargs):
        evidence = get_object_or_404(
            ProgressEvidence, update_id=kwargs["pk"], update__in=self.visible_updates()
        )
        response = HttpResponse(bytes(evidence.content), content_type="application/octet-stream")
        response["Content-Disposition"] = content_disposition_header(True, evidence.filename)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response

