from django.conf import settings
from django.db import models

from apps.schools.models import School


class Notice(models.Model):
    AUDIENCE_CHOICES = (
        ("ALL", "All"),
        ("STAFF", "Staff"),
        ("STUDENTS", "Students"),
        ("PARENTS", "Parents"),
    )
    PRIORITY_CHOICES = (
        ("NORMAL", "Normal"),
        ("IMPORTANT", "Important"),
        ("URGENT", "Urgent"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="notices")
    title = models.CharField(max_length=150)
    body = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="ALL")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="NORMAL")
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notices",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
