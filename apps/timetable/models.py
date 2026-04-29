from django.conf import settings
from django.db import models

from apps.academics.models import AcademicClass, AcademicSubject
from apps.schools.models import School


class PeriodMaster(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="periods")
    name = models.CharField(max_length=50)  # Example: Period 1, Break, etc.
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"


class TimetableSlot(models.Model):
    DAY_CHOICES = (
        ("MONDAY", "Monday"),
        ("TUESDAY", "Tuesday"),
        ("WEDNESDAY", "Wednesday"),
        ("THURSDAY", "Thursday"),
        ("FRIDAY", "Friday"),
        ("SATURDAY", "Saturday"),
        ("SUNDAY", "Sunday"),
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="timetable_slots")
    academic_class = models.ForeignKey(
        AcademicClass, on_delete=models.CASCADE, related_name="timetable_slots"
    )
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    period = models.ForeignKey(PeriodMaster, on_delete=models.CASCADE, related_name="slots")
    subject = models.ForeignKey(
        AcademicSubject,
        on_delete=models.CASCADE,
        related_name="timetable_slots",
        null=True,
        blank=True,
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_slots",
    )
    room_number = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("academic_class", "day", "period")
        ordering = ["day", "period__start_time"]

    def __str__(self):
        return f"{self.academic_class} - {self.day} - {self.period.name}"
