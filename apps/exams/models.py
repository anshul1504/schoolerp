from django.conf import settings
from django.db import models

from apps.academics.models import AcademicClass, AcademicSubject
from apps.schools.models import School
from apps.students.models import Student


class Exam(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="exams")
    name = models.CharField(max_length=120)
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.CASCADE, related_name="exams")
    exam_date = models.DateField()
    total_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=33)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_exams",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-exam_date", "name"]
        unique_together = ("academic_class", "name", "exam_date")

    def __str__(self):
        return f"{self.name} - {self.academic_class}"


class ExamMark(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="exam_marks")
    subject = models.ForeignKey(AcademicSubject, on_delete=models.CASCADE, related_name="exam_marks")
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    remark = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["student__first_name", "subject__name"]
        unique_together = ("exam", "student", "subject")

    def __str__(self):
        return f"{self.student} - {self.subject}"
