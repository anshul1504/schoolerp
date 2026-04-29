from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("digital_marketing", "0006_reportschedule_and_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="websiteformintegration",
            name="field_mapping",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
