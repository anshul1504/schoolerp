import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("digital_marketing", "0007_websiteintegration_field_mapping"),
    ]

    operations = [
        migrations.CreateModel(
            name="DigitalMarketingJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "job_type",
                    models.CharField(
                        choices=[
                            ("PUBLISH_POST", "Publish Post"),
                            ("INGEST_LEAD", "Ingest Lead"),
                            ("SEND_REPORT", "Send Report"),
                        ],
                        max_length=30,
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("QUEUED", "Queued"),
                            ("RUNNING", "Running"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                            ("DEAD_LETTER", "Dead Letter"),
                        ],
                        default="QUEUED",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("max_attempts", models.PositiveIntegerField(default=3)),
                ("last_error", models.CharField(blank=True, max_length=255)),
                ("run_at", models.DateTimeField(default=django.db.models.functions.datetime.Now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dm_jobs",
                        to="schools.school",
                    ),
                ),
            ],
        ),
    ]
