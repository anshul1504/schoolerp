# Generated manually (project prioritizes rapid development).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("academics", "0003_classmaster_sectionmaster"),
        ("schools", "0001_initial"),
        ("frontoffice", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionApplication",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("SUBMITTED", "Submitted"),
                            ("DOCUMENTS_PENDING", "Documents Pending"),
                            ("UNDER_REVIEW", "Under Review"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                            ("ADMITTED", "Admitted"),
                            ("CLOSED", "Closed"),
                        ],
                        default="DRAFT",
                        max_length=30,
                    ),
                ),
                ("application_no", models.CharField(blank=True, max_length=50)),
                ("student_name", models.CharField(max_length=150)),
                ("guardian_name", models.CharField(blank=True, max_length=150)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("address", models.TextField(blank=True)),
                ("previous_school", models.CharField(blank=True, max_length=255)),
                ("desired_class_text", models.CharField(blank=True, max_length=120)),
                ("desired_section_text", models.CharField(blank=True, max_length=60)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_year",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admission_applications",
                        to="academics.academicyear",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_admissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "desired_class_master",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admission_applications",
                        to="academics.classmaster",
                    ),
                ),
                (
                    "desired_section_master",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admission_applications",
                        to="academics.sectionmaster",
                    ),
                ),
                (
                    "enquiry",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admission_application",
                        to="frontoffice.enquiry",
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admission_applications",
                        to="schools.school",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_admissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AdmissionEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("UPDATED", "Updated"),
                            ("STATUS_CHANGED", "Status Changed"),
                            ("DOCUMENT_RECEIVED", "Document Received"),
                            ("STUDENT_CREATED", "Student Created"),
                        ],
                        max_length=40,
                    ),
                ),
                ("message", models.CharField(blank=True, max_length=255)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admission_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="admissions.admissionapplication",
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admission_events",
                        to="schools.school",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AdmissionDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=150)),
                (
                    "document",
                    models.FileField(blank=True, null=True, upload_to="admissions/documents/"),
                ),
                ("is_received", models.BooleanField(default=False)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=255)),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="admissions.admissionapplication",
                    ),
                ),
            ],
            options={"ordering": ["title", "id"]},
        ),
        migrations.AddConstraint(
            model_name="admissionapplication",
            constraint=models.UniqueConstraint(
                fields=("school", "application_no"), name="uniq_admission_application_no_per_school"
            ),
        ),
    ]
