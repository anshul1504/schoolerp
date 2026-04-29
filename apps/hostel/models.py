from django.db import models

from apps.schools.models import School
from apps.students.models import Student


class Hostel(models.Model):
    HOSTEL_TYPE_CHOICES = (
        ("BOYS", "Boys"),
        ("GIRLS", "Girls"),
        ("COED", "Co-Ed"),
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="hostels")
    name = models.CharField(max_length=150)
    hostel_type = models.CharField(max_length=10, choices=HOSTEL_TYPE_CHOICES, default="BOYS")
    address = models.TextField(blank=True)
    warden_name = models.CharField(max_length=150, blank=True)
    warden_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Room(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="rooms")
    room_number = models.CharField(max_length=50)
    room_type = models.CharField(
        max_length=100, blank=True, help_text="Example: AC, Non-AC, 4-Seater"
    )
    capacity = models.PositiveIntegerField(default=4)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.room_number} ({self.hostel.name})"


class Bed(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="beds")
    bed_number = models.CharField(max_length=50)
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"Bed {self.bed_number} - {self.room.room_number}"


class MessPlan(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="mess_plans")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class HostelAllocation(models.Model):
    student = models.OneToOneField(
        Student, on_delete=models.CASCADE, related_name="hostel_allocation"
    )
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="allocations")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="allocations")
    bed = models.ForeignKey(
        Bed, on_delete=models.SET_NULL, null=True, blank=True, related_name="allocations"
    )
    mess_plan = models.ForeignKey(
        MessPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="allocations"
    )
    allocated_on = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.student} - {self.room.room_number}"
