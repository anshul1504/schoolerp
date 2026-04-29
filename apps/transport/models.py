from django.db import models

from apps.schools.models import School
from apps.students.models import Student


class Driver(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="drivers")
    full_name = models.CharField(max_length=150)
    license_number = models.CharField(max_length=50, unique=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = (
        ("BUS", "Bus"),
        ("VAN", "Van"),
        ("MINI_BUS", "Mini Bus"),
        ("OTHER", "Other"),
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="vehicles")
    vehicle_no = models.CharField(max_length=50, unique=True)
    vehicle_model = models.CharField(max_length=100, blank=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES, default="BUS")
    capacity = models.PositiveIntegerField(default=40)
    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name="vehicles"
    )
    registration_expiry = models.DateField(null=True, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vehicle_no} ({self.vehicle_type})"


class Route(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="routes")
    name = models.CharField(max_length=150)
    start_point = models.CharField(max_length=200)
    end_point = models.CharField(max_length=200)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="routes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Stop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=150)
    pickup_time = models.TimeField()
    drop_time = models.TimeField()
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} ({self.route.name})"


class TransportAllocation(models.Model):
    student = models.OneToOneField(
        Student, on_delete=models.CASCADE, related_name="transport_allocation"
    )
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="allocations")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="allocations")
    allocated_on = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.student} - {self.route.name}"
