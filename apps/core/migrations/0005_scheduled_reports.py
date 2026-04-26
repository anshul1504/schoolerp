from django.db import migrations, models
from django.db.models import JSONField


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_platform_branding_tokens"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("report_type", models.CharField(choices=[("INVOICES", "Billing Invoices (CSV)"), ("ACTIVITY", "Activity Log (CSV)"), ("STUDENTS", "Students Export (CSV)")], max_length=20)),
                ("frequency", models.CharField(choices=[("DAILY", "Daily"), ("WEEKLY", "Weekly"), ("MONTHLY", "Monthly")], default="WEEKLY", max_length=20)),
                ("recipients", models.TextField(help_text="Comma-separated emails")),
                ("filters", JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]

