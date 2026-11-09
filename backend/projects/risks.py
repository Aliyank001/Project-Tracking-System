import hashlib
import json
from datetime import timedelta

from django.conf import settings

from .models import Project, WorkItem
from .progress import project_progress


def dashboard_risks(projects, today):
    flags, upcoming = [], []
    open_projects = {
        project.pk for project in projects
        if project.status not in (Project.Status.COMPLETED, Project.Status.CANCELLED)
    }
    milestones = WorkItem.objects.filter(
        project_id__in=open_projects, kind=WorkItem.Kind.MILESTONE,
        is_active=True, percent_complete__lt=100,
        planned_end__lte=today + timedelta(days=settings.MILESTONE_LOOKAHEAD_DAYS),
    )
    for item in milestones:
        entry = {
            "project_id": str(item.project_id), "work_item_id": item.pk, "title": item.title,
            "due_date": item.planned_end.isoformat(),
        }
        if item.planned_end < today:
            flags.append({**entry, "reason": "Incomplete milestone is overdue.", "type": "overdue"})
        else:
            upcoming.append(entry)

    for project in projects:
        if project.pk not in open_projects:
            continue
        risk = {"project_id": str(project.pk), "title": project.title}
        recorded = project.recorded or 0
        if recorded > project.approved_budget:
            flags.append({**risk, "reason": "Recorded spending exceeds approved budget.", "type": "budget",
                          "recorded": str(recorded), "budget": str(project.approved_budget)})
        latest = project.latest_reporting_date
        stale_days = settings.PROGRESS_STALE_DAYS
        if (latest or project.planned_start) < today - timedelta(days=stale_days):
            flags.append({**risk, "reason": f"No progress report in the last {stale_days} days.", "type": "stale",
                          "last_report": latest.isoformat() if latest else None})
        progress, source = project_progress(project)
        if project.status == Project.Status.ACTIVE and progress is not None and project.planned_start <= today:
            duration = max(1, (project.planned_end - project.planned_start).days)
            planned = min(100, round(100 * (today - project.planned_start).days / duration))
            if planned - progress >= settings.SCHEDULE_LAG_POINTS:
                flags.append({
                    **risk, "type": "schedule", "planned_percent": planned,
                    "actual_percent": progress, "progress_source": source,
                    "reason": f"Progress is {progress:g}% against an estimated {planned}% planned by today.",
                })
    project_lookup = {str(project.pk): project for project in projects}
    for flag in flags:
        if flag["type"] == "schedule":
            # A new reported completion or baseline reopens the flag. Passing
            # another day alone does not immediately undo a dismissal.
            project = project_lookup[flag["project_id"]]
            evidence = {
                "actual_percent": flag["actual_percent"], "source": flag["progress_source"],
                "planned_start": project.planned_start.isoformat(), "planned_end": project.planned_end.isoformat(),
            }
            signature_data = [flag["project_id"], flag["type"], evidence]
        else:
            signature_data = flag
        flag["signature"] = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    return flags, upcoming
