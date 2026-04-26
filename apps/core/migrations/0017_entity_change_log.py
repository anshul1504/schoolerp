from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0016_two_factor_policy"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EntityChangeLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entity", models.CharField(max_length=80)),
                ("object_id", models.CharField(max_length=64)),
                ("action", models.CharField(max_length=20)),
                ("changes", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="entity_change_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="entitychangelog",
            index=models.Index(fields=["entity", "object_id"], name="core_entity_entity_3f0f6d_idx"),
        ),
        migrations.AddIndex(
            model_name="entitychangelog",
            index=models.Index(fields=["created_at"], name="core_entity_created_9df0b2_idx"),
        ),
    ]

