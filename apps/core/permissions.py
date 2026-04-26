from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.core.cache import cache

from apps.core.models import RolePermissionsOverride


DEFAULT_PERMISSIONS = {
    "SUPER_ADMIN": {"*"},
    "SCHOOL_OWNER": {"schools.view", "schools.manage", "schools.comm_settings", "schools.team", "admissions.*", "students.*", "academics.*", "attendance.*", "fees.*", "exams.*", "communication.*", "staff.*", "reports.view"},
    "ADMIN": {"schools.view", "schools.manage", "schools.comm_settings", "schools.team", "admissions.*", "students.*", "academics.*", "attendance.*", "fees.*", "exams.*", "communication.*", "staff.*", "reports.view"},
    "PRINCIPAL": {"schools.view", "schools.manage", "schools.comm_settings", "schools.team", "admissions.*", "students.*", "academics.*", "attendance.*", "exams.*", "communication.*", "staff.*", "reports.view"},
    "VICE_PRINCIPAL": {"schools.view", "admissions.*", "students.*", "academics.*", "attendance.*", "exams.*", "communication.*", "staff.*", "reports.view"},
    "MANAGEMENT_TRUSTEE": {"schools.view", "students.view", "academics.view", "attendance.view", "fees.view", "exams.view", "communication.view", "staff.view", "reports.view"},
    "REPORT_VIEWER": {"schools.view", "students.view", "academics.view", "attendance.view", "fees.view", "exams.view", "communication.view", "staff.view", "reports.view"},
    "ACADEMIC_COORDINATOR": {"students.view", "academics.*", "attendance.*", "exams.view", "communication.*", "reports.view"},
    "EXAM_CONTROLLER": {"students.view", "academics.view", "exams.*", "communication.view", "reports.view"},
    "CLASS_TEACHER": {"students.view", "academics.view", "attendance.*", "exams.view", "communication.*"},
    "SUBJECT_TEACHER": {"students.view", "academics.view", "attendance.view", "exams.*", "communication.view"},
    "HOD": {"students.view", "academics.*", "attendance.view", "exams.*", "communication.*", "staff.view", "reports.view"},
    "SUBSTITUTE_TEACHER": {"students.view", "academics.view", "attendance.manage", "communication.view"},
    "TUTOR_MENTOR": {"students.view", "academics.view", "attendance.view", "exams.view", "communication.view"},
    "TEACHER": {"students.view", "academics.view", "attendance.*", "exams.*", "communication.*"},
    "STUDENT": {"academics.view", "attendance.view", "exams.view", "communication.view"},
    "PARENT": {"fees.view", "attendance.view", "communication.view"},
    "OFFICE_ADMIN": {"schools.view", "admissions.*", "students.*", "staff.view", "communication.*", "reports.view"},
    "RECEPTIONIST": {"admissions.*", "students.*", "communication.*", "frontoffice.*"},
    "ADMISSION_COUNSELOR": {"admissions.*", "students.view", "frontoffice.*", "communication.*", "reports.view"},
    "HR_MANAGER": {"staff.*", "communication.view", "reports.view"},
    "STAFF_COORDINATOR": {"staff.view", "attendance.view", "communication.view"},
    "ACCOUNTANT": {"fees.*", "reports.view"},
    "FEE_MANAGER": {"fees.*", "students.view", "communication.view", "reports.view"},
    "BILLING_EXECUTIVE": {"billing.manage", "fees.*", "reports.view"},
    "AUDITOR": {"fees.view", "billing.view", "activity.view", "reports.view"},
    "TRANSPORT_MANAGER": {"transport.*", "students.view", "staff.view", "communication.*", "reports.view"},
    "TRANSPORT_SUPERVISOR": {"transport.view", "transport.manage", "students.view", "communication.view"},
    "DRIVER": {"transport.view", "communication.view"},
    "CONDUCTOR_ATTENDANT": {"transport.view", "students.view", "communication.view"},
    "HOSTEL_MANAGER": {"hostel.*", "students.view", "fees.view", "communication.*", "reports.view"},
    "HOSTEL_WARDEN": {"hostel.view", "hostel.manage", "students.view", "communication.view"},
    "ASSISTANT_WARDEN": {"hostel.view", "students.view", "communication.view"},
    "MESS_MANAGER": {"hostel.view", "inventory.view", "communication.view"},
    "LIBRARIAN": {"library.*", "students.view", "communication.view", "reports.view"},
    "LAB_ASSISTANT": {"inventory.view", "academics.view", "communication.view"},
    "SPORTS_COACH": {"students.view", "attendance.view", "communication.view"},
    "INVENTORY_MANAGER": {"inventory.*", "reports.view"},
    "IT_ADMINISTRATOR": {"settings.manage", "users.manage", "activity.view", "reports.view"},
    "SYSTEM_OPERATOR": {"students.manage", "staff.view", "frontoffice.*", "communication.view"},
    "ROLE_PERMISSION_MANAGER": {"users.manage", "settings.manage", "activity.view"},
    "API_INTEGRATION_USER": {"api.*"},
    "NOTIFICATION_MANAGER": {"communication.*", "students.view", "staff.view", "reports.view"},
    "SCHOOL_COUNSELOR": {"students.view", "communication.view"},
    "EVENT_MANAGER": {"communication.*", "students.view", "staff.view"},
    "COMPLIANCE_OFFICER": {"activity.view", "reports.view", "students.view", "staff.view"},
    "SECURITY_OFFICER": {"activity.view", "frontoffice.view", "reports.view"},
    "DIGITAL_MARKETING_MANAGER": {"communication.*", "admissions.view", "reports.view"},
    "ALUMNI_MANAGER": {"students.view", "communication.*", "reports.view"},
    "PLACEMENT_COORDINATOR": {"students.view", "communication.*", "reports.view"},
    "RESEARCH_COORDINATOR": {"academics.view", "students.view", "reports.view"},
}


