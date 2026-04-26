from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0019_phase2_student_ops_models"),
        ("core", "0022_inventorymovement_libraryissue"),
    ]

    operations = [
        migrations.CreateModel(
            name="HostelAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bed_label", models.CharField(blank=True, max_length=40)),
                ("active", models.BooleanField(default=True)),
                ("allocated_on", models.DateField(auto_now_add=True)),
                ("released_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="core.hostelroom")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hostel_allocations", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hostel_allocations", to="students.student")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "unique_together": {("room", "student", "active")},
            },
        ),
        migrations.CreateModel(
            name="TransportAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pickup_stop", models.CharField(blank=True, max_length=120)),
                ("active", models.BooleanField(default=True)),
                ("assigned_on", models.DateField(auto_now_add=True)),
                ("released_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("route", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="core.transportroute")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transport_assignments", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transport_assignments", to="students.student")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "unique_together": {("route", "student", "active")},
            },
        ),
    ]
