from calendar import monthrange
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.academics.models import (
    AcademicClass,
    AcademicSubject,
    AcademicYear,
    ClassMaster,
    SectionMaster,
    TeacherAllocation,
)
from apps.accounts.models import User, UserInvitation
from apps.admissions.models import AdmissionApplication
from apps.attendance.models import AttendanceSession
from apps.communication.models import Notice
from apps.core.models import (
    ActivityLog,
    AuthSecurityEvent,
    BillingWebhookEvent,
    InventoryItem,
    InventoryMovement,
    InventoryPurchaseOrder,
    InventoryVendor,
    LabBooking,
    LabEquipment,
    LabRoom,
    PlatformSettings,
    RBACChangeEvent,
    ReportTemplate,
    ScheduledReport,
    ServiceConfiguration,
    ServiceRefundEvent,
    SupportTicket,
    SystemBackup,
)
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context, get_role_config
from apps.exams.models import Exam
from apps.fees.models import FeePayment, FeeStructure, StudentFeeLedger
from apps.frontoffice.models import (
    Enquiry,
    MeetingRequest,
    MessageDeliveryLog,
    VisitorLog,
)
from apps.hostel.models import (
    Bed as HostelBed,
)
from apps.hostel.models import (
    Hostel,
    HostelAllocation,
)
from apps.hostel.models import (
    Room as HostelRoom,
)
from apps.library.models import (
    Author as LibraryAuthor,
)
from apps.library.models import (
    Book as LibraryBook,
)
from apps.library.models import (
    BookIssue as LibraryIssue,
)
from apps.library.models import (
    Category as LibraryCategory,
)
from apps.schools.models import (
    Campus,
    ImplementationProject,
    School,
    SchoolCommunicationSettings,
    SchoolDomain,
    SchoolSubscription,
    SubscriptionInvoice,
)
from apps.students.models import Student
from apps.transport.models import (
    Driver as TransportDriver,
)
from apps.transport.models import (
    Route as TransportRoute,
)
from apps.transport.models import (
    Stop as TransportStop,
)
from apps.transport.models import (
    TransportAllocation as TransportAssignment,
)
from apps.transport.models import (
    Vehicle as TransportVehicle,
)


def _month_labels(start_month, count=6):
    labels = []
    cursor = start_month
    for _ in range(count):
        labels.append(cursor)
        month = cursor.month + 1
        year = cursor.year
        if month > 12:
            month = 1
            year += 1
        cursor = cursor.replace(year=year, month=month)
    return labels


def _monthly_counts(queryset, field_name, months):
    start_dt = timezone.make_aware(datetime.combine(months[0], time.min))
    rows = (
        queryset.filter(**{f"{field_name}__gte": start_dt})
        .annotate(month=TruncMonth(field_name))
        .values("month")
        .annotate(total=Count("id"))
    )
    lookup = {row["month"].date().replace(day=1): row["total"] for row in rows if row["month"]}
    return [lookup.get(month, 0) for month in months]


def _money(value):
    return value or Decimal("0.00")


def _ensure_service_fee_ledger(student, school, service_code, service_name, amount, due_date=None):
    if not student or not school:
        return None
    if amount is None:
        return None
    try:
        amount_dec = Decimal(str(amount))
    except Exception:
        return None
    if amount_dec <= 0:
        return None
    due_on = due_date or timezone.localdate()
    billing_month = f"{due_on.year}-{due_on.month:02d}"
    fee_structure, _ = FeeStructure.objects.get_or_create(
        school=school,
        name=service_name,
        class_name=service_code,
        defaults={
            "amount": amount_dec,
            "frequency": "MONTHLY",
            "due_day": due_on.day,
            "is_active": True,
        },
    )
    if fee_structure.amount != amount_dec:
        fee_structure.amount = amount_dec
        fee_structure.is_active = True
        fee_structure.save(update_fields=["amount", "is_active"])
    ledger, _ = StudentFeeLedger.objects.get_or_create(
        school=school,
        student=student,
        fee_structure=fee_structure,
        billing_month=billing_month,
        defaults={
            "amount_due": amount_dec,
            "amount_paid": Decimal("0.00"),
            "due_date": due_on,
            "status": "DUE",
        },
    )
    return ledger


def _create_refund_event(student, school, service_type, source, source_ref=""):
    today = timezone.localdate()
    billing_month = f"{today.year}-{today.month:02d}"
    fee_structure = FeeStructure.objects.filter(
        school=school, class_name=service_type, is_active=True
    ).first()
    if not fee_structure:
        return None
    ledger = (
        StudentFeeLedger.objects.filter(
            school=school,
            student=student,
            fee_structure=fee_structure,
            billing_month=billing_month,
        )
        .order_by("-id")
        .first()
    )
    if not ledger:
        return None
    total_days = monthrange(today.year, today.month)[1]
    days_remaining = max(0, total_days - today.day + 1)
    ratio = (Decimal(days_remaining) / Decimal(total_days)) if total_days else Decimal("0")
    paid_amount = ledger.amount_paid or Decimal("0")
    recommended_refund = (paid_amount * ratio).quantize(Decimal("0.01"))
    return ServiceRefundEvent.objects.create(
        school=school,
        student=student,
        service_type=service_type,
        fee_ledger=ledger,
        source=source,
        source_ref=str(source_ref or ""),
        billed_amount=ledger.amount_due or Decimal("0"),
        paid_amount=paid_amount,
        policy_ratio=ratio.quantize(Decimal("0.0001")),
        days_remaining=days_remaining,
        total_days=total_days,
        recommended_refund=recommended_refund,
        status="OPEN",
        notes=f"Auto policy refund estimate for {service_type.lower()} discontinuation.",
    )


