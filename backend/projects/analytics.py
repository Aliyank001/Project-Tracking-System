import json
from datetime import timedelta
from decimal import Decimal
from functools import lru_cache

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Expenditure, ProgressUpdate, WorkItem
from .train_forecast import DATA_DIR, predict, sigmoid
from .access import portfolio_projects


class ScenarioInputs(serializers.Serializer):
    budget_cut = serializers.IntegerField(min_value=0, max_value=100, default=0)
    extra_days = serializers.IntegerField(min_value=0, max_value=365, default=0)
    price_increase = serializers.IntegerField(min_value=0, max_value=100, default=0)
    resource_loss = serializers.IntegerField(min_value=0, max_value=90, default=0)


def money(value):
    return str(value.quantize(Decimal("0.01")))


def scenarios(project, recorded, estimated_cost, late_days, inputs, today):
    output = []
    for name, factor in (("best", Decimal("0.5")), ("base", Decimal(1)), ("worst", Decimal("1.5"))):
        budget_cut = min(Decimal(100), inputs["budget_cut"] * factor) / 100
        price = inputs["price_increase"] * factor / 100
        loss = min(Decimal(90), inputs["resource_loss"] * factor) / 100
        remaining_work = max(0, (project.planned_end - today).days)
        resource_days = round(remaining_work * loss / (1 - loss))
        cost = recorded + max(Decimal(0), estimated_cost - recorded) * (1 + price)
        budget = project.approved_budget * (1 - budget_cut)
        delay = late_days + round(inputs["extra_days"] * factor) + resource_days
        output.append({
            "case": name, "budget": money(budget), "estimated_cost": money(cost),
            "budget_gap": money(budget - cost), "extra_days": delay,
            "finish_date": project.planned_end + timedelta(days=delay),
        })
    return output


@lru_cache(maxsize=1)
def model_data():
    return json.loads((DATA_DIR / "model.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def forest_evaluation():
    path = DATA_DIR / "forest_evaluation.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@api_view(["GET"])
def analytics(request, project_id):
    project = get_object_or_404(portfolio_projects(request.user), pk=project_id)
    inputs = ScenarioInputs(data=request.query_params)
    inputs.is_valid(raise_exception=True)
    today = timezone.localdate()
    budget = project.approved_budget
    milestones = list(WorkItem.objects.filter(project=project, kind="milestone", is_active=True))
    latest = ProgressUpdate.objects.filter(project=project, reporting_date__lte=today).first()
    recorded = Expenditure.objects.filter(project=project, date__lte=today).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")
    evm = {"method": "Equal shares of approved budget per active milestone; spending recorded through today."}
    estimate = max(budget, recorded)
    forecast = {"status": "insufficient_data"}
    late_days = 0
    if milestones and budget > 0:
        pv = budget * sum(item.planned_end <= today for item in milestones) / len(milestones)
        ev = budget * sum(item.percent_complete for item in milestones) / (100 * len(milestones))
        cpi = ev / recorded if recorded else None
        spi = ev / pv if pv else None
        evm.update({
            "pv": money(pv), "ev": money(ev), "ac": money(recorded),
            "spi": round(spi, 3) if spi is not None else None, "cpi": round(cpi, 3) if cpi is not None else None,
            "schedule_status": ("behind plan" if spi < 1 else "on or ahead of plan") if spi is not None else None,
            "cost_status": ("over earned value" if cpi < 1 else "within earned value") if cpi is not None else None,
            "eac": money(budget / cpi) if cpi else None,
        })
        if cpi:
            estimate = max(recorded, budget / cpi)
        if latest and project.planned_start <= today and project.status not in ("completed", "cancelled"):
            try:
                model = model_data()
            except FileNotFoundError:
                model = None
            if model:
                duration = max(1, (project.planned_end - project.planned_start).days)
                overdue = sum(item.planned_end < today and item.percent_complete < 100 for item in milestones)
                features = [
                    min(1, (today - project.planned_start).days / duration),
                    latest.percent_complete / 100,
                    min(1.5, float(recorded / budget)),
                    overdue / len(milestones),
                ]
                late_days = max(0, round(100 * predict(model["days"], features)))
                estimate = max(recorded, budget * Decimal(str(predict(model["cost"], features))))
                forecast = {
                    "status": "available", "method": model["version"], "data_date": latest.reporting_date,
                    "delay_probability": round(sigmoid(predict(model["delay"], features)), 3),
                    "days_late": late_days, "final_cost": money(estimate), "evaluation": model["metrics"],
                    "limitation": "Trained and evaluated on synthetic records for coursework only.",
                    "inputs": dict(zip(model["features"], features)),
                }
    return Response({
        "as_of": timezone.now(), "currency": project.currency, "evm": evm, "forecast": forecast,
        "scenario_basis": "Best, base and worst apply 50%, 100% and 150% of the input shocks. Price affects only unspent work. Resource loss extends remaining duration.",
        "scenarios": scenarios(project, recorded, estimate, late_days, inputs.validated_data, today),
        "forest_evaluation": forest_evaluation(),
    })

