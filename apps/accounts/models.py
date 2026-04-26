from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid
import secrets

from apps.schools.models import School


class User(AbstractUser):
    ROLE_CHOICES = (
        # Super Admin & Management
        ("SUPER_ADMIN", "Super Admin"),
        ("SCHOOL_OWNER", "School Owner"),
        ("ADMIN", "Admin"),
        ("PRINCIPAL", "Principal"),
        ("VICE_PRINCIPAL", "Vice Principal"),
        ("MANAGEMENT_TRUSTEE", "Management / Trustee"),
        ("REPORT_VIEWER", "Report Viewer (Read-only)"),
        # Academic Roles
        ("ACADEMIC_COORDINATOR", "Academic Coordinator"),
        ("EXAM_CONTROLLER", "Exam Controller"),
        ("CLASS_TEACHER", "Class Teacher / Class Incharge"),
        ("SUBJECT_TEACHER", "Subject Teacher"),
        ("HOD", "Head of Department (HOD)"),
        ("SUBSTITUTE_TEACHER", "Substitute Teacher"),
        ("TUTOR_MENTOR", "Tutor / Mentor"),
        ("TEACHER", "Teacher"),
        # Student & Parent Roles
        ("STUDENT", "Student"),
        ("PARENT", "Parent / Guardian"),
        # Administration & Office Roles
        ("OFFICE_ADMIN", "Office Admin"),
        ("RECEPTIONIST", "Receptionist / Front Desk"),
        ("ADMISSION_COUNSELOR", "Admission Counselor"),
        ("HR_MANAGER", "HR Manager"),
        ("STAFF_COORDINATOR", "Staff Coordinator"),
        # Finance & Accounts Roles
        ("ACCOUNTANT", "Accountant"),
        ("FEE_MANAGER", "Fee Manager"),
        ("BILLING_EXECUTIVE", "Billing Executive"),
        ("AUDITOR", "Auditor"),
        # Transport Management Roles
        ("TRANSPORT_MANAGER", "Transport Manager"),
        ("TRANSPORT_SUPERVISOR", "Transport Supervisor"),
        ("DRIVER", "Driver"),
        ("CONDUCTOR_ATTENDANT", "Conductor / Attendant"),
        # Hostel Management Roles
        ("HOSTEL_MANAGER", "Hostel Manager"),
        ("HOSTEL_WARDEN", "Hostel Warden"),
        ("ASSISTANT_WARDEN", "Assistant Warden"),
        ("MESS_MANAGER", "Mess Manager"),
        # Facilities & Resource Roles
        ("LIBRARIAN", "Librarian"),
        ("LAB_ASSISTANT", "Lab Assistant"),
        ("SPORTS_COACH", "Sports Coach"),
        ("INVENTORY_MANAGER", "Inventory Manager / Store Keeper"),
        # IT & System Roles
        ("IT_ADMINISTRATOR", "IT Administrator"),
        ("SYSTEM_OPERATOR", "System Operator / Data Entry Operator"),
        ("ROLE_PERMISSION_MANAGER", "Role & Permission Manager"),
        ("API_INTEGRATION_USER", "API / Integration User"),
        # Communication & Support Roles
        ("NOTIFICATION_MANAGER", "Notification Manager (SMS/Email/WhatsApp)"),
        ("SCHOOL_COUNSELOR", "School Counselor"),
        ("EVENT_MANAGER", "Event Manager"),
        ("COMPLIANCE_OFFICER", "Compliance Officer"),
        # Optional / Advanced Roles
        ("SECURITY_OFFICER", "Security Officer"),
        ("DIGITAL_MARKETING_MANAGER", "Digital Marketing Manager"),
        ("ALUMNI_MANAGER", "Alumni Manager"),
        ("PLACEMENT_COORDINATOR", "Placement Coordinator"),
        ("RESEARCH_COORDINATOR", "Research Coordinator"),
    )

    role = models.CharField(max_length=40, choices=ROLE_CHOICES)
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)

    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    avatar = models.ImageField(upload_to="users/avatars/", null=True, blank=True)


class UserInvitation(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="invitation")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_invitations")
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    sent_to = models.EmailField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    send_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_accepted(self):
        return self.accepted_at is not None


class UserLoginOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_otps")
    salt = models.CharField(max_length=64, default=secrets.token_hex, editable=False)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_used(self):
        return self.used_at is not None
