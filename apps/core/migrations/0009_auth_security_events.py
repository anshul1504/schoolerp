from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_support_ticketing"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthSecurityEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "event",
                    models.CharField(
                        choices=[
                            ("LOGIN_SUCCESS", "Login success"),
                            ("LOGIN_FAIL", "Login failed"),
                            ("LOGIN_LOCKED", "Login locked"),
                            ("OTP_SENT", "OTP sent"),
                            ("OTP_VERIFY_SUCCESS", "OTP verified"),
                            ("OTP_VERIFY_FAIL", "OTP verify failed"),
                            ("THROTTLED", "Throttled"),
                        ],
                        max_length=30,
                    ),
                ),
                ("username", models.CharField(blank=True, max_length=150)),
                ("ip_address", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.TextField(blank=True)),
                ("user_id", models.IntegerField(blank=True, null=True)),
                ("success", models.BooleanField(default=False)),
                ("details", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
