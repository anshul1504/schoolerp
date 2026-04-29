from django.db import models

from apps.schools.models import School
from apps.staff.models import StaffMember


class ResearchProject(models.Model):
    STATUS_CHOICES = (
        ("PROPOSED", "Proposed"),
        ("ONGOING", "Ongoing"),
        ("COMPLETED", "Completed"),
        ("SUSPENDED", "Suspended"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="research_projects")
    title = models.CharField(max_length=255)
    description = models.TextField()
    pi = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, related_name="led_projects", verbose_name="Principal Investigator")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PROPOSED")
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

class Grant(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("DISBURSED", "Disbursed"),
    )
    project = models.ForeignKey(ResearchProject, on_delete=models.CASCADE, related_name="grants")
    grant_id = models.CharField(max_length=100, blank=True, verbose_name="Grant ID/Reference")
    agency = models.CharField(max_length=255, verbose_name="Funding Agency")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    received_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.agency} - {self.amount}"

class ResearchPaper(models.Model):
    project = models.ForeignKey(ResearchProject, on_delete=models.SET_NULL, null=True, blank=True, related_name="papers")
    title = models.CharField(max_length=255)
    journal = models.CharField(max_length=255)
    publication_date = models.DateField()
    doi = models.CharField(max_length=100, blank=True, verbose_name="DOI")
    link = models.URLField(blank=True)

    def __str__(self):
        return self.title

class EthicsReview(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )
    project = models.OneToOneField(ResearchProject, on_delete=models.CASCADE, related_name="ethics_review")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    comments = models.TextField(blank=True)
    reviewer = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, related_name="reviewed_ethics")
    reviewed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for {self.project.title}"
