ROLE_GROUP_LABELS = (
    (
        "Super Admin & Management",
        (
            "SUPER_ADMIN",
            "SCHOOL_OWNER",
            "ADMIN",
            "PRINCIPAL",
            "VICE_PRINCIPAL",
            "MANAGEMENT_TRUSTEE",
            "REPORT_VIEWER",
        ),
    ),
    (
        "Academic Roles",
        (
            "ACADEMIC_COORDINATOR",
            "EXAM_CONTROLLER",
            "CLASS_TEACHER",
            "SUBJECT_TEACHER",
            "HOD",
            "SUBSTITUTE_TEACHER",
            "TUTOR_MENTOR",
            "TEACHER",
        ),
    ),
    ("Student & Parent Roles", ("STUDENT", "PARENT")),
    (
        "Administration & Office Roles",
        ("OFFICE_ADMIN", "RECEPTIONIST", "ADMISSION_COUNSELOR", "HR_MANAGER", "STAFF_COORDINATOR"),
    ),
    ("Finance & Accounts Roles", ("ACCOUNTANT", "FEE_MANAGER", "BILLING_EXECUTIVE", "AUDITOR")),
    (
        "Transport Management Roles",
        ("TRANSPORT_MANAGER", "TRANSPORT_SUPERVISOR", "DRIVER", "CONDUCTOR_ATTENDANT"),
    ),
    (
        "Hostel Management Roles",
        ("HOSTEL_MANAGER", "HOSTEL_WARDEN", "ASSISTANT_WARDEN", "MESS_MANAGER"),
    ),
    (
        "Facilities & Resource Roles",
        ("LIBRARIAN", "LAB_ASSISTANT", "SPORTS_COACH", "INVENTORY_MANAGER"),
    ),
    (
        "IT & System Roles",
        ("IT_ADMINISTRATOR", "SYSTEM_OPERATOR", "ROLE_PERMISSION_MANAGER", "API_INTEGRATION_USER"),
    ),
    (
        "Communication & Support Roles",
        ("NOTIFICATION_MANAGER", "SCHOOL_COUNSELOR", "EVENT_MANAGER", "COMPLIANCE_OFFICER"),
    ),
    (
        "Optional / Advanced Roles",
        (
            "SECURITY_OFFICER",
            "DIGITAL_MARKETING_MANAGER",
            "ALUMNI_MANAGER",
            "CAREER_COUNSELOR",
            "RESEARCH_COORDINATOR",
        ),
    ),
)


def grouped_role_choices(role_choices):
    labels = dict(role_choices)
    grouped = []
    used = set()
    for group_label, values in ROLE_GROUP_LABELS:
        options = []
        for value in values:
            if value in labels:
                options.append((value, labels[value]))
                used.add(value)
        if options:
            grouped.append((group_label, options))

    remaining = [(value, label) for value, label in role_choices if value not in used]
    if remaining:
        grouped.append(("Other Roles", remaining))
    return grouped
