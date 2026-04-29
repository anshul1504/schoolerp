from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_scheduled_reports"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledReportRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                            ("SKIPPED", "Skipped"),
                        ],
                        max_length=20,
                    ),
                ),
                ("recipients", models.TextField(blank=True)),
                ("filename", models.CharField(blank=True, max_length=120)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="runs",
                        to="core.scheduledreport",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
