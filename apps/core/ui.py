from django.core.cache import cache

from apps.core.models import RoleSectionsOverride
from apps.core.permissions import has_permission
from apps.schools.feature_access import MODULE_FEATURE_MAP, enabled_feature_codes_for_school
from apps.schools.models import SchoolSubscription

ROLE_UI = {
    "SUPER_ADMIN": {
        "label": "Super Admin",
        "subtitle": "Platform",
        "welcome": "Manage platform-level schools, users, billing, and settings.",
        "sections": {
            "platform",
            "dashboard",
            "students",
            "schools",
            "users",
            "billing",
            "activity",
            "reports",
            "settings",
            "research",
        },
    },
    "SCHOOL_OWNER": {
        "label": "School Owner",
        "subtitle": "Ownership",
        "welcome": "Full institutional oversight. Manage school profiles, finances, teams, and high-level strategy.",
        "sections": {
            "dashboard",
            "students",
            "schools",
            "admissions",
            "academics",
            "staff",
            "attendance",
            "fees",
            "exams",
            "communication",
            "reports",
            "transport",
            "hostel",
            "library",
            "timetable",
            "research",
        },
    },
    "PRINCIPAL": {
        "label": "Principal",
        "subtitle": "Academics",
        "welcome": "Lead school operations — academics, admissions, staff, exams, attendance, communication, and all facilities.",
        "sections": {
            "dashboard",
            "students",
            "schools",
            "admissions",
            "academics",
            "staff",
            "attendance",
            "fees",
            "exams",
            "communication",
            "reports",
            "timetable",
            "transport",
            "hostel",
            "library",
            "research",
        },
    },
    "TEACHER": {
        "label": "Teacher",
        "subtitle": "Teaching",
        "welcome": "Access your teaching and attendance modules.",
        "sections": {"dashboard", "students", "academics", "attendance", "exams", "communication"},
    },
    "STUDENT": {
        "label": "Student",
        "subtitle": "Student",
        "welcome": "View your classes, attendance, exam schedule, and school notices in one place.",
        "sections": {"dashboard", "academics", "attendance", "exams", "communication"},
    },
    "PARENT": {
        "label": "Parent",
        "subtitle": "Parent",
        "welcome": "Follow your child's attendance, fee status, school notices, and academic progress.",
        "sections": {"dashboard", "fees", "attendance", "communication"},
    },
    "ACCOUNTANT": {
        "label": "Accountant",
        "subtitle": "Finance",
        "welcome": "Manage collections, dues, receipts, and finance visibility for your assigned school.",
        "sections": {"dashboard", "fees", "reports"},
    },
    "RECEPTIONIST": {
        "label": "Receptionist",
        "subtitle": "Front office",
        "welcome": "Handle front-desk operations, visitor support, enquiries, and daily coordination smoothly.",
        "sections": {"frontoffice"},
    },
}