def _school_maturity_snapshot(school):
    comm = SchoolCommunicationSettings.objects.filter(school=school).first()
    subscription = SchoolSubscription.objects.select_related("plan").filter(school=school).first()
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    class_master_count = ClassMaster.objects.filter(school=school, is_active=True).count()
    section_master_count = SectionMaster.objects.filter(school=school, is_active=True).count()
    class_count = AcademicClass.objects.filter(school=school, is_active=True).count()
    subject_count = AcademicSubject.objects.filter(school=school).count()
    allocation_count = TeacherAllocation.objects.filter(school=school).count()
    campus_count = Campus.objects.filter(school=school, is_active=True).count()
    domain_count = SchoolDomain.objects.filter(school=school, is_active=True).count()
    notices_count = Notice.objects.filter(school=school, is_published=True).count()
    attendance_sessions = AttendanceSession.objects.filter(school=school).count()
    exams = Exam.objects.filter(school=school).count()
    ledgers = StudentFeeLedger.objects.filter(school=school).count()
    support_open = (
        SupportTicket.objects.filter(school=school)
        .exclude(status__in=["RESOLVED", "CLOSED"])
        .count()
    )
    implementation = ImplementationProject.objects.filter(school=school).first()

    checks = [
        {
            "key": "profile",
            "label": "School profile",
            "done": bool(school.name and school.code and school.email and school.phone),
            "weight": 10,
        },
        {"key": "campus", "label": "Main campus", "done": campus_count > 0, "weight": 8},
        {
            "key": "comm",
            "label": "Communication settings",
            "done": bool(comm and (comm.smtp_enabled or comm.whatsapp_enabled)),
            "weight": 12,
        },
        {
            "key": "subscription",
            "label": "Subscription active",
            "done": bool(subscription and subscription.status == "ACTIVE"),
            "weight": 10,
        },
        {"key": "domain", "label": "Domain mapped", "done": domain_count > 0, "weight": 8},
        {"key": "year", "label": "Academic year", "done": bool(current_year), "weight": 10},
        {
            "key": "class_master",
            "label": "Class master",
            "done": class_master_count > 0,
            "weight": 8,
        },
        {
            "key": "section_master",
            "label": "Section master",
            "done": section_master_count > 0,
            "weight": 8,
        },
        {"key": "classes", "label": "Academic classes", "done": class_count > 0, "weight": 8},
        {"key": "subjects", "label": "Subjects", "done": subject_count > 0, "weight": 6},
        {
            "key": "allocations",
            "label": "Teacher allocations",
            "done": allocation_count > 0,
            "weight": 10,
        },
        {"key": "notices", "label": "First notice", "done": notices_count > 0, "weight": 4},
        {
            "key": "attendance",
            "label": "Attendance started",
            "done": attendance_sessions > 0,
            "weight": 4,
        },
        {"key": "exams", "label": "Exams started", "done": exams > 0, "weight": 2},
        {"key": "fees", "label": "Fee ledgers", "done": ledgers > 0, "weight": 2},
        {"key": "support", "label": "Open support", "done": support_open == 0, "weight": 4},
        {
            "key": "implementation",
            "label": "Implementation complete",
            "done": bool(implementation and implementation.status == "DONE"),
            "weight": 6,
        },
    ]
    total_weight = sum(item["weight"] for item in checks) or 1
    achieved = sum(item["weight"] for item in checks if item["done"])
    score = round((achieved / total_weight) * 100, 1)
    completed = sum(1 for item in checks if item["done"])
    return {
        "school": school,
        "comm": comm,
        "subscription": subscription,
        "current_year": current_year,
        "class_master_count": class_master_count,
        "section_master_count": section_master_count,
        "class_count": class_count,
        "subject_count": subject_count,
        "allocation_count": allocation_count,
        "campus_count": campus_count,
        "domain_count": domain_count,
        "notices_count": notices_count,
        "attendance_sessions": attendance_sessions,
        "exams": exams,
        "ledgers": ledgers,
        "support_open": support_open,
        "implementation": implementation,
        "checks": checks,
        "completed": completed,
        "total": len(checks),
        "score": score,
        "status": "Ready" if score >= 85 else "Watch" if score >= 50 else "Needs setup",
    }


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def platform_home(request):
    now = timezone.now()
    today = now.date()
    start_month = today.replace(day=1)
    months = _month_labels(
        (start_month.replace(day=1) - timedelta(days=150)).replace(day=1), count=6
    )

    schools = School.objects.order_by("-created_at")
    users = User.objects.select_related("school").order_by("-date_joined")
    invites = UserInvitation.objects.select_related("user", "user__school").order_by("-created_at")
    activity = ActivityLog.objects.select_related("actor", "school").order_by("-created_at")
    subscriptions = SchoolSubscription.objects.select_related("school", "plan").order_by(
        "-created_at"
    )
    invoices = SubscriptionInvoice.objects.select_related("school", "plan").order_by("-created_at")
    support_tickets = SupportTicket.objects.select_related(
        "school", "assigned_to", "created_by"
    ).order_by("-updated_at")
    security_events = AuthSecurityEvent.objects.order_by("-created_at")
    domains = SchoolDomain.objects.select_related("school").order_by("-created_at")

    issued_invoices = invoices.exclude(status="VOID")
    paid_total = _money(
        issued_invoices.filter(status="PAID").aggregate(total=Sum("total_amount"))["total"]
    )
    outstanding_total = _money(
        issued_invoices.filter(status__in=["DRAFT", "ISSUED"]).aggregate(total=Sum("total_amount"))[
            "total"
        ]
    )

    subscription_status = list(
        subscriptions.values("status").annotate(total=Count("id")).order_by("status")
    )
    support_status = list(
        support_tickets.values("status").annotate(total=Count("id")).order_by("status")
    )
    activity_methods = list(
        activity.exclude(method="")
        .values("method")
        .annotate(total=Count("id"))
        .order_by("-total")[:6]
    )

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "kpis": {
                "schools_total": schools.count(),
                "schools_active": schools.filter(is_active=True).count(),
                "schools_inactive": schools.filter(is_active=False).count(),
                "users_total": users.count(),
                "users_active": users.filter(is_active=True).count(),
                "invites_pending": invites.filter(accepted_at__isnull=True).count(),
                "subscriptions_active": subscriptions.filter(status="ACTIVE").count(),
                "subscriptions_past_due": subscriptions.filter(status="PAST_DUE").count(),
                "open_support": support_tickets.exclude(status__in=["RESOLVED", "CLOSED"]).count(),
                "security_failures_24h": security_events.filter(
                    created_at__gte=now - timedelta(hours=24), success=False
                ).count(),
                "domains_active": domains.filter(is_active=True).count(),
                "paid_total": paid_total,
                "outstanding_total": outstanding_total,
            },
            "charts": {
                "months": [month.strftime("%b") for month in months],
                "school_growth": _monthly_counts(School.objects.all(), "created_at", months),
                "user_growth": _monthly_counts(User.objects.all(), "date_joined", months),
                "subscription_status_labels": [
                    row["status"].replace("_", " ").title() for row in subscription_status
                ],
                "subscription_status_values": [row["total"] for row in subscription_status],
                "support_status_labels": [
                    row["status"].replace("_", " ").title() for row in support_status
                ],
                "support_status_values": [row["total"] for row in support_status],
                "activity_method_labels": [row["method"] for row in activity_methods],
                "activity_method_values": [row["total"] for row in activity_methods],
            },
            "recent_schools": schools[:8],
            "recent_users": users[:8],
            "recent_invites": invites[:8],
            "recent_activity": activity[:10],
            "recent_subscriptions": subscriptions[:8],
            "recent_invoices": invoices[:8],
            "support_tickets": support_tickets[:8],
            "security_events": security_events[:8],
        }
    )
    return render(request, "platform/home.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def platform_rollout(request):
    projects = (
        ImplementationProject.objects.select_related("school")
        .prefetch_related("tasks")
        .order_by("-updated_at", "-id")
    )

    rows = []
    for project in projects:
        tasks = list(project.tasks.all())
        total = len(tasks)
        rows.append(
            {
                "project": project,
                "school": project.school,
                "total": total,
                "todo": sum(1 for t in tasks if t.status == "TODO"),
                "in_progress": sum(1 for t in tasks if t.status == "IN_PROGRESS"),
                "blocked": sum(1 for t in tasks if t.status == "BLOCKED"),
                "done": sum(1 for t in tasks if t.status == "DONE"),
                "done_pct": round((sum(1 for t in tasks if t.status == "DONE") / total * 100), 1)
                if total
                else 0,
            }
        )

    context = build_layout_context(request.user, current_section="platform")
    context["projects"] = rows
    context["project_counts"] = {
        "total": len(rows),
        "not_started": sum(1 for row in rows if row["project"].status == "NOT_STARTED"),
        "in_progress": sum(1 for row in rows if row["project"].status == "IN_PROGRESS"),
        "blocked": sum(1 for row in rows if row["project"].status == "BLOCKED"),
        "done": sum(1 for row in rows if row["project"].status == "DONE"),
    }
    return render(request, "platform/rollout.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_hub(request):
    recent_activity = ActivityLog.objects.select_related("actor", "school").order_by("-created_at")[
        :8
    ]
    recent_rbac = RBACChangeEvent.objects.select_related("actor").order_by("-created_at")[:8]
    recent_security = AuthSecurityEvent.objects.order_by("-created_at")[:8]
    now = timezone.now()
    today = now.date()

    overdue_invoices = SubscriptionInvoice.objects.filter(
        status="ISSUED", due_date__isnull=False, due_date__lt=today
    ).count()
    invoices_issued_7d = (
        SubscriptionInvoice.objects.filter(created_at__gte=now - timedelta(days=7))
        .exclude(status="VOID")
        .count()
    )
    invoices_paid_7d = SubscriptionInvoice.objects.filter(
        created_at__gte=now - timedelta(days=7), status="PAID"
    ).count()
    collection_rate_7d = (
        round((invoices_paid_7d / invoices_issued_7d) * 100, 1) if invoices_issued_7d else 100.0
    )

    webhook_processed_24h = BillingWebhookEvent.objects.filter(
        created_at__gte=now - timedelta(hours=24), processed_at__isnull=False
    ).count()
    webhook_failed_24h = (
        BillingWebhookEvent.objects.filter(created_at__gte=now - timedelta(hours=24))
        .exclude(process_error="")
        .count()
    )
    webhook_success_rate_24h = (
        round(((webhook_processed_24h - webhook_failed_24h) / webhook_processed_24h) * 100, 1)
        if webhook_processed_24h
        else 100.0
    )

    past_due_subscriptions = SchoolSubscription.objects.filter(status="PAST_DUE").count()
    urgent_open_support = (
        SupportTicket.objects.filter(priority="URGENT")
        .exclude(status__in=["RESOLVED", "CLOSED"])
        .count()
    )

    if overdue_invoices == 0 and webhook_failed_24h == 0 and collection_rate_7d >= 85:
        sla_state = "GREEN"
        sla_label = "Healthy"
    elif overdue_invoices <= 10 and webhook_failed_24h <= 5 and collection_rate_7d >= 70:
        sla_state = "YELLOW"
        sla_label = "Watch"
    else:
        sla_state = "RED"
        sla_label = "Critical"

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "recent_activity": recent_activity,
            "recent_rbac": recent_rbac,
            "recent_security": recent_security,
            "counts": {
                "activity": ActivityLog.objects.count(),
                "rbac": RBACChangeEvent.objects.count(),
                "security": AuthSecurityEvent.objects.count(),
            },
            "billing_sla": {
                "state": sla_state,
                "label": sla_label,
                "overdue_invoices": overdue_invoices,
                "past_due_subscriptions": past_due_subscriptions,
                "collection_rate_7d": collection_rate_7d,
                "webhook_processed_24h": webhook_processed_24h,
                "webhook_failed_24h": webhook_failed_24h,
                "webhook_success_rate_24h": webhook_success_rate_24h,
                "urgent_open_support": urgent_open_support,
            },
        }
    )
    return render(request, "platform/super_admin_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_pages_index(request):
    pages = [
        {
            "group": "Core",
            "label": "Super Admin Hub",
            "url": "/super-admin/",
            "icon": "ri-dashboard-line",
            "desc": "Control tower and SLA signals",
        },
        {
            "group": "Core",
            "label": "Platform Command Center",
            "url": "/platform/",
            "icon": "ri-line-chart-line",
            "desc": "Global metrics, charts, and queues",
        },
        {
            "group": "Core",
            "label": "Rollout Board",
            "url": "/platform/rollout/",
            "icon": "ri-road-map-line",
            "desc": "Implementation tracker across schools",
        },
        {
            "group": "Core",
            "label": "Pages Index",
            "url": "/super-admin/pages/",
            "icon": "ri-apps-2-line",
            "desc": "All super admin pages in one list",
        },
        {
            "group": "Governance",
            "label": "Role Sheet",
            "url": "/super-admin/roles/",
            "icon": "ri-shield-user-line",
            "desc": "Role completion and module coverage",
        },
        {
            "group": "Governance",
            "label": "Gap Sheet",
            "url": "/super-admin/gaps/",
            "icon": "ri-alert-line",
            "desc": "Pending areas and system gaps",
        },
        {
            "group": "Governance",
            "label": "Decision Dashboard",
            "url": "/super-admin/decision/",
            "icon": "ri-focus-3-line",
            "desc": "Priority ranking and execution focus",
        },
        {
            "group": "Governance",
            "label": "Setup Wizard",
            "url": "/super-admin/setup/",
            "icon": "ri-settings-3-line",
            "desc": "School readiness and onboarding",
        },
        {
            "group": "Operations",
            "label": "Transport",
            "url": "/super-admin/transport/",
            "icon": "ri-bus-line",
            "desc": "Routes, assignments, releases",
        },
        {
            "group": "Operations",
            "label": "Hostel",
            "url": "/super-admin/hostel/",
            "icon": "ri-hotel-bed-line",
            "desc": "Rooms, allocations, releases",
        },
        {
            "group": "Operations",
            "label": "Library",
            "url": "/super-admin/library/",
            "icon": "ri-book-open-line",
            "desc": "Issue, return, lost, fines",
        },
        {
            "group": "Operations",
            "label": "Inventory",
            "url": "/super-admin/inventory/",
            "icon": "ri-inbox-archive-line",
            "desc": "Stock and movement ledger",
        },
        {
            "group": "Operations",
            "label": "Fee Reconciliation",
            "url": "/super-admin/fees/",
            "icon": "ri-money-rupee-circle-line",
            "desc": "Fees control and monitoring",
        },
        {
            "group": "Platform Ops",
            "label": "Security",
            "url": "/platform/security/",
            "icon": "ri-shield-flash-line",
            "desc": "Security event stream",
        },
        {
            "group": "Platform Ops",
            "label": "Support",
            "url": "/platform/support/",
            "icon": "ri-customer-service-2-line",
            "desc": "Ticket operations",
        },
        {
            "group": "Platform Ops",
            "label": "Domains",
            "url": "/platform/domains/",
            "icon": "ri-global-line",
            "desc": "Domain mapping controls",
        },
        {
            "group": "Platform Ops",
            "label": "Tokens",
            "url": "/platform/tokens/",
            "icon": "ri-key-2-line",
            "desc": "API token lifecycle",
        },
        {
            "group": "Platform Ops",
            "label": "Announcements",
            "url": "/platform/announcements/",
            "icon": "ri-notification-3-line",
            "desc": "Platform-wide notices",
        },
        {
            "group": "Platform Ops",
            "label": "System Ops & Backups",
            "url": "/super-admin/system/",
            "icon": "ri-cpu-line",
            "desc": "Cloud gateway, health, and DB backups",
        },
    ]
    groups = {}
    for page in pages:
        groups.setdefault(page["group"], []).append(page)

    context = build_layout_context(request.user, current_section="platform")
    context["page_groups"] = groups
    context["page_total"] = len(pages)
    return render(request, "platform/pages_index.html", context)


def _module_state_snapshot():
    return {
        "platform": "GREEN" if School.objects.exists() else "YELLOW",
        "dashboard": "GREEN",
        "students": "GREEN" if Student.objects.exists() else "YELLOW",
        "schools": "GREEN" if School.objects.exists() else "YELLOW",
        "admissions": "GREEN" if AdmissionApplication.objects.exists() else "YELLOW",
        "users": "GREEN" if User.objects.count() > 1 else "YELLOW",
        "academics": "GREEN"
        if AcademicClass.objects.exists() and AcademicSubject.objects.exists()
        else "YELLOW",
        "staff": "YELLOW",
        "attendance": "YELLOW" if AttendanceSession.objects.exists() else "RED",
        "fees": "YELLOW"
        if StudentFeeLedger.objects.exists() or FeePayment.objects.exists()
        else "RED",
        "exams": "YELLOW" if Exam.objects.exists() else "RED",
        "communication": "YELLOW" if Notice.objects.exists() else "RED",
        "frontoffice": "GREEN"
        if Enquiry.objects.exists()
        or VisitorLog.objects.exists()
        or MeetingRequest.objects.exists()
        else "YELLOW",
        "billing": "YELLOW" if SubscriptionInvoice.objects.exists() else "RED",
        "transport": "GREEN"
        if TransportRoute.objects.filter(is_active=True).exists()
        and TransportAssignment.objects.filter(is_active=True).exists()
        else "YELLOW"
        if TransportRoute.objects.filter(is_active=True).exists()
        else "RED",
        "hostel": "GREEN"
        if HostelRoom.objects.filter(is_active=True).exists()
        and HostelAllocation.objects.filter(is_active=True).exists()
        else "YELLOW"
        if HostelRoom.objects.filter(is_active=True).exists()
        else "RED",
        "library": "GREEN"
        if LibraryBook.objects.filter(is_active=True).exists()
        and LibraryIssue.objects.filter(status="ISSUED").exists()
        else "YELLOW"
        if LibraryBook.objects.filter(is_active=True).exists()
        else "RED",
        "inventory": "GREEN"
        if InventoryItem.objects.filter(is_active=True).exists()
        and InventoryMovement.objects.exists()
        else "YELLOW"
        if InventoryItem.objects.filter(is_active=True).exists()
        else "RED",
        "activity": "GREEN" if ActivityLog.objects.exists() else "YELLOW",
        "reports": "YELLOW"
        if ScheduledReport.objects.exists() or ReportTemplate.objects.exists()
        else "YELLOW",
        "settings": "GREEN" if PlatformSettings.objects.exists() else "YELLOW",
    }


def _build_role_rows():
    module_state = _module_state_snapshot()
    role_rows = []
    role_counts = dict(
        User.objects.values("role").annotate(total=Count("id")).values_list("role", "total")
    )
    for value, label in User.ROLE_CHOICES:
        role_stub = type("RoleStub", (), {"role": value})
        sections = list(get_role_config(role_stub).get("sections", set()))
        tracked_sections = sorted([key for key in sections if key in module_state])
        if not tracked_sections:
            tracked_sections = ["dashboard"]
        green_modules = sum(1 for key in tracked_sections if module_state.get(key) == "GREEN")
        yellow_modules = sum(1 for key in tracked_sections if module_state.get(key) == "YELLOW")
        red_modules = sum(1 for key in tracked_sections if module_state.get(key) == "RED")
        total_modules = len(tracked_sections) or 1
        completion_pct = round(((green_modules + (0.5 * yellow_modules)) / total_modules) * 100)
        if completion_pct >= 85 and red_modules == 0:
            status = "Complete"
            status_color = "GREEN"
        elif completion_pct >= 45:
            status = "Partial"
            status_color = "YELLOW"
        else:
            status = "Pending"
            status_color = "RED"
        role_rows.append(
            {
                "role": value,
                "label": label,
                "status": status,
                "status_color": status_color,
                "completion_pct": completion_pct,
                "green": green_modules,
                "yellow": yellow_modules,
                "red": red_modules,
                "white": 0,
                "blue": 1
                if value
                in {"RECEPTIONIST", "ROLE_PERMISSION_MANAGER", "REPORT_VIEWER", "SUPER_ADMIN"}
                else 0,
                "assigned_users": role_counts.get(value, 0),
                "tracked_modules": ", ".join(tracked_sections),
                "tracked_section_keys": tracked_sections,
                "module_state": {key: module_state.get(key, "YELLOW") for key in tracked_sections},
            }
        )
    role_rows.sort(
        key=lambda item: (
            item["status"] != "Pending",
            item["status"] != "Partial",
            -item["completion_pct"],
            item["label"],
        )
    )
    return role_rows


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_role_sheet(request):
    role_rows = _build_role_rows()
    context = build_layout_context(request.user, current_section="platform")
    context["role_rows"] = role_rows
    context["role_sheet_summary"] = {
        "complete": sum(1 for row in role_rows if row["status"] == "Complete"),
        "partial": sum(1 for row in role_rows if row["status"] == "Partial"),
        "pending": sum(1 for row in role_rows if row["status"] == "Pending"),
    }
    return render(request, "platform/role_sheet.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_role_detail(request, role):
    role_rows = _build_role_rows()
    row = next((item for item in role_rows if item["role"] == role), None)
    context = build_layout_context(request.user, current_section="platform")
    if not row:
        context["requested_role"] = role
        return render(request, "platform/role_detail.html", context, status=404)
    module_rows = []
    for module_key in row["tracked_section_keys"]:
        state = row["module_state"].get(module_key, "YELLOW")
        module_rows.append(
            {"module": module_key, "state": state, "needs_work": state in {"YELLOW", "RED"}}
        )
    context["role_row"] = row
    context["module_rows"] = module_rows
    return render(request, "platform/role_detail.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_gap_sheet(request):
    gap_rows = [
        {
            "name": "Parent portal maturity",
            "status": "RED",
            "detail": "Child switching, summary cards, alerts, and parent-first workflow.",
        },
        {
            "name": "Student portal maturity",
            "status": "RED",
            "detail": "Student-first dashboard, notices, results, and document tasks.",
        },
        {
            "name": "Academic control center",
            "status": "YELLOW",
            "detail": "Timetable, lesson plan, syllabus progress, substitution, and calendar.",
        },
        {
            "name": "Transport operations",
            "status": "RED",
            "detail": "Routes, trips, vehicle assignment, and daily run sheets.",
        },
        {
            "name": "Hostel operations",
            "status": "RED",
            "detail": "Rooms, occupancy, attendance, mess, and leave workflows.",
        },
        {
            "name": "Library circulation",
            "status": "RED",
            "detail": "Issue/return, fines, due alerts, and student borrowing history.",
        },
        {
            "name": "Lab operations",
            "status": "RED",
            "detail": "Lab booking, equipment, and session workflow.",
        },
        {
            "name": "Inventory lifecycle",
            "status": "YELLOW",
            "detail": "Stock movement, issue/return, low-stock alerts, and approvals.",
        },
        {
            "name": "Fee reconciliation",
            "status": "YELLOW",
            "detail": "Day-close, refunds, concessions, and payment gateway lifecycle.",
        },
        {
            "name": "Communication delivery tracking",
            "status": "YELLOW",
            "detail": "Delivery logs, read status, retries, and channel-wise failures.",
        },
        {
            "name": "Setup wizard",
            "status": "GREEN",
            "detail": "School onboarding flow for classes, staff, subjects, fees, and comms.",
        },
    ]
    context = build_layout_context(request.user, current_section="platform")
    context["gap_rows"] = gap_rows
    return render(request, "platform/gap_sheet.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_academics(request):
    schools = School.objects.order_by("name")
    current_years = AcademicYear.objects.filter(is_current=True).select_related("school")
    classes = AcademicClass.objects.select_related("school", "class_teacher").order_by(
        "school__name", "name", "section"
    )
    subjects = AcademicSubject.objects.select_related("school", "academic_class").order_by(
        "school__name", "academic_class__name", "name"
    )
    allocations = TeacherAllocation.objects.select_related(
        "school", "teacher", "academic_class", "subject"
    ).order_by("school__name", "academic_class__name", "subject__name")

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "academics_counts": {
                "schools": schools.count(),
                "current_years": current_years.count(),
                "classes": classes.count(),
                "subjects": subjects.count(),
                "allocations": allocations.count(),
            },
            "current_years": current_years[:10],
            "recent_classes": classes[:10],
            "recent_subjects": subjects[:10],
            "recent_allocations": allocations[:10],
        }
    )
    return render(request, "platform/academics_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_decision_dashboard(request):
    schools = School.objects.select_related().order_by("name")
    rows = []
    for school in schools:
        snapshot = _school_maturity_snapshot(school)
        rows.append(
            {
                "school": school,
                "score": snapshot["score"],
                "issues": [item["label"] for item in snapshot["checks"] if not item["done"]][:6],
                "current_year": snapshot["current_year"],
                "campuses": snapshot["campus_count"],
                "classes": snapshot["class_count"],
                "subjects": snapshot["subject_count"],
                "allocations": snapshot["allocation_count"],
                "attendance_sessions": snapshot["attendance_sessions"],
                "exams": snapshot["exams"],
                "ledgers": snapshot["ledgers"],
                "notices": snapshot["notices_count"],
                "domains": snapshot["domain_count"],
                "support_open": snapshot["support_open"],
                "subscription_status": snapshot["subscription"].status
                if snapshot["subscription"]
                else "NONE",
            }
        )

    rows.sort(key=lambda item: item["score"])
    context = build_layout_context(request.user, current_section="platform")
    context["decision_rows"] = rows[:50]
    context["decision_summary"] = {
        "schools": len(rows),
        "critical": sum(1 for row in rows if row["score"] < 50),
        "watch": sum(1 for row in rows if 50 <= row["score"] < 80),
        "healthy": sum(1 for row in rows if row["score"] >= 80),
    }
    return render(request, "platform/decision_dashboard.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_setup_wizard(request):
    schools = School.objects.select_related().order_by("name")
    rows = []
    for school in schools:
        snapshot = _school_maturity_snapshot(school)
        rows.append(
            {
                "school": school,
                "completed": snapshot["completed"],
                "total": snapshot["total"],
                "score": snapshot["score"],
                "steps": [
                    {"label": item["label"], "done": item["done"]} for item in snapshot["checks"]
                ],
                "current_year": snapshot["current_year"],
                "subscription_status": snapshot["subscription"].status
                if snapshot["subscription"]
                else "NONE",
                "campus_count": snapshot["campus_count"],
                "domain_count": snapshot["domain_count"],
                "class_master_count": snapshot["class_master_count"],
                "section_master_count": snapshot["section_master_count"],
                "class_count": snapshot["class_count"],
                "subject_count": snapshot["subject_count"],
                "allocation_count": snapshot["allocation_count"],
                "notices_count": snapshot["notices_count"],
            }
        )

    rows.sort(key=lambda item: (item["score"], item["school"].name))
    context = build_layout_context(request.user, current_section="platform")
    context["wizard_rows"] = rows
    context["wizard_summary"] = {
        "schools": len(rows),
        "complete": sum(1 for row in rows if row["score"] == 100),
        "in_progress": sum(1 for row in rows if 0 < row["score"] < 100),
        "not_started": sum(1 for row in rows if row["score"] == 0),
    }
    return render(request, "platform/setup_wizard.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_transport(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "create_route").strip()
        if action == "create_route":
            school_id = (request.POST.get("school_id") or "").strip()
            route_code = (request.POST.get("route_code") or "").strip()
            route_name = (request.POST.get("route_name") or "").strip()
            vehicle_number = (request.POST.get("vehicle_number") or "").strip()
            driver_name = (request.POST.get("driver_name") or "").strip()
            stops_raw = (request.POST.get("stops") or "").strip()
            if (
                not school_id.isdigit()
                or not School.objects.filter(id=int(school_id), is_active=True).exists()
            ):
                messages.error(request, "Valid school is required.")
            elif not route_code:
                messages.error(request, "Route code is required.")
            else:
                school = School.objects.get(id=int(school_id))
                vehicle = None
                if vehicle_number:
                    vehicle, _ = TransportVehicle.objects.get_or_create(
                        school=school, vehicle_no=vehicle_number
                    )
                    if driver_name and not vehicle.driver:
                        driver, _ = TransportDriver.objects.get_or_create(
                            school=school,
                            license_number=f"DL-{vehicle_number}",
                            defaults={"full_name": driver_name},
                        )
                        vehicle.driver = driver
                        vehicle.save()

                route_name_value = f"{route_code} - {route_name}".strip()
                route_name_value = route_name_value.removeprefix("- ").removesuffix(" -")
                route = TransportRoute.objects.create(
                    school=school, name=route_name_value, vehicle=vehicle
                )
                stops = [item.strip() for item in stops_raw.split(",") if item.strip()]
                for i, stop_name in enumerate(stops):
                    TransportStop.objects.create(
                        route=route,
                        name=stop_name,
                        order=i,
                        pickup_time=time(8, 0),
                        drop_time=time(14, 0),
                    )

                messages.success(request, "Transport route created.")
                return redirect("/super-admin/transport/")
        elif action == "assign_student":
            school_id = (request.POST.get("school_id") or "").strip()
            route_id = (request.POST.get("route_id") or "").strip()
            student_id = (request.POST.get("student_id") or "").strip()
            pickup_stop_name = (request.POST.get("pickup_stop") or "").strip()
            fee_amount_raw = (request.POST.get("fee_amount") or "500").strip()
            try:
                fee_amount = Decimal(fee_amount_raw or "0")
            except Exception:
                fee_amount = Decimal("0")
            if not (school_id.isdigit() and route_id.isdigit() and student_id.isdigit()):
                messages.error(request, "School, route, and student are required.")
            else:
                school_id_i = int(school_id)
                route = TransportRoute.objects.filter(
                    id=int(route_id), school_id=school_id_i
                ).first()
                student = Student.objects.filter(
                    id=int(student_id), school_id=school_id_i, is_active=True
                ).first()
                if not route or not student:
                    messages.error(request, "Invalid route or student selection.")
                elif TransportAssignment.objects.filter(student=student, is_active=True).exists():
                    messages.error(request, "Student already has an active route assignment.")
                else:
                    stop = TransportStop.objects.filter(route=route, name=pickup_stop_name).first()
                    if not stop:
                        stop = TransportStop.objects.filter(route=route).first()

                    TransportAssignment.objects.create(
                        route=route,
                        student=student,
                        stop=stop,
                        is_active=True,
                    )
                    student.transport_required = True
                    student.route_number = route.name[:20]
                    student.save(update_fields=["transport_required", "route_number"])
                    _ensure_service_fee_ledger(
                        student=student,
                        school=route.school,
                        service_code="TRANSPORT",
                        service_name="Transport Service",
                        amount=fee_amount,
                    )
                    messages.success(request, "Student assigned to route.")
                    return redirect("/super-admin/transport/")
        elif action == "release_assignment":
            assignment_id = (request.POST.get("assignment_id") or "").strip()
            if not assignment_id.isdigit():
                messages.error(request, "Invalid assignment.")
            else:
                assignment = (
                    TransportAssignment.objects.select_related("student", "route__school")
                    .filter(id=int(assignment_id), is_active=True)
                    .first()
                )
                if not assignment:
                    messages.error(request, "Active assignment not found.")
                else:
                    assignment.is_active = False
                    assignment.save(update_fields=["is_active"])
                    assignment.student.transport_required = False
                    assignment.student.route_number = ""
                    assignment.student.save(update_fields=["transport_required", "route_number"])
                    _create_refund_event(
                        student=assignment.student,
                        school=assignment.route.school,
                        service_type="TRANSPORT",
                        source="transport_release",
                        source_ref=assignment.id,
                    )
                    messages.success(request, "Transport assignment released.")
                    return redirect("/super-admin/transport/")

    schools = School.objects.order_by("name")
    rows = []
    routes = TransportRoute.objects.select_related("school").filter(is_active=True)
    routes_by_school = {}
    for route in routes:
        routes_by_school.setdefault(route.school_id, []).append(route)

    total_transport_students = Student.objects.filter(
        transport_required=True, is_active=True
    ).count()
    active_assignments = (
        TransportAssignment.objects.select_related("school", "route", "student")
        .filter(active=True)
        .order_by("-created_at")
    )
    assignments_by_school = {}
    for assignment in active_assignments:
        assignments_by_school.setdefault(assignment.school_id, []).append(assignment)
    total_routes = set()
    total_buses = set()
    for school in schools:
        school_routes = routes_by_school.get(school.id, [])
        school_assignments = assignments_by_school.get(school.id, [])
        transport_students = Student.objects.filter(
            school=school, transport_required=True, is_active=True
        )
        route_names = sorted({r.name for r in school_routes if r.name})
        bus_numbers = sorted({r.vehicle.vehicle_no for r in school_routes if r.vehicle})
        pickups = sorted({s.name for r in school_routes for s in r.stops.all() if s.name})
        rows.append(
            {
                "school": school,
                "transport_students": transport_students.count(),
                "route_records": len(school_routes),
                "route_count": len(route_names),
                "bus_count": len(bus_numbers),
                "pickup_count": len(pickups),
                "assignment_count": len(school_assignments),
                "routes": route_names[:8],
                "buses": bus_numbers[:8],
                "pickups": pickups[:8],
                "status": "Ready" if route_names and school_assignments else "Needs setup",
            }
        )
        total_routes.update(route_names)
        total_buses.update(bus_numbers)

    rows.sort(key=lambda item: (-item["transport_students"], item["school"].name))
    context = build_layout_context(request.user, current_section="platform")
    context["transport_summary"] = {
        "schools": len(rows),
        "students": total_transport_students,
        "routes": len(total_routes),
        "buses": len(total_buses),
        "assignments": active_assignments.count(),
        "ready": sum(1 for row in rows if row["status"] == "Ready"),
        "needs_setup": sum(1 for row in rows if row["status"] == "Needs setup"),
    }
    context["schools"] = schools.filter(is_active=True)
    context["transport_routes"] = routes.order_by("school__name", "name")[:300]
    context["transport_students"] = (
        Student.objects.filter(is_active=True)
        .select_related("school")
        .order_by("first_name", "last_name")[:400]
    )
    context["open_transport_assignments"] = active_assignments[:200]
    context["transport_rows"] = rows
    return render(request, "platform/transport_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_hostel(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "create_room").strip()
        if action == "create_room":
            school_id = (request.POST.get("school_id") or "").strip()
            room_number = (request.POST.get("room_number") or "").strip()
            block_name = (request.POST.get("block_name") or "").strip()
            try:
                bed_capacity = int((request.POST.get("bed_capacity") or "1").strip())
            except Exception:
                bed_capacity = 0
            if (
                not school_id.isdigit()
                or not School.objects.filter(id=int(school_id), is_active=True).exists()
            ):
                messages.error(request, "Valid school is required.")
            elif not room_number:
                messages.error(request, "Room number is required.")
            elif bed_capacity <= 0:
                messages.error(request, "Bed capacity should be greater than 0.")
            else:
                school = School.objects.get(id=int(school_id))
                hostel, _ = Hostel.objects.get_or_create(
                    school=school, name=f"Hostel {school.code}", defaults={"hostel_type": "COED"}
                )
                room = HostelRoom.objects.create(
                    hostel=hostel,
                    room_number=room_number,
                    room_type=block_name,
                    capacity=bed_capacity,
                    is_active=True,
                )
                for i in range(1, bed_capacity + 1):
                    HostelBed.objects.create(room=room, bed_number=str(i))

                messages.success(request, "Hostel room created.")
                return redirect("/super-admin/hostel/")
        elif action == "allocate_student":
            school_id = (request.POST.get("school_id") or "").strip()
            room_id = (request.POST.get("room_id") or "").strip()
            student_id = (request.POST.get("student_id") or "").strip()
            _bed_label = (request.POST.get("bed_label") or "").strip()
            fee_amount_raw = (request.POST.get("fee_amount") or "1200").strip()
            try:
                fee_amount = Decimal(fee_amount_raw or "0")
            except Exception:
                fee_amount = Decimal("0")
            if not (school_id.isdigit() and room_id.isdigit() and student_id.isdigit()):
                messages.error(request, "School, room, and student are required.")
            else:
                school_id_i = int(school_id)
                room = HostelRoom.objects.filter(
                    id=int(room_id), hostel__school_id=school_id_i, is_active=True
                ).first()
                student = Student.objects.filter(
                    id=int(student_id), school_id=school_id_i, is_active=True
                ).first()
                if not room or not student:
                    messages.error(request, "Invalid room or student selection.")
                elif room.beds.filter(is_occupied=True).count() >= room.capacity:
                    messages.error(request, "Selected room is full.")
                elif HostelAllocation.objects.filter(student=student, is_active=True).exists():
                    messages.error(request, "Student already has active hostel allocation.")
                else:
                    with transaction.atomic():
                        bed = room.beds.filter(is_occupied=False).first()
                        if not bed:
                            messages.error(request, "No available beds.")
                            return redirect("/super-admin/hostel/")

                        HostelAllocation.objects.create(
                            student=student,
                            hostel=room.hostel,
                            room=room,
                            bed=bed,
                            is_active=True,
                        )
                        bed.is_occupied = True
                        bed.save(update_fields=["is_occupied"])
                        student.hostel_required = True
                        student.save(update_fields=["hostel_required"])
                        _ensure_service_fee_ledger(
                            student=student,
                            school=room.hostel.school,
                            service_code="HOSTEL",
                            service_name="Hostel Service",
                            amount=fee_amount,
                        )
                    messages.success(request, "Student allocated to hostel room.")
                    return redirect("/super-admin/hostel/")
        elif action == "release_allocation":
            allocation_id = (request.POST.get("allocation_id") or "").strip()
            if not allocation_id.isdigit():
                messages.error(request, "Invalid hostel allocation.")
            else:
                allocation = (
                    HostelAllocation.objects.select_related(
                        "room", "student", "bed", "hostel__school"
                    )
                    .filter(id=int(allocation_id), is_active=True)
                    .first()
                )
                if not allocation:
                    messages.error(request, "Active allocation not found.")
                else:
                    with transaction.atomic():
                        allocation.is_active = False
                        allocation.save(update_fields=["is_active"])
                        if allocation.bed:
                            allocation.bed.is_occupied = False
                            allocation.bed.save(update_fields=["is_occupied"])
                        allocation.student.hostel_required = False
                        allocation.student.save(update_fields=["hostel_required"])
                        _create_refund_event(
                            student=allocation.student,
                            school=allocation.hostel.school,
                            service_type="HOSTEL",
                            source="hostel_release",
                            source_ref=allocation.id,
                        )
                    messages.success(request, "Hostel allocation released.")
                    return redirect("/super-admin/hostel/")

    schools = School.objects.order_by("name")
    rooms = HostelRoom.objects.select_related("hostel__school").filter(is_active=True)
    rooms_by_school = {}
    for room in rooms:
        rooms_by_school.setdefault(room.hostel.school_id, []).append(room)

    rows = []
    active_allocations = (
        HostelAllocation.objects.select_related("hostel__school", "room", "student")
        .filter(is_active=True)
        .order_by("-id")
    )
    allocations_by_school = {}
    for allocation in active_allocations:
        allocations_by_school.setdefault(allocation.hostel.school_id, []).append(allocation)
    total_hostel_students = Student.objects.filter(hostel_required=True, is_active=True).count()
    total_rooms = set()
    total_wardens = set()
    for school in schools:
        hostel_students = Student.objects.filter(
            school=school, hostel_required=True, is_active=True
        )
        school_rooms = rooms_by_school.get(school.id, [])
        school_allocations = allocations_by_school.get(school.id, [])
        room_numbers = sorted({r.room_number for r in school_rooms if r.room_number})
        warden_names = sorted({r.hostel.warden_name for r in school_rooms if r.hostel.warden_name})
        rows.append(
            {
                "school": school,
                "hostel_students": hostel_students.count(),
                "room_records": len(school_rooms),
                "room_count": len(room_numbers),
                "warden_count": len(warden_names),
                "mess_count": 0,
                "allocation_count": len(school_allocations),
                "rooms": room_numbers[:8],
                "wardens": warden_names[:8],
                "mess_plans": [],
                "status": "Ready" if room_numbers and school_allocations else "Needs setup",
            }
        )
        total_rooms.update(room_numbers)
        total_wardens.update(warden_names)

    rows.sort(key=lambda item: (-item["hostel_students"], item["school"].name))
    context = build_layout_context(request.user, current_section="platform")
    context["hostel_summary"] = {
        "schools": len(rows),
        "students": total_hostel_students,
        "rooms": len(total_rooms),
        "wardens": len(total_wardens),
        "allocations": active_allocations.count(),
        "ready": sum(1 for row in rows if row["status"] == "Ready"),
        "needs_setup": sum(1 for row in rows if row["status"] == "Needs setup"),
    }
    context["schools"] = schools.filter(is_active=True)
    context["hostel_rooms"] = rooms.order_by("hostel__school__name", "room_number")[:300]
    context["hostel_students"] = (
        Student.objects.filter(is_active=True)
        .select_related("school")
        .order_by("first_name", "last_name")[:400]
    )
    context["open_hostel_allocations"] = active_allocations[:200]
    context["hostel_rows"] = rows
    return render(request, "platform/hostel_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_library(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "create_book").strip()
        if action == "create_book":
            school_id = (request.POST.get("school_id") or "").strip()
            accession_no = (request.POST.get("accession_no") or "").strip()
            title = (request.POST.get("title") or "").strip()
            author_name = (request.POST.get("author") or "").strip()
            category_name = (request.POST.get("category") or "").strip()
            try:
                total_copies = int((request.POST.get("total_copies") or "1").strip())
            except Exception:
                total_copies = 0
            if (
                not school_id.isdigit()
                or not School.objects.filter(id=int(school_id), is_active=True).exists()
            ):
                messages.error(request, "Valid school is required.")
            elif not accession_no or not title:
                messages.error(request, "Accession and title are required.")
            elif total_copies <= 0:
                messages.error(request, "Total copies should be greater than 0.")
            else:
                school = School.objects.get(id=int(school_id))
                category = None
                if category_name:
                    category, _ = LibraryCategory.objects.get_or_create(
                        school=school, name=category_name
                    )
                author = None
                if author_name:
                    author, _ = LibraryAuthor.objects.get_or_create(school=school, name=author_name)

                LibraryBook.objects.create(
                    school=school,
                    title=title,
                    isbn=accession_no,
                    category=category,
                    author=author,
                    total_copies=total_copies,
                    available_copies=total_copies,
                    is_active=True,
                )
                messages.success(request, "Library book created.")
                return redirect("/super-admin/library/")
        elif action == "issue_book":
            school_id = (request.POST.get("school_id") or "").strip()
            book_id = (request.POST.get("book_id") or "").strip()
            student_id = (request.POST.get("student_id") or "").strip()
            due_on_raw = (request.POST.get("due_on") or "").strip()
            if not (school_id.isdigit() and book_id.isdigit() and student_id.isdigit()):
                messages.error(request, "School, book, and student are required.")
            else:
                school_id_i = int(school_id)
                book = LibraryBook.objects.filter(
                    id=int(book_id), school_id=school_id_i, is_active=True
                ).first()
                student = Student.objects.filter(
                    id=int(student_id), school_id=school_id_i, is_active=True
                ).first()
                if not book or not student:
                    messages.error(request, "Invalid book or student selection.")
                elif book.available_copies <= 0:
                    messages.error(request, "No available copies for selected book.")
                else:
                    due_date = timezone.localdate() + timedelta(days=14)
                    if due_on_raw:
                        try:
                            due_date = datetime.strptime(due_on_raw, "%Y-%m-%d").date()
                        except ValueError:
                            pass

                    LibraryIssue.objects.create(
                        book=book,
                        student=student,
                        status="ISSUED",
                        issue_date=timezone.localdate(),
                        due_date=due_date,
                    )
                    book.available_copies = max(0, book.available_copies - 1)
                    book.save(update_fields=["available_copies"])
                    messages.success(request, "Book issued.")
                    return redirect("/super-admin/library/")
        elif action == "return_book":
            issue_id = (request.POST.get("issue_id") or "").strip()
            fine_amount_raw = (request.POST.get("fine_amount") or "0").strip()
            try:
                fine_amount = Decimal(fine_amount_raw or "0")
            except Exception:
                fine_amount = Decimal("0")
            if not issue_id.isdigit():
                messages.error(request, "Invalid issue record.")
            else:
                issue = (
                    LibraryIssue.objects.select_related("book")
                    .filter(id=int(issue_id), status="ISSUED")
                    .first()
                )
                if not issue:
                    messages.error(request, "Issue record not found or already closed.")
                else:
                    auto_fine = Decimal("0")
                    if issue.due_date and timezone.localdate() > issue.due_date:
                        overdue_days = (timezone.localdate() - issue.due_date).days
                        auto_fine = Decimal(overdue_days)
                    issue.status = "RETURNED"
                    issue.return_date = timezone.localdate()
                    issue.fine_amount = max(fine_amount, auto_fine)
                    issue.save(update_fields=["status", "return_date", "fine_amount"])
                    issue.book.available_copies = min(
                        issue.book.total_copies, issue.book.available_copies + 1
                    )
                    issue.book.save(update_fields=["available_copies"])
                    messages.success(request, "Book returned.")
                    return redirect("/super-admin/library/")
        elif action == "mark_lost":
            issue_id = (request.POST.get("issue_id") or "").strip()
            fine_amount_raw = (request.POST.get("fine_amount") or "0").strip()
            try:
                fine_amount = Decimal(fine_amount_raw or "0")
            except Exception:
                fine_amount = Decimal("0")
            if not issue_id.isdigit():
                messages.error(request, "Invalid issue record.")
            else:
                issue = (
                    LibraryIssue.objects.select_related("book")
                    .filter(id=int(issue_id), status="ISSUED")
                    .first()
                )
                if not issue:
                    messages.error(request, "Issue record not found or already closed.")
                else:
                    issue.status = "LOST"
                    issue.return_date = timezone.localdate()
                    issue.fine_amount = fine_amount
                    issue.save(update_fields=["status", "return_date", "fine_amount"])
                    issue.book.total_copies = max(0, issue.book.total_copies - 1)
                    issue.book.available_copies = min(
                        issue.book.available_copies, issue.book.total_copies
                    )
                    issue.book.save(update_fields=["total_copies", "available_copies"])
                    messages.success(request, "Issue marked as lost.")
                    return redirect("/super-admin/library/")

    schools = School.objects.order_by("name")
    books = LibraryBook.objects.select_related("school").filter(is_active=True)
    books_by_school = {}
    for book in books:
        books_by_school.setdefault(book.school_id, []).append(book)

    rows = []
    total_students = Student.objects.filter(is_active=True).count()
    total_books = books.count()
    issues = LibraryIssue.objects.select_related("book__school", "book", "student").all()
    issues_by_school = {}
    open_issues = []
    for issue in issues:
        issues_by_school.setdefault(issue.book.school_id, []).append(issue)
        if issue.status == "ISSUED":
            open_issues.append(issue)
    for school in schools:
        school_books = books_by_school.get(school.id, [])
        school_issues = issues_by_school.get(school.id, [])
        issued = sum(1 for i in school_issues if i.status == "ISSUED")
        returned = sum(1 for i in school_issues if i.status == "RETURNED")
        lost = sum(1 for i in school_issues if i.status == "LOST")
        fine_count = sum((i.fine_amount or Decimal("0")) for i in school_issues)
        rows.append(
            {
                "school": school,
                "students": Student.objects.filter(school=school, is_active=True).count(),
                "issue_count": issued,
                "return_count": returned,
                "lost_count": lost,
                "fine_count": fine_count,
                "borrowing_count": issued,
                "status": "Ready" if school_books else "Needs setup",
                "book_count": len(school_books),
            }
        )

    context = build_layout_context(request.user, current_section="platform")
    context["library_summary"] = {
        "schools": len(rows),
        "students": total_students,
        "books": total_books,
        "issued_open": len(open_issues),
        "fines_total": sum((issue.fine_amount or Decimal("0")) for issue in issues),
        "ready": sum(1 for row in rows if row["status"] == "Ready"),
        "needs_setup": sum(1 for row in rows if row["status"] == "Needs setup"),
    }
    context["schools"] = schools.filter(is_active=True)
    context["library_books"] = books[:200]
    context["library_students"] = (
        Student.objects.filter(is_active=True)
        .select_related("school")
        .order_by("first_name", "last_name")[:300]
    )
    context["open_library_issues"] = open_issues[:150]
    context["library_rows"] = rows
    return render(request, "platform/library_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_lab(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "create_lab").strip()
        if action == "create_lab":
            school_id = (request.POST.get("school_id") or "").strip()
            room_number = (request.POST.get("room_number") or "").strip()
            name = (request.POST.get("name") or "").strip()
            in_charge_name = (request.POST.get("in_charge_name") or "").strip()
            try:
                capacity = int((request.POST.get("capacity") or "30").strip())
            except Exception:
                capacity = 30
            if (
                not school_id.isdigit()
                or not School.objects.filter(id=int(school_id), is_active=True).exists()
            ):
                messages.error(request, "Valid school is required.")
            elif not room_number or not name:
                messages.error(request, "Room number and name are required.")
            elif LabRoom.objects.filter(school_id=int(school_id), room_number=room_number).exists():
                messages.error(request, "Room number already exists for this school.")
            else:
                LabRoom.objects.create(
                    school_id=int(school_id),
                    room_number=room_number,
                    name=name,
                    capacity=capacity,
                    in_charge_name=in_charge_name,
                    is_active=True,
                )
                messages.success(request, "Lab room created.")
                return redirect("/super-admin/lab/")
        elif action == "create_equipment":
            school_id = (request.POST.get("school_id") or "").strip()
            lab_id = (request.POST.get("lab_id") or "").strip()
            name = (request.POST.get("name") or "").strip()
            sku = (request.POST.get("sku") or "").strip()
            try:
                quantity = int((request.POST.get("quantity") or "1").strip())
            except Exception:
                quantity = 1
            if not (school_id.isdigit() and lab_id.isdigit()):
                messages.error(request, "School and lab are required.")
            elif not name:
                messages.error(request, "Equipment name is required.")
            else:
                school_id_i = int(school_id)
                lab = LabRoom.objects.filter(
                    id=int(lab_id), school_id=school_id_i, is_active=True
                ).first()
                if not lab:
                    messages.error(request, "Invalid lab selection.")
                else:
                    LabEquipment.objects.create(
                        school_id=school_id_i,
                        lab=lab,
                        name=name,
                        sku=sku,
                        quantity=quantity,
                        is_active=True,
                    )
                    messages.success(request, "Equipment added to lab.")
                    return redirect("/super-admin/lab/")

    schools = School.objects.order_by("name")
    labs = LabRoom.objects.select_related("school").filter(is_active=True)
    equipments = LabEquipment.objects.select_related("school", "lab").filter(is_active=True)
    bookings = LabBooking.objects.select_related("school", "lab", "booked_by").all()

    labs_by_school = {}
    for lab in labs:
        labs_by_school.setdefault(lab.school_id, []).append(lab)

    equipments_by_school = {}
    for eq in equipments:
        equipments_by_school.setdefault(eq.school_id, []).append(eq)

    bookings_by_school = {}
    for booking in bookings:
        bookings_by_school.setdefault(booking.school_id, []).append(booking)

    rows = []
    total_students = 0
    for school in schools:
        students = Student.objects.filter(school=school, is_active=True)
        school_labs = labs_by_school.get(school.id, [])
        school_equipments = equipments_by_school.get(school.id, [])
        school_bookings = bookings_by_school.get(school.id, [])

        rows.append(
            {
                "school": school,
                "students": students.count(),
                "lab_count": len(school_labs),
                "equipment_count": sum(eq.quantity for eq in school_equipments),
                "booking_count": len(school_bookings),
                "status": "Ready" if school_labs else "Needs setup",
            }
        )
        total_students += students.count()

    context = build_layout_context(request.user, current_section="platform")
    context["lab_summary"] = {
        "schools": len(rows),
        "students": total_students,
        "labs": labs.count(),
        "equipments": sum(eq.quantity for eq in equipments),
        "bookings": bookings.count(),
        "ready": sum(1 for row in rows if row["status"] == "Ready"),
        "needs_setup": sum(1 for row in rows if row["status"] == "Needs setup"),
    }
    context["schools"] = schools.filter(is_active=True)
    context["labs"] = labs.order_by("school__name", "name")[:300]
    context["equipments"] = equipments.order_by("lab__name", "name")[:300]
    context["lab_bookings"] = bookings[:200]
    context["lab_rows"] = rows
    return render(request, "platform/lab_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_inventory(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "create_item").strip()
        if action == "create_item":
            school_id = (request.POST.get("school_id") or "").strip()
            sku = (request.POST.get("sku") or "").strip()
            name = (request.POST.get("name") or "").strip()
            category = (request.POST.get("category") or "").strip()
            unit = (request.POST.get("unit") or "unit").strip()
            try:
                quantity_on_hand = Decimal((request.POST.get("quantity_on_hand") or "0").strip())
                reorder_level = Decimal((request.POST.get("reorder_level") or "0").strip())
            except Exception:
                quantity_on_hand = Decimal("0")
                reorder_level = Decimal("0")
            if (
                not school_id.isdigit()
                or not School.objects.filter(id=int(school_id), is_active=True).exists()
            ):
                messages.error(request, "Valid school is required.")
            elif not sku or not name:
                messages.error(request, "SKU and item name are required.")
            elif InventoryItem.objects.filter(school_id=int(school_id), sku=sku).exists():
                messages.error(request, "SKU already exists for this school.")
            else:
                InventoryItem.objects.create(
                    school_id=int(school_id),
                    sku=sku,
                    name=name,
                    category=category,
                    quantity_on_hand=quantity_on_hand,
                    reorder_level=reorder_level,
                    unit=unit or "unit",
                    is_active=True,
                )
                messages.success(request, "Inventory item created.")
                return redirect("/super-admin/inventory/")
        elif action == "create_vendor":
            school_id = (request.POST.get("school_id") or "").strip()
            name = (request.POST.get("name") or "").strip()
            contact_person = (request.POST.get("contact_person") or "").strip()
            phone = (request.POST.get("phone") or "").strip()
            email = (request.POST.get("email") or "").strip()
            gstin = (request.POST.get("gstin") or "").strip()
            if (
                not school_id.isdigit()
                or not School.objects.filter(id=int(school_id), is_active=True).exists()
            ):
                messages.error(request, "Valid school is required.")
            elif not name:
                messages.error(request, "Vendor name is required.")
            elif InventoryVendor.objects.filter(school_id=int(school_id), name=name).exists():
                messages.error(request, "Vendor name already exists for this school.")
            else:
                InventoryVendor.objects.create(
                    school_id=int(school_id),
                    name=name,
                    contact_person=contact_person,
                    phone=phone,
                    email=email,
                    gstin=gstin,
                    is_active=True,
                )
                messages.success(request, "Vendor created.")
                return redirect("/super-admin/inventory/")
        elif action == "create_po":
            school_id = (request.POST.get("school_id") or "").strip()
            vendor_id = (request.POST.get("vendor_id") or "").strip()
            item_id = (request.POST.get("item_id") or "").strip()
            po_number = (request.POST.get("po_number") or "").strip()
            notes = (request.POST.get("notes") or "").strip()
            try:
                quantity = Decimal((request.POST.get("quantity") or "0").strip())
                unit_cost = Decimal((request.POST.get("unit_cost") or "0").strip())
            except Exception:
                quantity = Decimal("0")
                unit_cost = Decimal("0")
            if not (school_id.isdigit() and vendor_id.isdigit() and item_id.isdigit()):
                messages.error(request, "School, vendor, and item are required.")
            elif not po_number:
                messages.error(request, "PO number is required.")
            elif quantity <= 0:
                messages.error(request, "PO quantity should be greater than 0.")
            elif InventoryPurchaseOrder.objects.filter(
                school_id=int(school_id), po_number=po_number
            ).exists():
                messages.error(request, "PO number already exists for this school.")
            else:
                school_id_i = int(school_id)
                vendor = InventoryVendor.objects.filter(
                    id=int(vendor_id), school_id=school_id_i, is_active=True
                ).first()
                item = InventoryItem.objects.filter(
                    id=int(item_id), school_id=school_id_i, is_active=True
                ).first()
                if not vendor or not item:
                    messages.error(request, "Invalid vendor or item.")
                else:
                    InventoryPurchaseOrder.objects.create(
                        school_id=school_id_i,
                        vendor=vendor,
                        item=item,
                        po_number=po_number,
                        quantity=quantity,
                        unit_cost=unit_cost,
                        status="PLACED",
                        notes=notes,
                    )
                    messages.success(request, "Purchase order created.")
                    return redirect("/super-admin/inventory/")
        elif action == "receive_po":
            po_id = (request.POST.get("po_id") or "").strip()
            if not po_id.isdigit():
                messages.error(request, "Invalid PO record.")
            else:
                po = (
                    InventoryPurchaseOrder.objects.select_related("item")
                    .filter(id=int(po_id))
                    .first()
                )
                if not po:
                    messages.error(request, "PO not found.")
                elif po.status == "RECEIVED":
                    messages.error(request, "PO already received.")
                else:
                    po.item.quantity_on_hand = po.item.quantity_on_hand + po.quantity
                    po.item.save(update_fields=["quantity_on_hand", "updated_at"])
                    InventoryMovement.objects.create(
                        school=po.school,
                        item=po.item,
                        movement_type="IN",
                        quantity=po.quantity,
                        notes=f"PO {po.po_number} received",
                    )
                    po.status = "RECEIVED"
                    po.received_on = timezone.localdate()
                    po.save(update_fields=["status", "received_on"])
                    messages.success(request, "PO received and stock updated.")
                    return redirect("/super-admin/inventory/")
        elif action == "move_stock":
            school_id = (request.POST.get("school_id") or "").strip()
            item_id = (request.POST.get("item_id") or "").strip()
            movement_type = (request.POST.get("movement_type") or "").strip().upper()
            notes = (request.POST.get("notes") or "").strip()
            try:
                qty = Decimal((request.POST.get("quantity") or "0").strip())
            except Exception:
                qty = Decimal("0")
            if not (school_id.isdigit() and item_id.isdigit()):
                messages.error(request, "School and item are required.")
            elif movement_type not in {"IN", "OUT", "ADJUST"}:
                messages.error(request, "Invalid movement type.")
            elif qty <= 0:
                messages.error(request, "Quantity should be greater than 0.")
            else:
                school_id_i = int(school_id)
                item = InventoryItem.objects.filter(
                    id=int(item_id), school_id=school_id_i, is_active=True
                ).first()
                if not item:
                    messages.error(request, "Invalid item selection.")
                else:
                    if movement_type == "IN":
                        item.quantity_on_hand = item.quantity_on_hand + qty
                    elif movement_type == "OUT":
                        if item.quantity_on_hand < qty:
                            messages.error(request, "Insufficient stock for OUT movement.")
                            return redirect("/super-admin/inventory/")
                        item.quantity_on_hand = item.quantity_on_hand - qty
                    else:
                        item.quantity_on_hand = qty
                    item.save(update_fields=["quantity_on_hand", "updated_at"])
                    InventoryMovement.objects.create(
                        school_id=school_id_i,
                        item=item,
                        movement_type=movement_type,
                        quantity=qty,
                        notes=notes,
                    )
                    messages.success(request, "Stock movement recorded.")
                    return redirect("/super-admin/inventory/")

    schools = School.objects.order_by("name")
    items = InventoryItem.objects.select_related("school").filter(is_active=True)
    items_by_school = {}
    for item in items:
        items_by_school.setdefault(item.school_id, []).append(item)

    rows = []
    total_students = Student.objects.filter(is_active=True).count()
    movements = InventoryMovement.objects.select_related("school", "item").all()
    vendors = InventoryVendor.objects.select_related("school").filter(is_active=True)
    purchase_orders = InventoryPurchaseOrder.objects.select_related(
        "school", "vendor", "item"
    ).all()
    movements_by_school = {}
    for movement in movements:
        movements_by_school.setdefault(movement.school_id, []).append(movement)
    for school in schools:
        school_items = items_by_school.get(school.id, [])
        school_movements = movements_by_school.get(school.id, [])
        issue_count = sum(1 for m in school_movements if m.movement_type == "OUT")
        return_count = sum(1 for m in school_movements if m.movement_type == "IN")
        low_stock_count = sum(
            1 for item in school_items if item.quantity_on_hand <= item.reorder_level
        )
        rows.append(
            {
                "school": school,
                "stock_items": len(school_items),
                "issue_count": issue_count,
                "return_count": return_count,
                "low_stock_count": low_stock_count,
                "status": "Ready" if school_items else "Needs setup",
            }
        )

    context = build_layout_context(request.user, current_section="platform")
    context["inventory_summary"] = {
        "schools": len(rows),
        "students": total_students,
        "low_stock": sum(row["low_stock_count"] for row in rows),
        "movements": movements.count(),
        "vendors": vendors.count(),
        "pos_open": purchase_orders.exclude(status__in=["RECEIVED", "CANCELLED"]).count(),
        "ready": sum(1 for row in rows if row["status"] == "Ready"),
        "needs_setup": sum(1 for row in rows if row["status"] == "Needs setup"),
    }
    context["schools"] = schools.filter(is_active=True)
    context["inventory_items"] = items[:300]
    context["inventory_movements"] = movements[:150]
    context["inventory_vendors"] = vendors[:300]
    context["inventory_purchase_orders"] = purchase_orders[:200]
    context["inventory_rows"] = rows
    return render(request, "platform/inventory_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_fee_reconciliation(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "process_refund":
            refund_id = (request.POST.get("refund_id") or "").strip()
            decision = (request.POST.get("decision") or "").strip()
            if not refund_id.isdigit():
                messages.error(request, "Invalid refund case.")
            elif decision not in {"APPROVED", "REJECTED"}:
                messages.error(request, "Invalid decision.")
            else:
                refund = ServiceRefundEvent.objects.filter(id=int(refund_id), status="OPEN").first()
                if not refund:
                    messages.error(request, "Refund case not found or already processed.")
                else:
                    refund.status = decision
                    refund.save(update_fields=["status"])
                    messages.success(request, f"Refund case marked as {decision}.")
                    return redirect("/super-admin/fees/")

    schools = School.objects.order_by("name")
    rows = []
    total_ledgers = 0
    total_payments = 0
    refund_events = ServiceRefundEvent.objects.select_related("school").all()
    refund_by_school = {}
    for event in refund_events:
        refund_by_school.setdefault(event.school_id, []).append(event)
    for school in schools:
        ledgers = StudentFeeLedger.objects.filter(school=school)
        payments = FeePayment.objects.filter(school=school)
        school_refunds = refund_by_school.get(school.id, [])
        paid_students = payments.values("student_id").distinct().count()
        rows.append(
            {
                "school": school,
                "ledger_count": ledgers.count(),
                "payment_count": payments.count(),
                "paid_students": paid_students,
                "refund_count": len(school_refunds),
                "refund_amount": sum(
                    (item.recommended_refund or Decimal("0")) for item in school_refunds
                ),
                "concession_count": 0,
                "gateway_count": 0,
                "status": "Ready" if payments.exists() else "Needs setup",
                "notes": "Refund policy analytics enabled for transport/hostel discontinuation.",
            }
        )
        total_ledgers += ledgers.count()
        total_payments += payments.count()

    rows.sort(key=lambda item: (-item["payment_count"], item["school"].name))
    context = build_layout_context(request.user, current_section="platform")
    context["fee_summary"] = {
        "schools": len(rows),
        "ledgers": total_ledgers,
        "payments": total_payments,
        "refund_cases": refund_events.count(),
        "refund_exposure": sum(
            (event.recommended_refund or Decimal("0")) for event in refund_events
        ),
        "ready": sum(1 for row in rows if row["status"] == "Ready"),
        "needs_setup": sum(1 for row in rows if row["status"] == "Needs setup"),
    }
    context["fee_rows"] = rows
    context["open_refunds"] = [e for e in refund_events if e.status == "OPEN"][:200]
    return render(request, "platform/fee_reconciliation_hub.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_communication_logs(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "retry":
            log_id = (request.POST.get("log_id") or "").strip()
            if not log_id.isdigit():
                messages.error(request, "Invalid log entry.")
            else:
                log = MessageDeliveryLog.objects.filter(id=int(log_id)).first()
                if not log:
                    messages.error(request, "Log entry not found.")
                elif log.status != "FAILED":
                    messages.error(request, "Only failed messages can be retried.")
                else:
                    log.status = "QUEUED"
                    log.attempt_count += 1
                    log.error = ""
                    log.save(update_fields=["status", "attempt_count", "error"])
                    messages.success(request, "Message requeued for delivery.")
                    return redirect("/super-admin/communication-logs/")

    logs = MessageDeliveryLog.objects.select_related("campaign", "campaign__school").all()
    _stats = {
        "total": logs.count(),
        "sent": logs.filter(status="SENT").count(),
        "failed": logs.filter(status="FAILED").count(),
        "queued": logs.filter(status="QUEUED").count(),
    }


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_system_ops(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "save_config":
            key = (request.POST.get("key") or "").strip()
            value = (request.POST.get("value") or "").strip()
            desc = (request.POST.get("description") or "").strip()
            is_secret = request.POST.get("is_secret") == "on"
            if key:
                ServiceConfiguration.objects.update_or_create(
                    key=key, defaults={"value": value, "description": desc, "is_secret": is_secret}
                )
                messages.success(request, f"Configuration '{key}' saved.")
            return redirect("/super-admin/system/")

        elif action == "delete_config":
            config_id = (request.POST.get("config_id") or "").strip()
            if config_id.isdigit():
                ServiceConfiguration.objects.filter(id=int(config_id)).delete()
                messages.success(request, "Configuration deleted.")
            return redirect("/super-admin/system/")

    backups = SystemBackup.objects.select_related("created_by").all()[:100]
    configs = ServiceConfiguration.objects.all()

    # System info (mocked for demo)
    sys_info = {
        "os": "Windows Server / Linux Cluster",
        "python": "3.11.x",
        "django": "4.2.x",
        "db": "PostgreSQL / SQLite",
        "disk_usage": "45%",
        "memory_usage": "2.4 GB / 8 GB",
        "last_backup": backups.first().created_at if backups.exists() else "Never",
    }

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "backups": backups,
            "configs": configs,
            "sys_info": sys_info,
        }
    )
    return render(request, "platform/system_ops.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def super_admin_backup_trigger(request):
    if request.method == "POST":
        # Mocking backup process
        from django.core.files.base import ContentFile

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"school_erp_backup_{timestamp}.sql"

        backup = SystemBackup.objects.create(
            filename=filename,
            status="PENDING",
            created_by=request.user,
            notes=request.POST.get("notes", ""),
        )

        try:
            # For demo: create a dummy content
            dummy_content = f"-- School ERP SQL Dump\n-- Date: {timezone.now()}\n-- Total Schools: {School.objects.count()}\n"
            backup.file.save(filename, ContentFile(dummy_content))
            backup.status = "COMPLETED"
            backup.size_bytes = len(dummy_content)
            backup.save()
            messages.success(request, f"Backup '{filename}' completed successfully.")
        except Exception as e:
            backup.status = "FAILED"
            backup.notes = f"Error: {str(e)}"
            backup.save()
            messages.error(request, f"Backup failed: {str(e)}")

    return redirect("/super-admin/system/")
