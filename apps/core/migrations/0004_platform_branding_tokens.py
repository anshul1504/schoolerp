from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_role_permissions_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="favicon",
            field=models.ImageField(blank=True, null=True, upload_to="platform/"),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="theme_primary",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="theme_secondary",
            field=models.CharField(blank=True, max_length=16),
        ),
    ]
