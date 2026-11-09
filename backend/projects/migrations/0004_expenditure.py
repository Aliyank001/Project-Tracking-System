import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0003_workitem_progressupdate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Expenditure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=16, validators=[django.core.validators.MinValueValidator(0)])),
                ("category", models.CharField(max_length=100)),
                ("reference", models.CharField(max_length=100)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("entered_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.project")),
            ],
            options={
                "ordering": ["-date", "-id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(amount__gte=0), name="expenditure_nonnegative")
                ],
            },
        ),
    ]

