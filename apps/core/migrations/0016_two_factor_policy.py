from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_rbac_change_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="TwoFactorPolicy",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("require_for_roles", models.JSONField(blank=True, default=list)),
                ("require_for_user_ids", models.JSONField(blank=True, default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
    ]

