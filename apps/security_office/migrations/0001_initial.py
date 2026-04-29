import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("schools", "0020_seed_advanced_erp_features"),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityIncident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("incident_type", models.CharField(blank=True, max_length=80)),
                ("severity", models.CharField(choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], default="LOW", max_length=20)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("INVESTIGATING", "Investigating"), ("RESOLVED", "Resolved"), ("CLOSED", "Closed")], default="OPEN", max_length=20)),
                ("location", models.CharField(blank=True, max_length=140)),
                ("description", models.TextField(blank=True)),
                ("reported_at", models.DateTimeField()),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_incidents", to="schools.school")),
            ],
            options={"ordering": ["-reported_at", "-id"]},
        ),
        migrations.CreateModel(
            name="VisitorEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=140)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("purpose", models.CharField(blank=True, max_length=160)),
                ("person_to_meet", models.CharField(blank=True, max_length=140)),
                ("check_in_at", models.DateTimeField()),
                ("check_out_at", models.DateTimeField(blank=True, null=True)),
                ("is_verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="visitor_entries", to="schools.school")),
            ],
            options={"ordering": ["-check_in_at", "-id"]},
        ),
    ]
