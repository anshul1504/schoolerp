from django.db import models

from apps.schools.models import School


class StaffMember(models.Model):
    ROLE_CHOICES = (
        ("TEACHER", "Teacher"),
        ("STAFF", "Staff"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="staff_members")
    full_name = models.CharField(max_length=150)
    staff_role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="STAFF")
    employee_id = models.CharField(max_length=50, blank=True)
    designation = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    joined_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["school", "employee_id"], name="uniq_employee_id_per_school"),
        ]

    def __str__(self):
        return self.full_name
