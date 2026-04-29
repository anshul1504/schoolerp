from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.academics.models import AcademicYear, ClassMaster, SectionMaster
from apps.schools.models import School


class AdmissionApplication(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("DOCUMENTS_PENDING", "Documents Pending"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("ADMITTED", "Admitted"),
        ("CLOSED", "Closed"),
    )

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="admission_applications"
    )
    enquiry = models.OneToOneField(
        "frontoffice.Enquiry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_application",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applications",
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="DRAFT")
    application_no = models.CharField(max_length=50, blank=True)

    student_name = models.CharField(max_length=150)
    guardian_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    previous_school = models.CharField(max_length=255, blank=True)

    desired_class_master = models.ForeignKey(
        ClassMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applications",
    )
    desired_class_text = models.CharField(max_length=120, blank=True)
    desired_section_master = models.ForeignKey(
        SectionMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applications",
    )
    desired_section_text = models.CharField(max_length=60, blank=True)

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_admissions",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_admissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "application_no"], name="uniq_admission_application_no_per_school"
            ),
        ]

    def __str__(self):
        return f"{self.application_no or 'APP'} - {self.student_name}"

    @property
    def desired_class_label(self):
        if self.desired_class_master_id:
            return self.desired_class_master.name
        return self.desired_class_text

    @property
    def desired_section_label(self):
        if self.desired_section_master_id:
            return self.desired_section_master.name
        return self.desired_section_text

    def save(self, *args, **kwargs):
        if not self.application_no:
            today = timezone.localdate()
            year = today.year
            prefix = f"APP/{year}/"
            last = (
                AdmissionApplication.objects.filter(
                    school=self.school, application_no__startswith=prefix
                )
                .order_by("-id")
                .first()
            )
            next_number = 1
            if last and last.application_no:
                try:
                    next_number = int(last.application_no.split("/")[-1]) + 1
                except Exception:
                    next_number = last.id + 1
            self.application_no = f"{prefix}{next_number:04d}"
        super().save(*args, **kwargs)


class AdmissionDocument(models.Model):
    application = models.ForeignKey(
        AdmissionApplication, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=150)
    document = models.FileField(upload_to="admissions/documents/", null=True, blank=True)
    is_received = models.BooleanField(default=False)
    received_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["title", "id"]

    def __str__(self):
        return f"{self.application_id} - {self.title}"


class AdmissionEvent(models.Model):
    ACTION_CHOICES = (
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("STATUS_CHANGED", "Status Changed"),
        ("DOCUMENT_RECEIVED", "Document Received"),
        ("STUDENT_CREATED", "Student Created"),
    )

    application = models.ForeignKey(
        AdmissionApplication, on_delete=models.CASCADE, related_name="events"
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="admission_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_events",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    message = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
