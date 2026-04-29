from django.db import models

from apps.schools.models import School


class SecurityIncident(models.Model):
    SEVERITY_CHOICES = (("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical"))
    STATUS_CHOICES = (("OPEN", "Open"), ("INVESTIGATING", "Investigating"), ("RESOLVED", "Resolved"), ("CLOSED", "Closed"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="security_incidents")
    title = models.CharField(max_length=180)
    incident_type = models.CharField(max_length=80, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="LOW")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    location = models.CharField(max_length=140, blank=True)
    description = models.TextField(blank=True)
    reported_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reported_at", "-id"]


class VisitorEntry(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="visitor_entries")
    name = models.CharField(max_length=140)
    phone = models.CharField(max_length=20, blank=True)
    purpose = models.CharField(max_length=160, blank=True)
    person_to_meet = models.CharField(max_length=140, blank=True)
    check_in_at = models.DateTimeField()
    check_out_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-check_in_at", "-id"]


class GuardRoster(models.Model):
    SHIFT_CHOICES = (("MORNING", "Morning"), ("EVENING", "Evening"), ("NIGHT", "Night"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="guard_rosters")
    guard_name = models.CharField(max_length=140)
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default="MORNING")
    area = models.CharField(max_length=120, blank=True)
    duty_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-duty_date", "-id"]


class GatePass(models.Model):
    TYPE_CHOICES = (("STUDENT_EXIT", "Student Exit"), ("VISITOR_EXIT", "Visitor Exit"), ("ASSET_MOVEMENT", "Asset Movement"))
    STATUS_CHOICES = (("ISSUED", "Issued"), ("USED", "Used"), ("EXPIRED", "Expired"), ("CANCELLED", "Cancelled"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="gate_passes")
    pass_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="VISITOR_EXIT")
    person_name = models.CharField(max_length=140)
    reason = models.CharField(max_length=255, blank=True)
    issued_at = models.DateTimeField()
    valid_till = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ISSUED")
    issued_by = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at", "-id"]


class PatrolCheckpointLog(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="patrol_logs")
    checkpoint_name = models.CharField(max_length=140)
    guard_name = models.CharField(max_length=140)
    logged_at = models.DateTimeField()
    status_note = models.CharField(max_length=255, blank=True)
    is_alert = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at", "-id"]
