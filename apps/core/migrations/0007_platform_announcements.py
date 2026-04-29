from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_scheduled_report_runs"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformAnnouncement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=120)),
                ("message", models.TextField()),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("INFO", "Info"),
                            ("WARNING", "Warning"),
                            ("DANGER", "Danger"),
                            ("SUCCESS", "Success"),
                        ],
                        default="INFO",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
