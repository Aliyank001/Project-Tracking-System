import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("department", models.CharField(max_length=150)),
                ("planned_start", models.DateField()),
                ("planned_end", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("proposed", "Proposed"),
                            ("planned", "Planned"),
                            ("active", "Active"),
                            ("on_hold", "On hold"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="proposed",
                        max_length=12,
                    ),
                ),
                (
                    "approved_budget",
                    models.DecimalField(
                        decimal_places=2, max_digits=16,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "currency",
                    models.CharField(
                        max_length=3,
                        validators=[
                            django.core.validators.RegexValidator(
                                r"\A[A-Z]{3}\Z", "Use a three-letter uppercase currency code."
                            )
                        ],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owned_projects",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(planned_end__gte=models.F("planned_start")),
                        name="project_valid_dates",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(approved_budget__gte=0),
                        name="project_nonnegative_budget",
                    ),
                ],
            },
        )
    ]
