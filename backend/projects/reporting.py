import csv
from collections import Counter, defaultdict
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, OuterRef, Subquery, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .finance import budget_summary
from .models import Expenditure, Project, RiskFeedback, WorkItem
from .progress import project_progress, with_progress
from .report_exports import excel_report, pdf_report
from .access import manages_project, portfolio_projects, visible_projects
from .risks import dashboard_risks


class ReportFilters(serializers.Serializer):
    project_id = serializers.UUIDField(required=False)
    department = serializers.CharField(max_length=150, required=False)
    status = serializers.ChoiceField(choices=Project.Status.choices, required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, data):
        if "start" in data and "end" in data and data["start"] > data["end"]:
            raise serializers.ValidationError({"end": "End must be on or after start."})
        return data


def project_rows(request):
    filters = ReportFilters(data=request.query_params)
    filters.is_valid(raise_exception=True)
    values = filters.validated_data
    projects = portfolio_projects(request.user)
    for field in ("project_id", "department", "status"):
        if field in values:
            projects = projects.filter(**{("pk" if field == "project_id" else field): values[field]})
    if "start" in values:
        projects = projects.filter(planned_end__gte=values["start"])
    if "end" in values:
        projects = projects.filter(planned_start__lte=values["end"])

    spend = (
        Expenditure.objects.filter(project_id=OuterRef("pk"))
        .order_by().values("project_id").annotate(total=Sum("amount")).values("total")
    )
    return with_progress(projects.annotate(recorded=Subquery(spend)))


def project_row(project):
    progress, source = project_progress(project)
    return {
        "id": str(project.pk), "title": project.title, "department": project.department,
        "status": project.status, "planned_end": project.planned_end,
        "progress": progress, "progress_source": source, "reporting_date": project.latest_reporting_date,
        **budget_summary(project, project.recorded or Decimal("0.00")),
    }


def report_chart_data(projects):
    counts = Counter()
    spending = defaultdict(lambda: {"budget": Decimal("0.00"), "recorded": Decimal("0.00")})
    groups = projects.order_by().values("status", "currency").annotate(
        project_count=Count("pk"), budget_total=Sum("approved_budget"), spend_total=Sum("recorded"),
    )
    for group in groups:
        counts[group["status"]] += group["project_count"]
        totals = spending[group["currency"]]
        totals["budget"] += group["budget_total"]
        totals["recorded"] += group["spend_total"] or Decimal("0.00")
    return {
        "status_counts": {value: counts[value] for value in Project.Status.values if counts[value]},
        "spending": {
            code: {key: str(value) for key, value in totals.items()}
            for code, totals in sorted(spending.items())
        },
    }


@api_view(["GET"])
def dashboard(request):
    today = timezone.localdate()
    my_work = WorkItem.objects.filter(
        project__in=visible_projects(request.user), project__archived_at__isnull=True,
        assignee=request.user, is_active=True, percent_complete__lt=100,
    ).values("id", "project_id", "project__title", "title", "planned_end", "percent_complete")[:20]
    projects = list(project_rows(request).filter(archived_at__isnull=True))
    flags, upcoming = dashboard_risks(projects, today)
    overdue_count = sum(flag["type"] == "overdue" for flag in flags)
    dismissed = set(RiskFeedback.objects.filter(
        user=request.user, dismissed=True, signature__in=[flag["signature"] for flag in flags],
    ).values_list("signature", flat=True))
    as_of = timezone.now()
    manageable = {str(project.pk) for project in projects if manages_project(request.user, project)}
    flags = [
        {**flag, "method": "rule", "generated_at": as_of, "can_respond": flag["project_id"] in manageable}
        for flag in flags if flag["signature"] not in dismissed
    ]

    spending = defaultdict(lambda: {"budget": Decimal("0.00"), "recorded": Decimal("0.00")})
    for project in projects:
        recorded = project.recorded or Decimal("0.00")
        spending[project.currency]["budget"] += project.approved_budget
        spending[project.currency]["recorded"] += recorded
    return Response({
        "as_of": as_of, "status_counts": dict(Counter(p.status for p in projects)),
        "project_count": len(projects), "overdue_count": overdue_count,
        "lookahead_days": settings.MILESTONE_LOOKAHEAD_DAYS,
        "at_risk_count": len({flag["project_id"] for flag in flags}),
        "spending": {code: {key: str(value) for key, value in amounts.items()} for code, amounts in spending.items()},
        "projects": [project_row(p) for p in projects[:10]],
        "upcoming": upcoming[:10], "flags": flags[:30],
        "my_work": list(my_work),
    })


class RiskResponseSerializer(serializers.Serializer):
    signature = serializers.RegexField(r"\A[0-9a-f]{64}\Z")
    reason = serializers.CharField(max_length=1000)
    dismiss = serializers.BooleanField(default=False)


@api_view(["POST"])
def risk_response(request, project_id):
    project = get_object_or_404(project_rows(request).filter(archived_at__isnull=True), pk=project_id)
    if not manages_project(request.user, project):
        raise PermissionDenied("Only the project manager can respond to this flag.")
    data = RiskResponseSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    response = data.validated_data
    flags, _ = dashboard_risks([project], timezone.localdate())
    flag = next((flag for flag in flags if flag["signature"] == response["signature"]), None)
    if flag is None:
        raise ValidationError({"detail": "This flag has changed. Refresh the dashboard."})
    RiskFeedback.objects.create(
        project=project, user=request.user, signature=flag["signature"], snapshot=flag,
        dismissed=response["dismiss"], reason=response["reason"],
    )
    return Response(status=204)


@api_view(["GET"])
def report(request):
    projects = project_rows(request)
    export = request.query_params.get("export")
    fields = ("title", "department", "status", "planned_end", "progress", "reporting_date",
              "currency", "approved_budget", "recorded_expenditure", "remaining", "variance",
              "progress_source")
    if export == "pdf":
        return pdf_report((project_row(project) for project in projects.iterator()), report_chart_data(projects))
    if export == "xlsx":
        return excel_report(fields, (project_row(project) for project in projects.iterator()))
    if export == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="project-portfolio.csv"'
        writer = csv.writer(response)
        writer.writerow(fields)
        for project in projects.iterator():
            row = project_row(project)
            for field in ("title", "department"):
                if row[field].lstrip().startswith(("=", "+", "-", "@")) or row[field].startswith(("\t", "\r", "\n")):
                    row[field] = "'" + row[field]
            writer.writerow([row[field] for field in fields])
        return response
    charts = report_chart_data(projects)
    return Response({
        "count": sum(charts["status_counts"].values()),
        "charts": charts,
        "results": [project_row(p) for p in projects[:200]],
    })

