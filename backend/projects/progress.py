from django.db.models import Count, F, OuterRef, Subquery, Sum

from .models import ProgressUpdate, WorkItem


def with_progress(projects):
    updates = ProgressUpdate.objects.filter(project_id=OuterRef("pk"))
    items = (
        WorkItem.objects.filter(project_id=OuterRef("pk"), is_active=True)
        .order_by().values("project_id")
        .annotate(
            count=Count("pk"),
            weighted_count=Count("weight"),
            total_weight=Sum("weight"),
            weighted_points=Sum(F("weight") * F("percent_complete")),
        )
    )
    return projects.annotate(
        latest_progress=Subquery(updates.values("percent_complete")[:1]),
        latest_reporting_date=Subquery(updates.values("reporting_date")[:1]),
        item_count=Subquery(items.values("count")),
        weighted_count=Subquery(items.values("weighted_count")),
        total_weight=Subquery(items.values("total_weight")),
        weighted_points=Subquery(items.values("weighted_points")),
    )


def project_progress(project):
    if project.total_weight and project.item_count == project.weighted_count:
        return round(project.weighted_points / project.total_weight, 2), "weighted"
    if project.latest_progress is not None:
        return project.latest_progress, "self_reported"
    return None, "unavailable"
