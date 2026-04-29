from django.db import models

from apps.schools.models import School


class CompliancePolicy(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("REVIEW_NEEDED", "Review Needed"),
        ("RETIRED", "Retired"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="compliance_policies")
    title = models.CharField(max_length=255)
    category = models.CharField(
        max_length=100, help_text="e.g., Safety, Academic, HR, Data Protection"
    )
    description = models.TextField()
    effective_date = models.DateField()
    review_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ComplianceInspection(models.Model):
    STATUS_CHOICES = (
        ("SCHEDULED", "Scheduled"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    )

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="compliance_inspections"
    )
    title = models.CharField(max_length=255)
    inspection_date = models.DateField()
    inspector_name = models.CharField(max_length=150)
    related_policy = models.ForeignKey(
        CompliancePolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspections",
    )
    findings = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SCHEDULED")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.inspection_date}"


class SchoolCertification(models.Model):
    STATUS_CHOICES = (
        ("VALID", "Valid"),
        ("EXPIRING_SOON", "Expiring Soon"),
        ("EXPIRED", "Expired"),
        ("REVOKED", "Revoked"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="certifications")
    name = models.CharField(max_length=255)
    issuing_authority = models.CharField(max_length=255)
    issue_date = models.DateField()
    expiry_date = models.DateField()
    certificate_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="VALID")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
