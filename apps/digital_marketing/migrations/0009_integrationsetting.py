import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("digital_marketing", "0008_digitalmarketingjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="DigitalMarketingIntegrationSetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("meta_app_id", models.CharField(blank=True, max_length=255)),
                ("meta_app_secret", models.CharField(blank=True, max_length=255)),
                ("google_client_id", models.CharField(blank=True, max_length=255)),
                ("google_client_secret", models.CharField(blank=True, max_length=255)),
                ("linkedin_client_id", models.CharField(blank=True, max_length=255)),
                ("linkedin_client_secret", models.CharField(blank=True, max_length=255)),
                ("x_api_key", models.CharField(blank=True, max_length=255)),
                ("x_api_secret", models.CharField(blank=True, max_length=255)),
                ("webhook_secret", models.CharField(blank=True, max_length=255)),
                ("webhook_ip_allowlist", models.TextField(blank=True)),
                ("attribution_model", models.CharField(default="LAST_TOUCH", max_length=30)),
                ("enable_auto_publish", models.BooleanField(default=False)),
                ("enable_report_email", models.BooleanField(default=True)),
                ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "school",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dm_integration_setting",
                        to="schools.school",
                    ),
                ),
            ],
        ),
    ]