ROLE_UI.update(
    {
        "ADMIN": {
            "label": "Admin",
            "subtitle": "Administration",
            "welcome": "Manage school operations, admissions, academics, fees, and reports.",
            "sections": {
                "dashboard",
                "students",
                "schools",
                "admissions",
                "academics",
                "staff",
                "attendance",
                "fees",
                "exams",
                "communication",
                "reports",
                "transport",
                "hostel",
                "library",
                "timetable",
                "research",
            },
        },
        "VICE_PRINCIPAL": {
            "label": "Vice Principal",
            "subtitle": "Academics",
            "welcome": "Coordinate academics, admissions, attendance, exams, communication, and student operations.",
            "sections": {
                "dashboard",
                "students",
                "schools",
                "admissions",
                "academics",
                "staff",
                "attendance",
                "exams",
                "communication",
                "reports",
                "timetable",
            },
        },
        "MANAGEMENT_TRUSTEE": {
            "label": "Management / Trustee",
            "subtitle": "Management",
            "welcome": "Review institutional progress, finance, staffing, and operational reports.",
            "sections": {
                "dashboard",
                "students",
                "schools",
                "academics",
                "staff",
                "attendance",
                "fees",
                "exams",
                "communication",
                "reports",
            },
        },
        "REPORT_VIEWER": {
            "label": "Report Viewer",
            "subtitle": "Read-only",
            "welcome": "View reports and operational summaries without making changes.",
            "sections": {
                "dashboard",
                "students",
                "academics",
                "attendance",
                "fees",
                "exams",
                "reports",
            },
        },
        "ACADEMIC_COORDINATOR": {
            "label": "Academic Coordinator",
            "subtitle": "Academics",
            "welcome": "Coordinate classes, curriculum, attendance, exams, and academic communication.",
            "sections": {
                "dashboard",
                "students",
                "academics",
                "attendance",
                "exams",
                "communication",
                "reports",
            },
        },
        "EXAM_CONTROLLER": {
            "label": "Exam Controller",
            "subtitle": "Exams",
            "welcome": "Manage exam schedules, results, and exam-related reporting.",
            "sections": {"dashboard", "students", "academics", "exams", "communication", "reports"},
        },
        "CLASS_TEACHER": {
            "label": "Class Teacher / Incharge",
            "subtitle": "Teaching",
            "welcome": "Manage your class students, attendance, notices, and academic follow-up.",
            "sections": {
                "dashboard",
                "students",
                "academics",
                "attendance",
                "exams",
                "communication",
            },
        },
        "SUBJECT_TEACHER": {
            "label": "Subject Teacher",
            "subtitle": "Teaching",
            "welcome": "Access your subject classes, attendance, exams, and school communication.",
            "sections": {
                "dashboard",
                "students",
                "academics",
                "attendance",
                "exams",
                "communication",
            },
        },
        "HOD": {
            "label": "Head of Department",
            "subtitle": "Department",
            "welcome": "Oversee department academics, teachers, exams, and reports.",
            "sections": {
                "dashboard",
                "students",
                "academics",
                "staff",
                "attendance",
                "exams",
                "communication",
                "reports",
            },
        },
        "SUBSTITUTE_TEACHER": {
            "label": "Substitute Teacher",
            "subtitle": "Teaching",
            "welcome": "Access assigned classes, attendance, and classroom communication.",
            "sections": {"dashboard", "students", "academics", "attendance", "communication"},
        },
        "TUTOR_MENTOR": {
            "label": "Tutor / Mentor",
            "subtitle": "Mentor",
            "welcome": "Track assigned students, academic progress, attendance, and communication.",
            "sections": {
                "dashboard",
                "students",
                "academics",
                "attendance",
                "exams",
                "communication",
            },
        },
        "OFFICE_ADMIN": {
            "label": "Office Admin",
            "subtitle": "Office",
            "welcome": "Manage front-office records, students, staff visibility, and communication.",
            "sections": {
                "dashboard",
                "frontoffice",
                "students",
                "staff",
                "communication",
                "reports",
            },
        },
        "ADMISSION_COUNSELOR": {
            "label": "Admission Counselor",
            "subtitle": "Admissions",
            "welcome": "Manage enquiries, admissions, follow-ups, and applicant communication.",
            "sections": {
                "dashboard",
                "frontoffice",
                "admissions",
                "students",
                "communication",
                "reports",
            },
        },
        "HR_MANAGER": {
            "label": "HR Manager",
            "subtitle": "Human Resources",
            "welcome": "Manage staff records, coordination, and HR reports.",
            "sections": {"dashboard", "staff", "attendance", "communication", "reports"},
        },
        "STAFF_COORDINATOR": {
            "label": "Staff Coordinator",
            "subtitle": "Coordination",
            "welcome": "Coordinate staff information, attendance visibility, and communication.",
            "sections": {"dashboard", "staff", "attendance", "communication"},
        },
        "FEE_MANAGER": {
            "label": "Fee Manager",
            "subtitle": "Finance",
            "welcome": "Manage student fees, dues, receipts, and collection reports.",
            "sections": {"dashboard", "students", "fees", "communication", "reports"},
        },
        "BILLING_EXECUTIVE": {
            "label": "Billing Executive",
            "subtitle": "Billing",
            "welcome": "Manage billing, invoices, fee operations, and finance reports.",
            "sections": {"dashboard", "fees", "billing", "reports"},
        },
        "AUDITOR": {
            "label": "Auditor",
            "subtitle": "Audit",
            "welcome": "Review finance, billing, activity logs, and reports.",
            "sections": {"dashboard", "fees", "billing", "activity", "reports"},
        },
        "TRANSPORT_MANAGER": {
            "label": "Transport Manager",
            "subtitle": "Transport",
            "welcome": "Coordinate transport staff, students, communication, and reports.",
            "sections": {"dashboard", "students", "staff", "communication", "reports", "transport"},
        },
        "TRANSPORT_SUPERVISOR": {
            "label": "Transport Supervisor",
            "subtitle": "Transport",
            "welcome": "Monitor transport operations, students, and communication.",
            "sections": {"dashboard", "students", "communication"},
        },
        "DRIVER": {
            "label": "Driver",
            "subtitle": "Transport",
            "welcome": "Access assigned transport communication and updates.",
            "sections": {"dashboard", "communication"},
        },
        "CONDUCTOR_ATTENDANT": {
            "label": "Conductor / Attendant",
            "subtitle": "Transport",
            "welcome": "Access assigned student and transport communication.",
            "sections": {"dashboard", "students", "communication"},
        },
        "HOSTEL_MANAGER": {
            "label": "Hostel Manager",
            "subtitle": "Hostel",
            "welcome": "Manage hostel students, communication, finance visibility, and reports.",
            "sections": {"dashboard", "students", "fees", "communication", "reports", "hostel"},
        },
        "HOSTEL_WARDEN": {
            "label": "Hostel Warden",
            "subtitle": "Hostel",
            "welcome": "Track hostel students and communication.",
            "sections": {"dashboard", "students", "communication"},
        },
        "ASSISTANT_WARDEN": {
            "label": "Assistant Warden",
            "subtitle": "Hostel",
            "welcome": "Support hostel student monitoring and communication.",
            "sections": {"dashboard", "students", "communication"},
        },
        "MESS_MANAGER": {
            "label": "Mess Manager",
            "subtitle": "Hostel",
            "welcome": "Access hostel-related communication and operational updates.",
            "sections": {"dashboard", "communication"},
        },
        "LIBRARIAN": {
            "label": "Librarian",
            "subtitle": "Library",
            "welcome": "Manage library-related students, communication, and reports.",
            "sections": {"dashboard", "students", "communication", "reports", "library"},
        },
        "LAB_ASSISTANT": {
            "label": "Lab Assistant",
            "subtitle": "Facilities",
            "welcome": "Access academic lab coordination and communication.",
            "sections": {"dashboard", "academics", "communication"},
        },
        "SPORTS_COACH": {
            "label": "Sports Coach",
            "subtitle": "Sports",
            "welcome": "Track students, attendance visibility, and sports communication.",
            "sections": {"dashboard", "students", "attendance", "communication"},
        },
        "INVENTORY_MANAGER": {
            "label": "Inventory Manager",
            "subtitle": "Resources",
            "welcome": "Review resource operations and reports.",
            "sections": {"dashboard", "reports"},
        },
        "IT_ADMINISTRATOR": {
            "label": "IT Administrator",
            "subtitle": "System",
            "welcome": "Manage users, settings, activity logs, and technical operations.",
            "sections": {"dashboard", "users", "activity", "reports", "settings"},
        },
        "SYSTEM_OPERATOR": {
            "label": "System Operator",
            "subtitle": "Data Entry",
            "welcome": "Manage assigned student, front-office, and data-entry operations.",
            "sections": {"dashboard", "frontoffice", "students", "staff", "communication"},
        },
        "ROLE_PERMISSION_MANAGER": {
            "label": "Role & Permission Manager",
            "subtitle": "RBAC",
            "welcome": "Manage users, role permissions, and RBAC audit activity.",
            "sections": {"dashboard", "users", "activity", "settings"},
        },
        "API_INTEGRATION_USER": {
            "label": "API / Integration User",
            "subtitle": "Integration",
            "welcome": "Integration account for API and automation access.",
            "sections": {"dashboard"},
        },
        "NOTIFICATION_MANAGER": {
            "label": "Notification Manager",
            "subtitle": "Communication",
            "welcome": "Manage SMS, email, WhatsApp, notices, and communication reports.",
            "sections": {"dashboard", "students", "staff", "communication", "reports"},
        },
        "SCHOOL_COUNSELOR": {
            "label": "School Counselor",
            "subtitle": "Student Support",
            "welcome": "Support students through profile visibility and communication.",
            "sections": {"dashboard", "students", "communication"},
        },
        "EVENT_MANAGER": {
            "label": "Event Manager",
            "subtitle": "Events",
            "welcome": "Coordinate school events, audiences, and communication.",
            "sections": {"dashboard", "students", "staff", "communication"},
        },
        "COMPLIANCE_OFFICER": {
            "label": "Compliance Officer",
            "subtitle": "Compliance",
            "welcome": "Review activity, students, staff, and compliance reporting.",
            "sections": {"dashboard", "students", "staff", "activity", "reports"},
        },
        "SECURITY_OFFICER": {
            "label": "Security Officer",
            "subtitle": "Security",
            "welcome": "Review front-office visibility, security activity, and reports.",
            "sections": {"dashboard", "frontoffice", "activity", "reports"},
        },
        "DIGITAL_MARKETING_MANAGER": {
            "label": "Digital Marketing Manager",
            "subtitle": "Marketing",
            "welcome": "Manage campaigns, admissions communication, and reports.",
            "sections": {"frontoffice", "communication", "reports"},
        },
        "ALUMNI_MANAGER": {
            "label": "Alumni Manager",
            "subtitle": "Alumni",
            "welcome": "Coordinate alumni communication and reports.",
            "sections": {"dashboard", "students", "communication", "reports"},
        },
        "PLACEMENT_COORDINATOR": {
            "label": "Placement Coordinator",
            "subtitle": "Placement",
            "welcome": "Coordinate senior student placement communication and reports.",
            "sections": {"dashboard", "students", "communication", "reports"},
        },
        "RESEARCH_COORDINATOR": {
            "label": "Research Coordinator",
            "subtitle": "Research",
            "welcome": "Review academic and student reports for research coordination.",
            "sections": {"dashboard", "students", "academics", "reports", "research"},
        },
        "CAREER_COUNSELOR": {
            "label": "Career Counselor",
            "subtitle": "Guidance",
            "welcome": "Track student aspirations, university applications, and counseling sessions.",
            "sections": {
                "dashboard",
                "students",
                "communication",
                "career_counseling",
                "research",
                "academics",
                "admissions",
                "attendance",
                "exams",
                "reports",
                "frontoffice",
            },
        },
        "TESTER": {
            "label": "System Tester",
            "subtitle": "QA & Testing",
            "welcome": "Access all system modules for comprehensive testing and verification.",
            "sections": {
                "platform",
                "dashboard",
                "students",
                "schools",
                "admissions",
                "users",
                "academics",
                "staff",
                "attendance",
                "fees",
                "exams",
                "communication",
                "frontoffice",
                "transport",
                "hostel",
                "library",
                "timetable",
                "billing",
                "activity",
                "reports",
                "settings",
                "research",
                "career_counseling",
            },
        },
    }
)

