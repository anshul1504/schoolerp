from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0011_schoolcommunicationsettings"),
        ("academics", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicYear",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Example: 2026-2027", max_length=40)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_current", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "school",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_years", to="schools.school"),
                ),
            ],
            options={
                "ordering": ["-start_date"],
                "unique_together": {("school", "name")},
            },
        ),
    ]

