from django.conf import settings
from django.db import models

from apps.academics.models import AcademicClass
from apps.schools.models import School
from apps.students.models import Student


class AttendanceSession(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="attendance_sessions")
    academic_class = models.ForeignKey(
        AcademicClass, on_delete=models.CASCADE, related_name="attendance_sessions"
    )
    attendance_date = models.DateField()
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendance_sessions",
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attendance_date", "academic_class__name", "academic_class__section"]
        unique_together = ("academic_class", "attendance_date")

    def __str__(self):
        return f"{self.academic_class} - {self.attendance_date}"


class StudentAttendance(models.Model):
    STATUS_CHOICES = (
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
        ("LEAVE", "Leave"),
    )

    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="student_attendance"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_entries"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PRESENT")
    remark = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        unique_together = ("session", "student")

    def __str__(self):
        return f"{self.student} - {self.status}"


class StaffAttendance(models.Model):
    STATUS_CHOICES = (
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
        ("LEAVE", "Leave"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="staff_attendance")
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_entries"
    )
    attendance_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PRESENT")
    remark = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_staff_attendance",
    )

    class Meta:
        ordering = ["-attendance_date", "staff__username"]
        unique_together = ("staff", "attendance_date")

    def __str__(self):
        return f"{self.staff} - {self.attendance_date} - {self.status}"


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = (
        ("SICK", "Sick Leave"),
        ("CASUAL", "Casual Leave"),
        ("EARNED", "Earned Leave"),
        ("OTHER", "Other"),
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="leave_requests")
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="leave_requests", null=True, blank=True
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_requests",
        null=True,
        blank=True,
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default="CASUAL")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_leave_requests",
    )
    review_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student or self.staff} - {self.leave_type} ({self.status})"
