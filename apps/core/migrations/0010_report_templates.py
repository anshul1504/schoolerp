from django.db import migrations, models
from django.db.models import JSONField


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_auth_security_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=140)),
                (
                    "dataset",
                    models.CharField(
                        choices=[
                            ("SCHOOLS", "Schools"),
                            ("USERS", "Users"),
                            ("ACTIVITY", "Activity Log"),
                            ("STUDENTS", "Students"),
                            ("FEES_PAYMENTS", "Fee Payments"),
                            ("FEES_LEDGER", "Fee Ledgers"),
                        ],
                        max_length=30,
                    ),
                ),
                ("filters", JSONField(blank=True, default=dict)),
                ("columns", JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
            },
        ),
    ]

