from django.conf import settings
from django.db import models

from apps.schools.models import School


class AcademicClass(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_classes")
    name = models.CharField(max_length=100)
    section = models.CharField(max_length=50)
    class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeroom_classes",
    )
    room_name = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "section"]
        unique_together = ("school", "name", "section")

    def __str__(self):
        return f"{self.name} - {self.section}"


class AcademicSubject(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_subjects")
    academic_class = models.ForeignKey(
        AcademicClass, on_delete=models.CASCADE, related_name="subjects"
    )
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, blank=True)
    is_optional = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("academic_class", "name")

    def __str__(self):
        return f"{self.name} ({self.academic_class})"


class TeacherAllocation(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="teacher_allocations")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teaching_allocations",
    )
    academic_class = models.ForeignKey(
        AcademicClass, on_delete=models.CASCADE, related_name="teacher_allocations"
    )
    subject = models.ForeignKey(
        AcademicSubject, on_delete=models.CASCADE, related_name="teacher_allocations"
    )
    is_class_lead = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["academic_class__name", "subject__name"]
        unique_together = ("teacher", "academic_class", "subject")

    def __str__(self):
        return f"{self.teacher} - {self.subject}"


class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years")
    name = models.CharField(max_length=40, help_text="Example: 2026-2027")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ("school", "name")

    def __str__(self):
        return f"{self.school} - {self.name}"


class ClassMaster(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="class_masters")
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("school", "name")

    def __str__(self):
        return f"{self.school} - {self.name}"


class SectionMaster(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="section_masters")
    name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("school", "name")

    def __str__(self):
        return f"{self.school} - {self.name}"


class SubjectMaster(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="subject_masters")
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("school", "name")

    def __str__(self):
        return f"{self.school} - {self.name}"
