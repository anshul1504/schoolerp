import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("digital_marketing", "0005_socialpost_review_audit_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="DigitalMarketingReportSchedule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                (
                    "frequency",
                    models.CharField(
                        choices=[("DAILY", "Daily"), ("WEEKLY", "Weekly"), ("MONTHLY", "Monthly")],
                        default="WEEKLY",
                        max_length=20,
                    ),
                ),
                ("delivery_email", models.EmailField(max_length=254)),
                ("is_active", models.BooleanField(default=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dm_report_schedules",
                        to="schools.school",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="DigitalMarketingReportRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("status", models.CharField(default="SUCCESS", max_length=20)),
                ("message", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="digital_marketing.digitalmarketingreportschedule",
                    ),
                ),
            ],
        ),
    ]
