from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0018_alter_subscriptioninvoice_options_and_more"),
        ("students", "0017_backfill_guardians"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionWorkflowEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage", models.CharField(choices=[("INQUIRY", "Inquiry"), ("FORM_SUBMITTED", "Form Submitted"), ("DOCUMENT_VERIFICATION", "Document Verification"), ("APPROVAL", "Approval"), ("FEE_COLLECTION", "Fee Collection"), ("ENROLLED", "Enrolled")], max_length=40)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("IN_PROGRESS", "In Progress"), ("DONE", "Done"), ("REJECTED", "Rejected")], default="PENDING", max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admission_workflow_events", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="admission_workflow_events", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="admission_workflow_events", to="students.student")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StudentProfileEditHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("changed_fields", models.JSONField(blank=True, default=list)),
                ("summary", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_profile_edit_history", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_profile_edit_history", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="profile_edit_history", to="students.student")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StudentClassChangeHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_class", models.CharField(max_length=100)),
                ("from_section", models.CharField(max_length=50)),
                ("to_class", models.CharField(max_length=100)),
                ("to_section", models.CharField(max_length=50)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("source", models.CharField(choices=[("PROMOTION", "Promotion"), ("MANUAL", "Manual Update")], default="MANUAL", max_length=20)),
                ("changed_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_class_change_history", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_class_change_history", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="class_change_history", to="students.student")),
            ],
            options={"ordering": ["-changed_on", "-created_at"]},
        ),
        migrations.CreateModel(
            name="TransferCertificateRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField(blank=True)),
                ("destination_school", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("CLOSED", "Closed")], default="PENDING", max_length=20)),
                ("review_note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_tc_requests", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_tc_requests", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tc_requests", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tc_requests", to="students.student")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
