import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q


class Project(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=150)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_projects"
    )
    planned_start = models.DateField()
    planned_end = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROPOSED)
    approved_budget = models.DecimalField(
        max_digits=16, decimal_places=2, validators=[MinValueValidator(0)]
    )
    currency = models.CharField(
        max_length=3,
        validators=[RegexValidator(r"\A[A-Z]{3}\Z", "Use a three-letter uppercase currency code.")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(planned_end__gte=F("planned_start")), name="project_valid_dates"
            ),
            models.CheckConstraint(
                condition=Q(approved_budget__gte=0), name="project_nonnegative_budget"
            ),
        ]

    def __str__(self):
        return self.title


class ProjectAccess(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_access")
        ]


class ProjectAuditEvent(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=20)
    changes = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class WorkItem(models.Model):
    class Kind(models.TextChoices):
        TASK = "task", "Task"
        MILESTONE = "milestone", "Milestone"

    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    kind = models.CharField(max_length=9, choices=Kind.choices)
    title = models.CharField(max_length=200)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    planned_start = models.DateField()
    planned_end = models.DateField()
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True)
    percent_complete = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    weight = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    acceptance_note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["planned_end", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(planned_end__gte=F("planned_start")), name="work_item_valid_dates"
            ),
            models.CheckConstraint(
                condition=Q(percent_complete__gte=0, percent_complete__lte=100),
                name="work_item_valid_progress",
            ),
            models.CheckConstraint(
                condition=Q(weight__isnull=True) | Q(weight__gte=1, weight__lte=1000),
                name="work_item_valid_weight",
            ),
        ]


class ProgressUpdate(models.Model):
    replaces = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="replacement"
    )
    evidence_url = models.URLField(blank=True, max_length=500)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reporting_date = models.DateField()
    percent_complete = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    summary = models.TextField()
    blockers = models.TextField(blank=True)
    next_steps = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reporting_date", "-submitted_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(percent_complete__gte=0, percent_complete__lte=100),
                name="progress_update_valid_percent",
            ),
        ]


class ProgressEvidence(models.Model):
    update = models.OneToOneField(ProgressUpdate, on_delete=models.CASCADE, related_name="evidence")
    filename = models.CharField(max_length=255)
    content = models.BinaryField()


class ProgressReview(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        CORRECTION = "correction_requested", "Correction requested"

    update = models.OneToOneField(ProgressUpdate, on_delete=models.PROTECT, related_name="review")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20, choices=Decision.choices)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    class Kind(models.TextChoices):
        ASSIGNMENT = "assignment", "Task assignment"
        UPCOMING = "upcoming", "Upcoming milestone"
        OVERDUE = "overdue", "Overdue milestone"
        REVIEW = "review", "Review decision"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    message = models.CharField(max_length=300)
    deadline_key = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["recipient", "deadline_key"], name="unique_deadline_notice")
        ]
        indexes = [models.Index(fields=["recipient", "read_at"])]


class RiskFeedback(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    signature = models.CharField(max_length=64, db_index=True)
    dismissed = models.BooleanField(default=False)
    reason = models.CharField(max_length=1000)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class ProjectStatusSetting(models.Model):
    status = models.CharField(max_length=12, choices=Project.Status.choices, unique=True)
    label = models.CharField(max_length=50)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.label


class Expenditure(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    date = models.DateField()
    amount = models.DecimalField(
        max_digits=16, decimal_places=2, validators=[MinValueValidator(0)]
    )
    category = models.CharField(max_length=100)
    reference = models.CharField(max_length=100)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="expenditure_nonnegative")
        ]
