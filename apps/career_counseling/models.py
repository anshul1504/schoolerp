from django.db import models

from apps.schools.models import School
from apps.staff.models import StaffMember
from apps.students.models import Student


class CareerProfile(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="career_profile")
    interests = models.TextField(blank=True, help_text="Comma separated interests")
    target_exams = models.TextField(blank=True, help_text="e.g. JEE, NEET, SAT")
    preferred_courses = models.TextField(blank=True)
    preferred_universities = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Career Profile: {self.student.full_name}"


class University(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, help_text="City, Country")
    website = models.URLField(blank=True)
    is_abroad = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Universities"

    def __str__(self):
        return self.name


class Application(models.Model):
    STATUS_CHOICES = (
        ("PLANNED", "Planned"),
        ("APPLIED", "Applied"),
        ("ACCEPTED", "Accepted"),
        ("REJECTED", "Rejected"),
        ("WAITLISTED", "Waitlisted"),
        ("ENROLLED", "Enrolled"),
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="university_applications"
    )
    university = models.ForeignKey(University, on_delete=models.CASCADE)
    course = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLANNED")
    deadline = models.DateField(null=True, blank=True)
    applied_on = models.DateField(null=True, blank=True)
    result_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.full_name} -> {self.university.name}"


class CounselingSession(models.Model):
    TYPE_CHOICES = (
        ("ONE_ON_ONE", "1-on-1 Session"),
        ("GROUP", "Group Workshop"),
        ("PARENT_MEETING", "Parent Consultation"),
    )
    MODE_CHOICES = (
        ("OFFLINE", "In-Person"),
        ("ONLINE", "Online Meeting"),
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="counseling_sessions"
    )
    counselor = models.ForeignKey(
        StaffMember, on_delete=models.CASCADE, related_name="conducted_sessions"
    )
    session_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="ONE_ON_ONE")
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="OFFLINE")
    meeting_link = models.URLField(blank=True, help_text="Zoom/Meet link for online sessions")
    scheduled_at = models.DateTimeField()
    duration_minutes = models.IntegerField(default=30)
    summary = models.TextField(blank=True)
    feedback = models.TextField(blank=True, help_text="Student feedback or post-session evaluation")
    follow_up_required = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.session_type} for {self.student.full_name} on {self.scheduled_at}"


class CareerEvent(models.Model):
    EVENT_TYPE = (
        ("FAIR", "Career Fair"),
        ("INFO_SESSION", "University Info Session"),
        ("WORKSHOP", "Workshop"),
        ("GUEST_LECTURE", "Guest Lecture"),
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE, default="INFO_SESSION")
    date = models.DateTimeField()
    location = models.CharField(max_length=255, default="Main Hall")
    description = models.TextField(blank=True)
    organizer = models.CharField(
        max_length=255, blank=True, help_text="External university or agency name"
    )

    def __str__(self):
        return self.title


class EventRegistration(models.Model):
    event = models.ForeignKey(CareerEvent, on_delete=models.CASCADE, related_name="registrations")
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    attended = models.BooleanField(default=False)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "student")