BASE_NAVIGATION = [
    {"key": "platform", "label": "Platform", "icon": "ri-command-line", "url": "/platform/"},
    {"key": "dashboard", "label": "Dashboard", "icon": "ri-home-4-line", "url": "/dashboard/"},
    {"key": "students", "label": "Students", "icon": "ri-graduation-cap-line", "url": "/students/"},
    {"key": "schools", "label": "Schools", "icon": "ri-school-line", "url": "/schools/"},
    {
        "key": "admissions",
        "label": "Admissions",
        "icon": "ri-file-list-2-line",
        "url": "/admissions/",
    },
    {"key": "users", "label": "Users & Roles", "icon": "ri-shield-user-line", "url": "/users/"},
    {"key": "academics", "label": "Academics", "icon": "ri-book-open-line", "url": "/academics/"},
    {"key": "staff", "label": "Staff", "icon": "ri-team-line", "url": "/staff/"},
    {
        "key": "attendance",
        "label": "Attendance",
        "icon": "ri-calendar-check-line",
        "url": "/attendance/",
    },
    {"key": "fees", "label": "Fees", "icon": "ri-money-dollar-circle-line", "url": "/fees/"},
    {"key": "exams", "label": "Exams", "icon": "ri-file-edit-line", "url": "/exams/"},
    {
        "key": "communication",
        "label": "Communication",
        "icon": "ri-message-2-line",
        "url": "/communication/",
    },
    {
        "key": "frontoffice",
        "label": "Front Office",
        "icon": "ri-briefcase-4-line",
        "url": "/frontoffice/",
    },
    {"key": "transport", "label": "Transport", "icon": "ri-bus-line", "url": "/transport/"},
    {"key": "hostel", "label": "Hostel", "icon": "ri-hotel-line", "url": "/hostel/"},
    {"key": "library", "label": "Library", "icon": "ri-book-3-line", "url": "/library/"},
    {
        "key": "timetable",
        "label": "Timetable",
        "icon": "ri-calendar-todo-line",
        "url": "/timetable/",
    },
    {"key": "billing", "label": "Billing", "icon": "ri-bill-line", "url": "/billing/plans/"},
    {
        "key": "activity",
        "label": "Activity Log",
        "icon": "ri-file-list-3-line",
        "url": "/activity/",
    },
    {"key": "reports", "label": "Reports", "icon": "ri-bar-chart-box-line", "url": "/reports/"},
    {"key": "settings", "label": "Settings", "icon": "ri-settings-3-line", "url": "/settings/"},
    {"key": "research", "label": "Research", "icon": "ri-microscope-line", "url": "/research/"},
    {
        "key": "career_counseling",
        "label": "Career Counseling",
        "icon": "ri-compass-3-line",
        "url": "/career-counseling/",
    },
]


