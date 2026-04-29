import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0011_schoolcommunicationsettings"),
        ("academics", "0002_academicyear"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClassMaster",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="class_masters",
                        to="schools.school",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("school", "name")},
            },
        ),
        migrations.CreateModel(
            name="SectionMaster",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="section_masters",
                        to="schools.school",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("school", "name")},
            },
        ),
    ]
