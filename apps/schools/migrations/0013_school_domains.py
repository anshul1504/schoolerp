from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0012_campus"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolDomain",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "domain",
                    models.CharField(
                        help_text="Example: erp.yourschool.com", max_length=190, unique=True
                    ),
                ),
                ("is_primary", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="domains",
                        to="schools.school",
                    ),
                ),
            ],
            options={
                "ordering": ["-is_primary", "domain", "id"],
            },
        ),
    ]