def get_role_config(user):
    role = getattr(user, "role", None) or "STUDENT"
    base = ROLE_UI.get(role, ROLE_UI["STUDENT"]).copy()

    cache_key = f"role_sections_override:{role}"
    override_sections = cache.get(cache_key)
    if override_sections is None:
        override = RoleSectionsOverride.objects.filter(role=role).first()
        override_sections = override.sections if override else None
        cache.set(cache_key, override_sections, timeout=60)

    if override_sections:
        base["sections"] = set(override_sections)
    return base


def build_layout_context(user, current_section="dashboard"):
    role_config = get_role_config(user)
    allowed_sections = role_config["sections"]
    navigation = []

    enabled_features = None
    if (
        getattr(user, "is_authenticated", False)
        and getattr(user, "role", None) != "SUPER_ADMIN"
        and getattr(user, "school_id", None)
    ):
        enabled_features = enabled_feature_codes_for_school(user.school_id)
        if (
            not enabled_features
            and not SchoolSubscription.objects.filter(school_id=user.school_id).exists()
        ):
            # No subscription configured yet: keep baseline role navigation visible.
            enabled_features = None

    for item in BASE_NAVIGATION:
        if item["key"] in allowed_sections:
            required_feature = MODULE_FEATURE_MAP.get(item["key"])
            if (
                required_feature
                and enabled_features is not None
                and required_feature not in enabled_features
            ):
                continue
            navigation.append({**item, "active": item["key"] == current_section})

    nav_keys = [item["key"] for item in navigation]

    return {
        "role_config": role_config,
        "navigation": navigation,
        "nav_keys": nav_keys,
        "ui_capabilities": {
            "can_manage_students": has_permission(user, "students.manage"),
            "can_manage_fees": has_permission(user, "fees.manage"),
            "can_manage_schools": has_permission(user, "schools.manage"),
            "can_manage_comm_settings": has_permission(user, "schools.comm_settings"),
            "can_manage_admissions": has_permission(user, "admissions.manage"),
            "can_manage_staff": has_permission(user, "staff.manage"),
            "can_manage_academics": has_permission(user, "academics.manage"),
            "can_manage_research": has_permission(user, "research.manage"),
        },
        "current_section": current_section,
    }
