from django.core.validators import URLValidator
from rest_framework import serializers

from .access import can_view_portfolio
from .models import ProgressEvidence, ProgressReview, ProgressUpdate, ProjectAccess, WorkItem


class WorkItemSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = WorkItem
        fields = (
            "id", "kind", "title", "assignee", "planned_start", "planned_end",
            "predecessor", "percent_complete", "status", "acceptance_note", "is_active", "weight",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        view = self.context["view"]
        user = view.request.user
        if instance.predecessor_id and not can_view_portfolio(user, view.project):
            if instance.predecessor.assignee_id != user.pk:
                data["predecessor"] = None
        return data

    def get_status(self, item):
        if not item.is_active:
            return "inactive"
        if item.percent_complete == 100:
            return "completed"
        if item.percent_complete:
            return "in_progress"
        return "pending"

    def validate_assignee(self, user):
        if user is None:
            return None
        if self.instance and self.instance.assignee_id == user.pk:
            return user
        project = self.context["view"].project
        if not user.is_active or (
            user.pk != project.owner_id and not (
                user.has_perm("projects.view_project")
                and ProjectAccess.objects.filter(project=project, user=user).exists()
            )
        ):
            raise serializers.ValidationError("Choose an active user with access to this project.")
        return user

    def validate_predecessor(self, predecessor):
        if predecessor is None:
            return None
        if predecessor.project_id != self.context["view"].project.pk:
            raise serializers.ValidationError("Choose a predecessor from this project.")
        if self.instance:
            links = dict(
                WorkItem.objects.filter(project_id=predecessor.project_id)
                .values_list("pk", "predecessor_id")
            )
            seen = {self.instance.pk}
            current = predecessor.pk
            while current is not None:
                if current in seen:
                    raise serializers.ValidationError("This dependency would create a cycle.")
                seen.add(current)
                current = links.get(current)
        return predecessor

    def validate(self, data):
        start = data.get("planned_start", getattr(self.instance, "planned_start", None))
        end = data.get("planned_end", getattr(self.instance, "planned_end", None))
        if end < start:
            raise serializers.ValidationError(
                {"planned_end": "The end date must be on or after the start date."}
            )
        return data


class ProgressReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgressReview
        fields = ("decision", "comment", "reviewer", "created_at")
        read_only_fields = ("reviewer", "created_at")
        extra_kwargs = {"comment": {"max_length": 4000}}

    def validate(self, data):
        if data["decision"] == ProgressReview.Decision.CORRECTION and not data.get("comment"):
            raise serializers.ValidationError({"comment": "Explain what needs correction."})
        return data


class ProgressUpdateSerializer(serializers.ModelSerializer):
    evidence_file = serializers.FileField(write_only=True, required=False, max_length=255)
    evidence_name = serializers.CharField(source="evidence.filename", read_only=True, default=None)
    evidence_url = serializers.CharField(
        max_length=500, required=False, allow_blank=True,
        validators=[URLValidator(schemes=["http", "https"])],
    )
    review = ProgressReviewSerializer(read_only=True)
    replaced = serializers.SerializerMethodField()

    class Meta:
        model = ProgressUpdate
        fields = (
            "id", "author", "reporting_date", "percent_complete", "summary",
            "blockers", "next_steps", "submitted_at", "evidence_url", "evidence_file",
            "evidence_name", "review", "replaces", "replaced",
        )
        read_only_fields = ("author", "submitted_at", "replaces")

    def get_replaced(self, update):
        return hasattr(update, "replacement")

    def validate_evidence_file(self, file):
        signatures = {
            "pdf": b"%PDF-",
            "png": b"\x89PNG\r\n\x1a\n",
            "jpg": b"\xff\xd8\xff",
            "jpeg": b"\xff\xd8\xff",
        }
        signature = signatures.get(file.name.rsplit(".", 1)[-1].lower())
        if file.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File must be 5 MB or smaller.")
        if signature is None or file.read(len(signature)) != signature:
            raise serializers.ValidationError("Upload a PDF, PNG or JPEG file.")
        file.seek(0)
        return file

    def create(self, validated_data):
        file = validated_data.pop("evidence_file", None)
        update = super().create(validated_data)
        if file:
            ProgressEvidence.objects.create(update=update, filename=file.name, content=file.read())
        return update
