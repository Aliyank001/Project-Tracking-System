import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_project_access_and_audit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("task", "Task"), ("milestone", "Milestone")], max_length=9)),
                ("title", models.CharField(max_length=200)),
                ("planned_start", models.DateField()),
                ("planned_end", models.DateField()),
                ("percent_complete", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100)])),
                ("acceptance_note", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("assignee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("predecessor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="projects.workitem")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.project")),
            ],
            options={
                "ordering": ["planned_end", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(planned_end__gte=models.F("planned_start")),
                        name="work_item_valid_dates",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(percent_complete__gte=0, percent_complete__lte=100),
                        name="work_item_valid_progress",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProgressUpdate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reporting_date", models.DateField()),
                ("percent_complete", models.PositiveSmallIntegerField(validators=[django.core.validators.MaxValueValidator(100)])),
                ("summary", models.TextField()),
                ("blockers", models.TextField(blank=True)),
                ("next_steps", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.project")),
            ],
            options={
                "ordering": ["-reporting_date", "-submitted_at", "-id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(percent_complete__gte=0, percent_complete__lte=100),
                        name="progress_update_valid_percent",
                    ),
                ],
            },
        ),
    ]
