from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0013_school_domains"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionCoupon",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("code", models.CharField(max_length=40, unique=True)),
                (
                    "discount_type",
                    models.CharField(
                        choices=[("PERCENT", "Percent"), ("FIXED", "Fixed amount")],
                        default="PERCENT",
                        max_length=20,
                    ),
                ),
                ("value", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("is_active", models.BooleanField(default=True)),
                ("starts_on", models.DateField(blank=True, null=True)),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("max_uses", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("used_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at", "code"],
            },
        ),
    ]
