from django.conf import settings
from django.db import models

from apps.academics.models import AcademicClass
from apps.schools.models import School
from apps.students.models import Student


class AttendanceSession(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="attendance_sessions")
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.CASCADE, related_name="attendance_sessions")
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

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="student_attendance")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_entries")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PRESENT")
    remark = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        unique_together = ("session", "student")

    def __str__(self):
        return f"{self.student} - {self.status}"
