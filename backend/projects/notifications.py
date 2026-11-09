from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from .models import Notification, ProgressReview, Project, WorkItem
from .access import visible_projects
from .views import ProjectPagination


def notify_assignment(item):
    if item.assignee_id and item.is_active and item.percent_complete < 100:
        Notification.objects.create(
            recipient_id=item.assignee_id, project_id=item.project_id,
            kind=Notification.Kind.ASSIGNMENT, message=f"Assigned to you: {item.title}",
        )


def notify_review(review, update):
    decision = "approved" if review.decision == ProgressReview.Decision.APPROVED else "returned for correction"
    Notification.objects.create(
        recipient_id=update.author_id, project_id=update.project_id,
        kind=Notification.Kind.REVIEW,
        message=f"Progress update #{update.pk} was {decision}.",
    )


def user_notifications(user):
    return Notification.objects.filter(recipient=user, project__in=visible_projects(user))


class NotificationSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.title", read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "project", "project_title", "kind", "message", "created_at", "read_at")


class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer
    pagination_class = ProjectPagination

    def get_queryset(self):
        notices = user_notifications(self.request.user).select_related("project")
        if self.request.query_params.get("unread") == "1":
            notices = notices.filter(read_at__isnull=True)
        return notices


@api_view(["GET"])
def notification_count(request):
    return Response({"unread_count": user_notifications(request.user).filter(read_at__isnull=True).count()})


@api_view(["POST"])
def mark_notification_read(request, pk):
    notices = user_notifications(request.user)
    notice = get_object_or_404(notices, pk=pk)
    if notice.read_at is None:
        notices.filter(pk=pk, read_at__isnull=True).update(read_at=timezone.now())
    return Response(status=204)


def generate_deadline_notifications(user, today):
    items = WorkItem.objects.filter(
        Q(assignee=user) | Q(assignee__isnull=True, project__owner=user),
        project__in=visible_projects(user), project__archived_at__isnull=True,
        kind=WorkItem.Kind.MILESTONE, is_active=True, percent_complete__lt=100,
        planned_end__lte=today + timedelta(days=settings.MILESTONE_LOOKAHEAD_DAYS),
    ).exclude(project__status__in=(Project.Status.COMPLETED, Project.Status.CANCELLED))
    notices = []
    for item in items.iterator():
        overdue = item.planned_end < today
        kind = Notification.Kind.OVERDUE if overdue else Notification.Kind.UPCOMING
        prefix = "Overdue milestone" if overdue else "Upcoming milestone"
        notices.append(Notification(
            recipient=user, project_id=item.project_id, kind=kind,
            message=f"{prefix}: {item.title} (due {item.planned_end})",
            deadline_key=f"{kind}:{item.pk}:{item.planned_end}",
        ))
        if len(notices) == 250:
            Notification.objects.bulk_create(notices, ignore_conflicts=True)
            notices.clear()
    Notification.objects.bulk_create(notices, ignore_conflicts=True)


@api_view(["POST"])
def sync_deadline_notifications(request):
    generate_deadline_notifications(request.user, timezone.localdate())
    return Response(status=204)
