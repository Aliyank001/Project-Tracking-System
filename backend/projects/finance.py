from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from django.db import transaction

from .access import can_view_portfolio
from .models import Expenditure
from .tracking_views import ProjectTrackingMixin
from .views import ProjectPagination


def budget_summary(project, recorded):
    baseline = project.approved_budget
    return {
        "currency": project.currency,
        "approved_budget": str(baseline),
        "recorded_expenditure": str(recorded),
        "remaining": str(baseline - recorded),
        "variance": str(recorded - baseline),
    }


class ExpenditureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expenditure
        fields = ("id", "date", "amount", "category", "reference", "note", "entered_by", "created_at")
        read_only_fields = ("entered_by", "created_at")


class ExpenditureView(ProjectTrackingMixin, ListCreateAPIView):
    serializer_class = ExpenditureSerializer
    pagination_class = ProjectPagination

    def get_queryset(self):
        if not can_view_portfolio(self.request.user, self.project):
            raise PermissionDenied("You do not have access to this project's budget.")
        return Expenditure.objects.filter(project=self.project)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        total = self.get_queryset().aggregate(total=Sum("amount"))["total"]
        response.data["summary"] = budget_summary(self.project, total or Decimal("0.00"))
        response.data["can_record"] = self.can_record()
        return response

    def can_record(self):
        user = self.request.user
        return not self.project.archived_at and user.has_perm("projects.add_expenditure") and (
            user.is_superuser or self.project.owner_id == user.pk
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not self.can_record():
            raise PermissionDenied("You do not have permission to record expenditure.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        entry = serializer.save(project=self.project, entered_by=self.request.user)
        self.audit("expenditure_added", {"entry_id": entry.pk, "amount": str(entry.amount)})

