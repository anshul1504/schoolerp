from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("digital_marketing", "0003_socialconnectiontestlog_socialpublishrun"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialpost",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("IN_REVIEW", "In Review"),
                    ("APPROVED", "Approved"),
                    ("SCHEDULED", "Scheduled"),
                    ("PUBLISHED", "Published"),
                    ("FAILED", "Failed"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
    ]
