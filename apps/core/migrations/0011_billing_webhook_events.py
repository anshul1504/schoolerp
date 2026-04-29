from django.db import migrations, models
from django.db.models import JSONField


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_report_templates"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingWebhookEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("provider", models.CharField(default="GENERIC", max_length=40)),
                ("event_id", models.CharField(max_length=120, unique=True)),
                ("event_type", models.CharField(blank=True, max_length=80)),
                ("invoice_id", models.IntegerField(blank=True, null=True)),
                ("status", models.CharField(blank=True, max_length=40)),
                ("payload", JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("process_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
