import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0018_alter_subscriptioninvoice_options_and_more"),
        ("students", "0018_phase1_student_workflow_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentCommunicationLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("CALL", "Call"),
                            ("SMS", "SMS"),
                            ("EMAIL", "Email"),
                            ("WHATSAPP", "WhatsApp"),
                            ("MEETING", "Meeting"),
                            ("NOTE", "Internal Note"),
                        ],
                        default="NOTE",
                        max_length=20,
                    ),
                ),
                ("subject", models.CharField(blank=True, max_length=150)),
                ("message", models.TextField(blank=True)),
                ("logged_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_communication_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_communication_logs",
                        to="schools.school",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="communication_logs",
                        to="students.student",
                    ),
                ),
            ],
            options={"ordering": ["-logged_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="StudentComplianceReminder",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("reminder_type", models.CharField(max_length=100)),
                ("due_date", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "Pending"), ("SENT", "Sent"), ("DONE", "Done")],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_compliance_reminders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_compliance_reminders",
                        to="schools.school",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compliance_reminders",
                        to="students.student",
                    ),
                ),
            ],
            options={"ordering": ["status", "due_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="StudentDisciplineIncident",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True)),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("CRITICAL", "Critical"),
                        ],
                        default="LOW",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("OPEN", "Open"), ("RESOLVED", "Resolved"), ("CLOSED", "Closed")],
                        default="OPEN",
                        max_length=20,
                    ),
                ),
                ("incident_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "reported_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reported_student_discipline_incidents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_discipline_incidents",
                        to="schools.school",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discipline_incidents",
                        to="students.student",
                    ),
                ),
            ],
            options={"ordering": ["-incident_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="StudentHealthRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "record_type",
                    models.CharField(
                        choices=[
                            ("CHECKUP", "Checkup"),
                            ("VACCINATION", "Vaccination"),
                            ("ALERT", "Health Alert"),
                            ("SICK_LEAVE", "Sick Leave"),
                        ],
                        default="CHECKUP",
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=150)),
                ("notes", models.TextField(blank=True)),
                ("record_date", models.DateField(blank=True, null=True)),
                ("next_due_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_health_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_health_records",
                        to="schools.school",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_records",
                        to="students.student",
                    ),
                ),
            ],
            options={"ordering": ["-record_date", "-created_at"]},
        ),
    ]
