from django.db import models

from apps.schools.models import School
from apps.students.models import Student


class Alumni(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="alumni")
    student = models.OneToOneField(
        Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="alumni_profile"
    )

    # Personal Info (if student is not linked)
    full_name = models.CharField(max_length=255)
    graduation_year = models.PositiveIntegerField()
    batch = models.CharField(max_length=50, blank=True)  # e.g. 2018-2022

    # Career Info
    current_occupation = models.CharField(max_length=255, blank=True)
    current_organization = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)

    # Contact Info
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    linkedin_profile = models.URLField(blank=True)

    # Status
    is_verified = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Alumni"
        ordering = ["-graduation_year", "full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.graduation_year})"


class AlumniEvent(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="alumni_events")
    title = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length=255)
    poster = models.ImageField(upload_to="alumni/events/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.title


class AlumniContribution(models.Model):
    TYPE_CHOICES = (
        ("DONATION", "Donation"),
        ("MENTORSHIP", "Mentorship"),
        ("GUEST_LECTURE", "Guest Lecture"),
        ("OTHER", "Other"),
    )
    alumni = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name="contributions")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Only for donations
    notes = models.TextField(blank=True)
    date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.alumni.full_name} - {self.type}"


class SuccessStory(models.Model):
    alumni = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name="success_stories")
    title = models.CharField(max_length=255)
    content = models.TextField()
    image = models.ImageField(upload_to="alumni/stories/", null=True, blank=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Success Stories"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