ROLE_EQUIVALENTS = {
    "SCHOOL_OWNER": {"ADMIN", "MANAGEMENT_TRUSTEE"},
    "PRINCIPAL": {"VICE_PRINCIPAL", "ACADEMIC_COORDINATOR", "HOD"},
    "TEACHER": {"CLASS_TEACHER", "SUBJECT_TEACHER", "SUBSTITUTE_TEACHER", "TUTOR_MENTOR"},
    "RECEPTIONIST": {"OFFICE_ADMIN", "ADMISSION_COUNSELOR", "SYSTEM_OPERATOR"},
    "ACCOUNTANT": {"FEE_MANAGER", "BILLING_EXECUTIVE", "AUDITOR"},
}


def _expanded_allowed_roles(allowed_roles):
    expanded = set(allowed_roles)
    for role in allowed_roles:
        expanded.update(ROLE_EQUIVALENTS.get(role, set()))
    return expanded


def _normalize_permissions(perms):
    return set(str(p).strip() for p in (perms or []) if str(p).strip())


def granted_permissions_for_role(role):
    cache_key = f"role_permissions:{role}"
    cached = cache.get(cache_key)
    if cached is not None:
        return set(cached)

    override = RolePermissionsOverride.objects.filter(role=role).first()
    if override:
        perms = _normalize_permissions(override.permissions)
    else:
        perms = DEFAULT_PERMISSIONS.get(role, set())

    cache.set(cache_key, list(perms), timeout=60)
    return set(perms)


def has_permission(user, permission_code):
    if not user or not getattr(user, "is_authenticated", False):
        return False

    role = getattr(user, "role", None) or "STUDENT"
    perms = granted_permissions_for_role(role)

    if "*" in perms:
        return True

    if permission_code in perms:
        return True

    parts = permission_code.split(".", 1)
    if len(parts) == 2:
        wildcard = f"{parts[0]}.*"
        if wildcard in perms:
            return True

    return False


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")

            if request.user.role not in _expanded_allowed_roles(allowed_roles):
                messages.error(request, "You do not have permission to access that section.")
                return redirect("dashboard")

            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def permission_required(permission_code, *, redirect_to="dashboard"):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")

            if not has_permission(request.user, permission_code):
                messages.error(request, "You do not have permission to perform that action.")
                return redirect(redirect_to)

            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
