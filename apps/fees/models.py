from django.conf import settings
from django.db import models

from apps.schools.models import School
from apps.students.models import Student


class FeeStructure(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="fee_structures")
    name = models.CharField(max_length=120)
    class_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    frequency = models.CharField(max_length=20, default="MONTHLY")
    due_day = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["class_name", "name"]
        unique_together = ("school", "name", "class_name")

    def __str__(self):
        return f"{self.name} - {self.class_name}"


class StudentFeeLedger(models.Model):
    STATUS_CHOICES = (
        ("DUE", "Due"),
        ("PARTIAL", "Partial"),
        ("PAID", "Paid"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="fee_ledgers")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fee_ledgers")
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name="student_ledgers")
    billing_month = models.CharField(max_length=20)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="DUE")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-due_date", "student__first_name"]
        unique_together = ("student", "fee_structure", "billing_month")

    def __str__(self):
        return f"{self.student} - {self.billing_month}"


class FeePayment(models.Model):
    PAYMENT_MODE_CHOICES = (
        ("CASH", "Cash"),
        ("ONLINE", "Online"),
        ("CHEQUE", "Cheque"),
    )

    ledger = models.ForeignKey(StudentFeeLedger, on_delete=models.CASCADE, related_name="payments")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="fee_payments")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fee_payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, default="CASH")
    reference_no = models.CharField(max_length=80, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fee_collections",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"{self.student} - {self.amount}"
