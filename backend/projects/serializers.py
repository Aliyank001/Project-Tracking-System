from rest_framework import serializers

from .access import can_view_portfolio
from .models import Project, ProjectAuditEvent, ProjectStatusSetting
from .progress import project_progress, with_progress


class ProjectSerializer(serializers.ModelSerializer):
    budget_revision_reason = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=1000)
    progress_summary = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "title",
            "description",
            "department",
            "owner",
            "planned_start",
            "planned_end",
            "status",
            "approved_budget",
            "currency",
            "created_at",
            "archived_at",
            "budget_revision_reason",
            "progress_summary",
        )
        read_only_fields = ("id", "owner", "created_at", "archived_at")

    def get_progress_summary(self, project):
        if not hasattr(project, "total_weight"):
            project = with_progress(Project.objects.filter(pk=project.pk)).get()
        value, source = project_progress(project)
        return {"percent": value, "source": source}

    def to_representation(self, instance):
        user = self.context["request"].user
        if can_view_portfolio(user, instance):
            return super().to_representation(instance)
        return {
            field: self.fields[field].to_representation(getattr(instance, field))
            for field in ("id", "title", "description", "department", "planned_start",
                          "planned_end", "status", "archived_at")
            if getattr(instance, field) is not None
        }

    def validate(self, data):
        current_status = self.instance.status if self.instance else None
        new_status = data.get("status", current_status or Project.Status.PROPOSED)
        if new_status != current_status and ProjectStatusSetting.objects.filter(
            status=new_status, enabled=False
        ).exists():
            raise serializers.ValidationError({"status": "This status is disabled for new assignments."})
        start = data.get("planned_start", getattr(self.instance, "planned_start", None))
        end = data.get("planned_end", getattr(self.instance, "planned_end", None))
        if end < start:
            raise serializers.ValidationError(
                {"planned_end": "The end date must be on or after the start date."}
            )
        if self.instance and "currency" in data and data["currency"] != self.instance.currency:
            if self.instance.expenditure_set.exists():
                raise serializers.ValidationError(
                    {"currency": "Currency cannot change after expenditure is recorded."}
                )
        if self.instance and (
            data.get("approved_budget", self.instance.approved_budget) != self.instance.approved_budget
            or data.get("currency", self.instance.currency) != self.instance.currency
        ) and not data.get("budget_revision_reason"):
            raise serializers.ValidationError({"budget_revision_reason": "Enter a reason for the budget revision."})
        return data

    def create(self, validated_data):
        validated_data.pop("budget_revision_reason", None)
        return super().create(validated_data)


class ProjectAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectAuditEvent
        fields = ("id", "project", "actor", "action", "changes", "created_at")


class ProjectRegisterFilters(serializers.Serializer):
    project_id = serializers.UUIDField(required=False)
    owner = serializers.CharField(max_length=150, required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    archived = serializers.BooleanField(default=False)

    def validate(self, data):
        if "start" in data and "end" in data and data["start"] > data["end"]:
            raise serializers.ValidationError({"end": "End must be on or after start."})
        return data


class ProjectArchiveSerializer(serializers.Serializer):
    archived = serializers.BooleanField(default=True)


class ProjectCreateSerializer(ProjectSerializer):
    manager_id = serializers.IntegerField(write_only=True, required=False, min_value=1)

    class Meta(ProjectSerializer.Meta):
        fields = (*ProjectSerializer.Meta.fields, "manager_id")
