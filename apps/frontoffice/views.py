from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import User
from apps.admissions.models import AdmissionApplication
from apps.core.permissions import has_permission, role_required
from apps.core.tenancy import (
    allowed_school_ids_for_user,
    school_scope_for_user,
    selected_school_for_request,
)
from apps.core.ui import build_layout_context
from apps.schools.email_utils import send_email_via_school_smtp
from apps.schools.models import SchoolCommunicationSettings
from apps.students.documents import missing_documents
from apps.students.models import Student

from .models import (
    CallLog,
    Enquiry,
    EnquiryFollowUp,
    MeetingRequest,
    MessageCampaign,
    MessageDeliveryLog,
    MessageTemplate,
    VisitorLog,
)


def _school_scope(user):
    return school_scope_for_user(user)


def _selected_school(request):
    return selected_school_for_request(request)


def _school_ids_for_user(user):
    return allowed_school_ids_for_user(user)


def _require_school(request, *, redirect_url="/frontoffice/"):
    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a valid school first.")
        return None, redirect(redirect_url)
    return school, None


def _log_delivery_event(log: MessageDeliveryLog, *, status: str, error: str = ""):
    log.status = status
    log.error = error
    log.attempt_count = log.attempt_count + 1
    log.last_attempt_at = timezone.now()
    if status == "SENT" and log.delivered_at is None:
        log.delivered_at = log.last_attempt_at
    log.save(update_fields=["status", "error", "attempt_count", "last_attempt_at", "delivered_at"])
    return log


def build_frontoffice_dashboard_context(request, *, current_section="frontoffice"):
    school = _selected_school(request)
    allowed_school_ids = _school_ids_for_user(request.user)

    enquiries = Enquiry.objects.select_related("school", "created_by", "converted_student").filter(
        school_id__in=allowed_school_ids
    )
    visitors = VisitorLog.objects.select_related("school", "created_by").filter(
        school_id__in=allowed_school_ids
    )
    calls = CallLog.objects.select_related("school", "created_by", "enquiry", "student").filter(
        school_id__in=allowed_school_ids
    )
    meetings = MeetingRequest.objects.select_related(
        "school", "created_by", "principal", "enquiry"
    ).filter(school_id__in=allowed_school_ids)

    if school:
        enquiries = enquiries.filter(school=school)
        visitors = visitors.filter(school=school)
        calls = calls.filter(school=school)
        meetings = meetings.filter(school=school)

    status = (request.GET.get("status") or "").strip().upper()
    if status:
        enquiries = enquiries.filter(status=status)

    today = timezone.localdate()
    context = build_layout_context(request.user, current_section=current_section)
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "enquiries": enquiries.order_by("-created_at")[:8],
            "visitors": visitors.order_by("-entry_time")[:8],
            "recent_follow_ups": EnquiryFollowUp.objects.filter(
                enquiry__in=enquiries
            ).select_related("enquiry", "created_by")[:8],
            "recent_calls": calls.order_by("-created_at")[:6],
            "upcoming_meetings": meetings.filter(status__in=["REQUESTED", "SCHEDULED"]).order_by(
                "scheduled_at", "-created_at"
            )[:6],
            "enquiry_status_choices": Enquiry.STATUS_CHOICES,
            "enquiry_source_choices": Enquiry.SOURCE_CHOICES,
            "follow_up_outcome_choices": EnquiryFollowUp.OUTCOME_CHOICES,
            "visitor_purpose_choices": VisitorLog.PURPOSE_CHOICES,
            "frontoffice_stats": {
                "new_enquiries": enquiries.filter(status="NEW").count(),
                "follow_ups_today": enquiries.filter(follow_up_date=today).count(),
                "overdue_follow_ups": enquiries.filter(follow_up_date__lt=today)
                .exclude(status="CLOSED")
                .count(),
                "visitors_today": visitors.filter(entry_time__date=today).count(),
                "open_visitors": visitors.filter(exit_time__isnull=True).count(),
                "open_calls": calls.filter(status="OPEN").count(),
                "calls_due_today": calls.filter(status="OPEN", follow_up_date=today).count(),
                "meetings_today": meetings.filter(scheduled_at__date=today).count(),
                "pending_meetings": meetings.filter(status__in=["REQUESTED", "SCHEDULED"]).count(),
            },
        }
    )
    return context


def build_counsellor_dashboard_context(request, *, current_section="dashboard"):
    school = _selected_school(request)
    allowed_school_ids = _school_ids_for_user(request.user)
    today = timezone.localdate()

    # Filter by created_by to ensure counsellor only sees their own leads/admissions
    # unless they are an admin or it's a shared pool (for now we assume counsellor-specific view as per request)
    enquiries = Enquiry.objects.select_related("school", "created_by").filter(
        school_id__in=allowed_school_ids
    )
    admissions = AdmissionApplication.objects.select_related(
        "school", "created_by", "academic_year"
    ).filter(school_id__in=allowed_school_ids)
    calls = CallLog.objects.select_related("school", "created_by", "enquiry").filter(
        school_id__in=allowed_school_ids
    )
    meetings = MeetingRequest.objects.select_related("school", "created_by", "enquiry").filter(
        school_id__in=allowed_school_ids
    )

    # Security Check: Counsellors see only their own data to prevent leakage
    if request.user.role in ["ADMISSION_COUNSELOR", "CAREER_COUNSELOR"]:
        enquiries = enquiries.filter(created_by=request.user)
        admissions = admissions.filter(created_by=request.user)
        calls = calls.filter(created_by=request.user)
        meetings = meetings.filter(created_by=request.user)

    if school:
        enquiries = enquiries.filter(school=school)
        admissions = admissions.filter(school=school)
        calls = calls.filter(school=school)
        meetings = meetings.filter(school=school)

    # Stats for Dashboard Cards
    stats = {
        "total_enquiries": enquiries.count(),
        "new_enquiries": enquiries.filter(status="NEW").count(),
        "pending_followups": enquiries.filter(follow_up_date__lte=today)
        .exclude(status="CLOSED")
        .count(),
        "followups_today": enquiries.filter(follow_up_date=today).count(),
        "total_applications": admissions.count(),
        "pending_applications": admissions.exclude(
            status__in=["APPROVED", "ADMITTED", "REJECTED", "CLOSED"]
        ).count(),
        "admitted_students": admissions.filter(status="ADMITTED").count(),
        "conversion_rate": 0,
        "meetings_today": meetings.filter(scheduled_at__date=today).count(),
        "calls_today": calls.filter(created_at__date=today).count(),
    }

    if stats["total_enquiries"] > 0:
        stats["conversion_rate"] = int(
            (stats["admitted_students"] / stats["total_enquiries"]) * 100
        )

    # Recent Data for Tables
    recent_enquiries = enquiries.order_by("-created_at")[:5]
    recent_followups = (
        EnquiryFollowUp.objects.filter(enquiry__in=enquiries)
        .select_related("enquiry", "created_by")
        .order_by("-created_at")[:5]
    )
    upcoming_meetings = meetings.filter(
        status__in=["REQUESTED", "SCHEDULED"], scheduled_at__gte=timezone.now()
    ).order_by("scheduled_at")[:5]
    recent_admissions = admissions.order_by("-created_at")[:5]

    # Chart Data (last 14 days enquiries)
    last_14_days = []
    enquiry_counts = []
    admission_counts = []
    for i in range(13, -1, -1):
        d = today - timezone.timedelta(days=i)
        last_14_days.append(d.strftime("%b %d"))
        enquiry_counts.append(enquiries.filter(created_at__date=d).count())
        admission_counts.append(admissions.filter(created_at__date=d).count())

    context = build_layout_context(request.user, current_section=current_section)

    if request.user.role == "CAREER_COUNSELOR":
        from apps.career_counseling.models import Application as CareerApp
        from apps.career_counseling.models import CounselingSession
        from apps.staff.models import StaffMember

        # Link User to StaffMember via email as there is no direct FK
        staff = StaffMember.objects.filter(email=request.user.email, school=school).first()

        context.update(
            {
                "today_sessions": CounselingSession.objects.filter(
                    counselor=staff, scheduled_at__date=today
                ).order_by("scheduled_at")
                if staff
                else [],
                "counseling_deadlines": CareerApp.objects.filter(
                    student__school=school, deadline__gte=today
                ).order_by("deadline")[:5],
            }
        )

    context.update(
        {
            "stats": stats,
            "recent_enquiries": recent_enquiries,
            "recent_followups": recent_followups,
            "upcoming_meetings": upcoming_meetings,
            "recent_admissions": recent_admissions,
            "chart_labels": last_14_days,
            "chart_enquiries": enquiry_counts,
            "chart_admissions": admission_counts,
            "status_distribution": [
                enquiries.filter(status="NEW").count(),
                enquiries.filter(status="QUALIFIED").count(),
                enquiries.filter(status="ADMISSION_IN_PROGRESS").count(),
                enquiries.filter(status="LOST").count(),
            ],
            "app_distribution": [
                admissions.filter(status="SUBMITTED").count(),
                admissions.filter(status="UNDER_REVIEW").count(),
                admissions.filter(status="ADMITTED").count(),
                admissions.filter(status="REJECTED").count(),
            ],
            "today": today,
        }
    )
    return context


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def frontoffice_search(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to use front office search.")
        return redirect("dashboard")

    school = _selected_school(request)
    school_ids = _school_ids_for_user(request.user)

    q = (request.GET.get("q") or "").strip()
    students = Student.objects.filter(school_id__in=school_ids, is_active=True).select_related(
        "school"
    )
    enquiries = Enquiry.objects.filter(school_id__in=school_ids).select_related("school")

    if school:
        students = students.filter(school=school)
        enquiries = enquiries.filter(school=school)

    if q:
        students = students.filter(
            models.Q(first_name__icontains=q)
            | models.Q(last_name__icontains=q)
            | models.Q(admission_no__icontains=q)
            | models.Q(guardian_phone__icontains=q)
            | models.Q(student_phone__icontains=q)
        )
        enquiries = enquiries.filter(
            models.Q(student_name__icontains=q)
            | models.Q(guardian_name__icontains=q)
            | models.Q(phone__icontains=q)
        )
    else:
        students = students.none()
        enquiries = enquiries.none()

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "q": q,
            "students": students.order_by("first_name", "last_name")[:50],
            "enquiries": enquiries.order_by("-created_at")[:50],
        }
    )
    return render(request, "frontoffice/search.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def frontoffice_daily_report(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view front office reports.")
        return redirect("dashboard")

    school = _selected_school(request)
    school_ids = _school_ids_for_user(request.user)
    today = timezone.localdate()

    enquiries = Enquiry.objects.select_related("school").filter(school_id__in=school_ids)
    visitors = VisitorLog.objects.select_related("school").filter(school_id__in=school_ids)
    calls = CallLog.objects.select_related("school").filter(school_id__in=school_ids)

    if school:
        enquiries = enquiries.filter(school=school)
        visitors = visitors.filter(school=school)
        calls = calls.filter(school=school)

    # Enquiries snapshot
    enquiries_today = enquiries.filter(created_at__date=today)
    follow_ups_due_today = enquiries.filter(follow_up_date=today).order_by(
        "follow_up_date", "-created_at"
    )[:50]
    follow_ups_overdue = (
        enquiries.filter(follow_up_date__lt=today)
        .exclude(status="CLOSED")
        .order_by("follow_up_date")[:50]
    )
    conversions_today = enquiries.filter(status="ADMISSION_IN_PROGRESS", updated_at__date=today)

    # Visitors snapshot
    visitors_today = visitors.filter(entry_time__date=today).order_by("-entry_time")[:50]
    open_visitors = visitors.filter(exit_time__isnull=True).order_by("-entry_time")[:50]

    # Calls snapshot
    calls_due_today = calls.filter(follow_up_date=today, status="OPEN").order_by(
        "follow_up_date", "-created_at"
    )[:50]
    calls_overdue = calls.filter(follow_up_date__lt=today, status="OPEN").order_by(
        "follow_up_date"
    )[:50]

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "today": today,
            "kpis": {
                "enquiries_today": enquiries_today.count(),
                "new_enquiries_open": enquiries.filter(status="NEW").count(),
                "follow_ups_due_today": enquiries.filter(follow_up_date=today).count(),
                "follow_ups_overdue": enquiries.filter(follow_up_date__lt=today)
                .exclude(status="CLOSED")
                .count(),
                "visitors_today": visitors.filter(entry_time__date=today).count(),
                "open_visitors": visitors.filter(exit_time__isnull=True).count(),
                "calls_due_today": calls.filter(follow_up_date=today, status="OPEN").count(),
                "calls_overdue": calls.filter(follow_up_date__lt=today, status="OPEN").count(),
                "conversions_today": conversions_today.count(),
            },
            "enquiries_today": enquiries_today.order_by("-created_at")[:50],
            "follow_ups_due_today_list": follow_ups_due_today,
            "follow_ups_overdue_list": follow_ups_overdue,
            "visitors_today": visitors_today,
            "open_visitors": open_visitors,
            "calls_due_today": calls_due_today,
            "calls_overdue": calls_overdue,
        }
    )
    return render(request, "frontoffice/daily_report.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def frontoffice_overview(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view front office records.")
        return redirect("dashboard")
    context = build_frontoffice_dashboard_context(request, current_section="frontoffice")
    return render(request, "frontoffice/overview.html", context)


def _enquiry_redirect(enquiry):
    return redirect(f"/frontoffice/?school={enquiry.school_id}")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_list(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view enquiries.")
        return redirect("dashboard")

    school = _selected_school(request)
    qs = Enquiry.objects.select_related("school", "created_by", "converted_student").filter(
        school_id__in=_school_ids_for_user(request.user)
    )
    if school:
        qs = qs.filter(school=school)

    query = (request.GET.get("q") or "").strip()
    if query:
        qs = (
            qs.filter(student_name__icontains=query)
            | qs.filter(guardian_name__icontains=query)
            | qs.filter(phone__icontains=query)
        )

    status = (request.GET.get("status") or "").strip().upper()
    if status:
        qs = qs.filter(status=status)

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "enquiries": qs.order_by("-created_at")[:200],
            "q": query,
            "status": status,
            "enquiry_status_choices": Enquiry.STATUS_CHOICES,
        }
    )
    return render(request, "frontoffice/enquiries_list.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_detail(request, enquiry_id):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view enquiries.")
        return redirect("dashboard")

    enquiry = get_object_or_404(
        Enquiry.objects.select_related("school", "created_by", "converted_student"),
        id=enquiry_id,
        school_id__in=_school_ids_for_user(request.user),
    )
    follow_ups = enquiry.follow_ups.select_related("created_by").all()[:50]
    calls = enquiry.call_logs.select_related("created_by").all()[:50]
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "enquiry": enquiry,
            "follow_ups": follow_ups,
            "calls": calls,
            "enquiry_status_choices": Enquiry.STATUS_CHOICES,
            "enquiry_source_choices": Enquiry.SOURCE_CHOICES,
            "follow_up_outcome_choices": EnquiryFollowUp.OUTCOME_CHOICES,
            "can_manage": has_permission(request.user, "frontoffice.manage"),
        }
    )
    return render(request, "frontoffice/enquiry_detail.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_create_page(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage enquiries.")
        return redirect("/frontoffice/enquiries/")

    if request.method == "POST":
        school, error_redirect = _require_school(
            request, redirect_url="/frontoffice/enquiries/create/"
        )
        if error_redirect:
            return error_redirect

        student_name = request.POST.get("student_name", "").strip()
        guardian_name = request.POST.get("guardian_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        if not student_name or not guardian_name or not phone:
            messages.error(request, "Student name, guardian name, and phone are required.")
            return redirect("/frontoffice/enquiries/create/")

        Enquiry.objects.create(
            school=school,
            student_name=student_name,
            guardian_name=guardian_name,
            phone=phone,
            email=request.POST.get("email", "").strip(),
            interested_class=request.POST.get("interested_class", "").strip(),
            source=request.POST.get("source", "WALK_IN"),
            status=request.POST.get("status", "NEW"),
            follow_up_date=request.POST.get("follow_up_date") or None,
            notes=request.POST.get("notes", "").strip(),
            created_by=request.user,
        )
        messages.success(request, "Enquiry created.")
        return redirect(f"/frontoffice/enquiries/?school={school.id}")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": _selected_school(request),
            "enquiry_status_choices": Enquiry.STATUS_CHOICES,
            "enquiry_source_choices": Enquiry.SOURCE_CHOICES,
            "today": timezone.localdate(),
        }
    )
    return render(request, "frontoffice/enquiry_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_edit(request, enquiry_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to edit enquiries.")
        return redirect("/frontoffice/enquiries/")

    enquiry = get_object_or_404(
        Enquiry, id=enquiry_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method == "POST":
        enquiry.student_name = request.POST.get("student_name", enquiry.student_name).strip()
        enquiry.guardian_name = request.POST.get("guardian_name", enquiry.guardian_name).strip()
        enquiry.phone = request.POST.get("phone", enquiry.phone).strip()
        enquiry.email = request.POST.get("email", enquiry.email).strip()
        enquiry.interested_class = request.POST.get(
            "interested_class", enquiry.interested_class
        ).strip()
        enquiry.source = request.POST.get("source", enquiry.source)
        enquiry.status = request.POST.get("status", enquiry.status)
        enquiry.follow_up_date = request.POST.get("follow_up_date") or None
        enquiry.notes = request.POST.get("notes", enquiry.notes).strip()
        enquiry.save()
        messages.success(request, "Enquiry updated.")
        return redirect(f"/frontoffice/enquiries/{enquiry.id}/")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "mode": "edit",
            "enquiry": enquiry,
            "school_options": _school_scope(request.user),
            "selected_school": enquiry.school,
            "enquiry_status_choices": Enquiry.STATUS_CHOICES,
            "enquiry_source_choices": Enquiry.SOURCE_CHOICES,
        }
    )
    return render(request, "frontoffice/enquiry_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_delete(request, enquiry_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to delete enquiries.")
        return redirect("/frontoffice/enquiries/")
    enquiry = get_object_or_404(
        Enquiry, id=enquiry_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method == "POST":
        school_id = enquiry.school_id
        enquiry.delete()
        messages.success(request, "Enquiry deleted.")
        return redirect(f"/frontoffice/enquiries/?school={school_id}")
    messages.error(request, "Invalid delete request.")
    return redirect(f"/frontoffice/enquiries/{enquiry_id}/")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def followup_list(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view follow-ups.")
        return redirect("dashboard")

    school = _selected_school(request)
    qs = EnquiryFollowUp.objects.select_related("enquiry", "enquiry__school", "created_by").filter(
        enquiry__school_id__in=_school_ids_for_user(request.user)
    )
    if school:
        qs = qs.filter(enquiry__school=school)

    outcome = (request.GET.get("outcome") or "").strip().upper()
    if outcome:
        qs = qs.filter(outcome=outcome)

    date_value = (request.GET.get("date") or "").strip()
    if date_value:
        qs = qs.filter(follow_up_on=date_value)

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "follow_ups": qs.order_by("-follow_up_on", "-created_at")[:250],
            "outcome": outcome,
            "date": date_value,
            "follow_up_outcome_choices": EnquiryFollowUp.OUTCOME_CHOICES,
        }
    )
    return render(request, "frontoffice/followups_list.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def visitor_list(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view visitor logs.")
        return redirect("dashboard")

    school = _selected_school(request)
    qs = VisitorLog.objects.select_related("school", "created_by").filter(
        school_id__in=_school_ids_for_user(request.user)
    )
    if school:
        qs = qs.filter(school=school)

    open_only = (request.GET.get("open") or "").strip() == "1"
    if open_only:
        qs = qs.filter(exit_time__isnull=True)

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "visitors": qs.order_by("-entry_time")[:250],
            "open_only": open_only,
            "can_manage": has_permission(request.user, "frontoffice.manage"),
        }
    )
    return render(request, "frontoffice/visitors_list.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def visitor_detail(request, visitor_id):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view visitor logs.")
        return redirect("dashboard")

    visitor = get_object_or_404(
        VisitorLog.objects.select_related("school", "created_by"),
        id=visitor_id,
        school_id__in=_school_ids_for_user(request.user),
    )
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "visitor": visitor,
            "visitor_purpose_choices": VisitorLog.PURPOSE_CHOICES,
            "can_manage": has_permission(request.user, "frontoffice.manage"),
        }
    )
    return render(request, "frontoffice/visitor_detail.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def visitor_create_page(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage visitor logs.")
        return redirect("/frontoffice/visitors/")

    if request.method == "POST":
        school, error_redirect = _require_school(
            request, redirect_url="/frontoffice/visitors/create/"
        )
        if error_redirect:
            return error_redirect

        visitor_name = request.POST.get("visitor_name", "").strip()
        if not visitor_name:
            messages.error(request, "Visitor name is required.")
            return redirect("/frontoffice/visitors/create/")

        VisitorLog.objects.create(
            school=school,
            visitor_name=visitor_name,
            phone=request.POST.get("phone", "").strip(),
            person_to_meet=request.POST.get("person_to_meet", "").strip(),
            purpose=request.POST.get("purpose", "OTHER"),
            remarks=request.POST.get("remarks", "").strip(),
            created_by=request.user,
        )
        messages.success(request, "Visitor entry logged.")
        return redirect(f"/frontoffice/visitors/?school={school.id}")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": _selected_school(request),
            "visitor_purpose_choices": VisitorLog.PURPOSE_CHOICES,
        }
    )
    return render(request, "frontoffice/visitor_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def visitor_edit(request, visitor_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to edit visitor logs.")
        return redirect("/frontoffice/visitors/")

    visitor = get_object_or_404(
        VisitorLog, id=visitor_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method == "POST":
        visitor.visitor_name = request.POST.get("visitor_name", visitor.visitor_name).strip()
        visitor.phone = request.POST.get("phone", visitor.phone).strip()
        visitor.person_to_meet = request.POST.get("person_to_meet", visitor.person_to_meet).strip()
        visitor.purpose = request.POST.get("purpose", visitor.purpose)
        visitor.remarks = request.POST.get("remarks", visitor.remarks).strip()
        visitor.save()
        messages.success(request, "Visitor updated.")
        return redirect(f"/frontoffice/visitors/{visitor.id}/")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "mode": "edit",
            "visitor": visitor,
            "school_options": _school_scope(request.user),
            "selected_school": visitor.school,
            "visitor_purpose_choices": VisitorLog.PURPOSE_CHOICES,
        }
    )
    return render(request, "frontoffice/visitor_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def visitor_delete(request, visitor_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to delete visitor logs.")
        return redirect("/frontoffice/visitors/")
    visitor = get_object_or_404(
        VisitorLog, id=visitor_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method == "POST":
        school_id = visitor.school_id
        visitor.delete()
        messages.success(request, "Visitor deleted.")
        return redirect(f"/frontoffice/visitors/?school={school_id}")
    messages.error(request, "Invalid delete request.")
    return redirect(f"/frontoffice/visitors/{visitor_id}/")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def call_list(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view call logs.")
        return redirect("dashboard")
    school = _selected_school(request)
    qs = CallLog.objects.select_related("school", "enquiry", "student", "created_by").filter(
        school_id__in=_school_ids_for_user(request.user)
    )
    if school:
        qs = qs.filter(school=school)

    call_type = (request.GET.get("type") or "").strip().upper()
    if call_type:
        qs = qs.filter(call_type=call_type)

    status = (request.GET.get("status") or "").strip().upper()
    if status:
        qs = qs.filter(status=status)

    due = (request.GET.get("due") or "").strip().lower()
    today = timezone.localdate()
    if due == "today":
        qs = qs.filter(follow_up_date=today)
    elif due == "overdue":
        qs = qs.filter(follow_up_date__lt=today, status="OPEN")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "calls": qs[:250],
            "call_type": call_type,
            "status": status,
            "due": due,
            "call_type_choices": CallLog.TYPE_CHOICES,
            "call_status_choices": CallLog.STATUS_CHOICES,
            "can_manage": has_permission(request.user, "frontoffice.manage"),
        }
    )
    return render(request, "frontoffice/calls_list.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def call_create(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage call logs.")
        return redirect("/frontoffice/calls/")
    if request.method == "POST":
        school, error_redirect = _require_school(request, redirect_url="/frontoffice/calls/create/")
        if error_redirect:
            return error_redirect
        phone = (request.POST.get("phone") or "").strip()
        if not phone:
            messages.error(request, "Phone is required.")
            return redirect("/frontoffice/calls/create/")
        CallLog.objects.create(
            school=school,
            enquiry_id=int(request.POST.get("enquiry_id"))
            if (request.POST.get("enquiry_id") or "").isdigit()
            else None,
            student_id=int(request.POST.get("student_id"))
            if (request.POST.get("student_id") or "").isdigit()
            else None,
            caller_name=(request.POST.get("caller_name") or "").strip(),
            phone=phone,
            call_type=request.POST.get("call_type", "INCOMING"),
            purpose=(request.POST.get("purpose") or "").strip(),
            follow_up_date=request.POST.get("follow_up_date") or None,
            status=request.POST.get("status", "OPEN"),
            notes=(request.POST.get("notes") or "").strip(),
            created_by=request.user,
        )
        messages.success(request, "Call log saved.")
        return redirect(f"/frontoffice/calls/?school={school.id}")

    school = _selected_school(request)
    enquiry = None
    enquiry_id = (request.GET.get("enquiry_id") or "").strip()
    if enquiry_id.isdigit():
        enquiry = Enquiry.objects.filter(
            id=int(enquiry_id), school_id__in=_school_ids_for_user(request.user)
        ).first()
        if enquiry:
            school = enquiry.school

    prefill_phone = (request.GET.get("phone") or "").strip()
    prefill_caller = (request.GET.get("caller_name") or "").strip()

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "enquiry": enquiry,
            "prefill": {
                "enquiry_id": enquiry.id if enquiry else "",
                "phone": prefill_phone or (enquiry.phone if enquiry else ""),
                "caller_name": prefill_caller or (enquiry.guardian_name if enquiry else ""),
            },
            "call_type_choices": CallLog.TYPE_CHOICES,
            "call_status_choices": CallLog.STATUS_CHOICES,
            "today": timezone.localdate(),
        }
    )
    return render(request, "frontoffice/call_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def call_detail(request, call_id):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view call logs.")
        return redirect("dashboard")
    call = get_object_or_404(
        CallLog.objects.select_related("school", "enquiry", "student", "created_by"),
        id=call_id,
        school_id__in=_school_ids_for_user(request.user),
    )
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update({"call": call, "can_manage": has_permission(request.user, "frontoffice.manage")})
    return render(request, "frontoffice/call_detail.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def call_edit(request, call_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to edit call logs.")
        return redirect("/frontoffice/calls/")
    call = get_object_or_404(CallLog, id=call_id, school_id__in=_school_ids_for_user(request.user))
    if request.method == "POST":
        call.caller_name = (request.POST.get("caller_name") or "").strip()
        call.phone = (request.POST.get("phone") or call.phone).strip()
        call.call_type = request.POST.get("call_type", call.call_type)
        call.purpose = (request.POST.get("purpose") or "").strip()
        call.follow_up_date = request.POST.get("follow_up_date") or None
        call.status = request.POST.get("status", call.status)
        call.notes = (request.POST.get("notes") or "").strip()
        call.save()
        messages.success(request, "Call log updated.")
        return redirect(f"/frontoffice/calls/{call.id}/")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "mode": "edit",
            "call": call,
            "school_options": _school_scope(request.user),
            "selected_school": call.school,
            "call_type_choices": CallLog.TYPE_CHOICES,
            "call_status_choices": CallLog.STATUS_CHOICES,
        }
    )
    return render(request, "frontoffice/call_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def call_delete(request, call_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to delete call logs.")
        return redirect("/frontoffice/calls/")
    call = get_object_or_404(CallLog, id=call_id, school_id__in=_school_ids_for_user(request.user))
    if request.method == "POST":
        school_id = call.school_id
        call.delete()
        messages.success(request, "Call log deleted.")
        return redirect(f"/frontoffice/calls/?school={school_id}")
    messages.error(request, "Invalid delete request.")
    return redirect(f"/frontoffice/calls/{call_id}/")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def meeting_list(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view meetings.")
        return redirect("dashboard")

    school = _selected_school(request)
    qs = MeetingRequest.objects.select_related(
        "school", "principal", "enquiry", "created_by"
    ).filter(school_id__in=_school_ids_for_user(request.user))
    if school:
        qs = qs.filter(school=school)

    status = (request.GET.get("status") or "").strip().upper()
    if status:
        qs = qs.filter(status=status)

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "meetings": qs.order_by("-created_at")[:250],
            "status": status,
            "meeting_status_choices": MeetingRequest.STATUS_CHOICES,
            "can_manage": has_permission(request.user, "frontoffice.manage"),
        }
    )
    return render(request, "frontoffice/meetings_list.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def meeting_detail(request, meeting_id):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view meetings.")
        return redirect("dashboard")

    meeting = get_object_or_404(
        MeetingRequest.objects.select_related("school", "principal", "enquiry", "created_by"),
        id=meeting_id,
        school_id__in=_school_ids_for_user(request.user),
    )
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "meeting": meeting,
            "can_manage": has_permission(request.user, "frontoffice.manage"),
            "meeting_status_choices": MeetingRequest.STATUS_CHOICES,
        }
    )
    return render(request, "frontoffice/meeting_detail.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def meeting_create(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to create meeting requests.")
        return redirect("/frontoffice/meetings/")

    if request.method == "POST":
        school, error_redirect = _require_school(
            request, redirect_url="/frontoffice/meetings/create/"
        )
        if error_redirect:
            return error_redirect

        guardian_name = (request.POST.get("guardian_name") or "").strip()
        if not guardian_name:
            messages.error(request, "Guardian name is required.")
            return redirect("/frontoffice/meetings/create/")

        principal_id = (request.POST.get("principal") or "").strip()
        principal = None
        if principal_id.isdigit():
            principal = User.objects.filter(
                id=int(principal_id), role="PRINCIPAL", school=school
            ).first()

        scheduled_at = request.POST.get("scheduled_at") or None
        meeting = MeetingRequest.objects.create(
            school=school,
            enquiry_id=int(request.POST.get("enquiry_id"))
            if (request.POST.get("enquiry_id") or "").isdigit()
            else None,
            principal=principal,
            guardian_name=guardian_name,
            guardian_phone=(request.POST.get("guardian_phone") or "").strip(),
            guardian_email=(request.POST.get("guardian_email") or "").strip(),
            student_name=(request.POST.get("student_name") or "").strip(),
            scheduled_at=scheduled_at,
            mode=request.POST.get("mode", "IN_PERSON"),
            status="SCHEDULED" if scheduled_at else "REQUESTED",
            reference_name=(request.POST.get("reference_name") or "").strip(),
            reference_social=request.POST.get("reference_social", "WHATSAPP"),
            notes=(request.POST.get("notes") or "").strip(),
            created_by=request.user,
        )

        if principal and principal.email:
            subject = f"Meeting scheduled: {meeting.guardian_name}"
            body = (
                f"Meeting request created in SchoolFlow.\n\n"
                f"School: {school.name}\n"
                f"Guardian: {meeting.guardian_name} ({meeting.guardian_phone})\n"
                f"Student: {meeting.student_name or '-'}\n"
                f"Mode: {meeting.get_mode_display()}\n"
                f"Scheduled: {meeting.scheduled_at or 'Not set'}\n"
                f"Notes: {meeting.notes or '-'}\n"
            )
            try:
                comm = SchoolCommunicationSettings.objects.filter(school=school).first()
                if comm and comm.smtp_enabled:
                    send_email_via_school_smtp(
                        settings_obj=comm, to_email=principal.email, subject=subject, body=body
                    )
                else:
                    EmailMultiAlternatives(subject=subject, body=body, to=[principal.email]).send(
                        fail_silently=True
                    )
            except Exception:
                pass

        messages.success(request, "Meeting request saved.")
        return redirect(f"/frontoffice/meetings/?school={school.id}")

    school = _selected_school(request)
    principals = (
        User.objects.filter(role="PRINCIPAL", school=school) if school else User.objects.none()
    )
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "principals": principals,
            "mode_choices": MeetingRequest.MODE_CHOICES,
            "social_choices": MeetingRequest.SOCIAL_CHOICES,
        }
    )
    return render(request, "frontoffice/meeting_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def meeting_edit(request, meeting_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to edit meeting requests.")
        return redirect("/frontoffice/meetings/")

    meeting = get_object_or_404(
        MeetingRequest, id=meeting_id, school_id__in=_school_ids_for_user(request.user)
    )
    school = meeting.school

    if request.method == "POST":
        meeting.guardian_name = (request.POST.get("guardian_name") or meeting.guardian_name).strip()
        meeting.student_name = (request.POST.get("student_name") or "").strip()
        meeting.guardian_phone = (request.POST.get("guardian_phone") or "").strip()
        meeting.guardian_email = (request.POST.get("guardian_email") or "").strip()
        meeting.mode = request.POST.get("mode", meeting.mode)
        meeting.scheduled_at = request.POST.get("scheduled_at") or None
        meeting.reference_name = (request.POST.get("reference_name") or "").strip()
        meeting.reference_social = request.POST.get("reference_social", meeting.reference_social)
        meeting.notes = (request.POST.get("notes") or "").strip()

        principal_id = (request.POST.get("principal") or "").strip()
        if principal_id.isdigit():
            meeting.principal_id = int(principal_id)
        else:
            meeting.principal_id = None

        status = (request.POST.get("status") or "").strip().upper()
        allowed = {v for v, _ in MeetingRequest.STATUS_CHOICES}
        if status in allowed:
            meeting.status = status
        elif meeting.scheduled_at:
            meeting.status = "SCHEDULED"

        meeting.save()
        messages.success(request, "Meeting updated.")
        return redirect(f"/frontoffice/meetings/{meeting.id}/")

    principals = (
        User.objects.filter(role="PRINCIPAL", school=school) if school else User.objects.none()
    )
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "mode": "edit",
            "meeting": meeting,
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "principals": principals,
            "mode_choices": MeetingRequest.MODE_CHOICES,
            "social_choices": MeetingRequest.SOCIAL_CHOICES,
            "meeting_status_choices": MeetingRequest.STATUS_CHOICES,
        }
    )
    return render(request, "frontoffice/meeting_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def meeting_status_update(request, meeting_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to update meeting status.")
        return redirect("/frontoffice/meetings/")

    meeting = get_object_or_404(
        MeetingRequest, id=meeting_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method != "POST":
        return redirect(f"/frontoffice/meetings/{meeting.id}/")

    status = (request.POST.get("status") or "").strip().upper()
    allowed = {v for v, _ in MeetingRequest.STATUS_CHOICES}
    if status not in allowed:
        messages.error(request, "Invalid status.")
        return redirect(f"/frontoffice/meetings/{meeting.id}/")

    meeting.status = status
    meeting.save(update_fields=["status"])
    messages.success(request, "Meeting status updated.")
    return redirect(f"/frontoffice/meetings/{meeting.id}/")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def messages_home(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view messaging.")
        return redirect("dashboard")

    school = _selected_school(request)
    templates = MessageTemplate.objects.filter(school_id__in=_school_ids_for_user(request.user))
    campaigns = MessageCampaign.objects.filter(school_id__in=_school_ids_for_user(request.user))
    if school:
        templates = templates.filter(school=school)
        campaigns = campaigns.filter(school=school)
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "templates": templates[:12],
            "campaigns": campaigns[:12],
            "can_manage": has_permission(request.user, "frontoffice.manage"),
        }
    )
    return render(request, "frontoffice/messages_home.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def template_list(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view templates.")
        return redirect("dashboard")
    school = _selected_school(request)
    qs = MessageTemplate.objects.filter(school_id__in=_school_ids_for_user(request.user))
    if school:
        qs = qs.filter(school=school)
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "templates": qs[:200],
            "channel_choices": MessageTemplate.CHANNEL_CHOICES,
            "target_choices": MessageTemplate.TARGET_CHOICES,
        }
    )
    return render(request, "frontoffice/templates_list.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def template_create(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage templates.")
        return redirect("/frontoffice/messages/templates/")
    if request.method == "POST":
        school, error_redirect = _require_school(
            request, redirect_url="/frontoffice/messages/templates/create/"
        )
        if error_redirect:
            return error_redirect
        name = (request.POST.get("name") or "").strip()
        body = (request.POST.get("body") or "").strip()
        if not name or not body:
            messages.error(request, "Template name and body are required.")
            return redirect("/frontoffice/messages/templates/create/")
        MessageTemplate.objects.create(
            school=school,
            name=name,
            channel=request.POST.get("channel", "EMAIL"),
            target=request.POST.get("target", "PARENTS"),
            subject=(request.POST.get("subject") or "").strip(),
            body=body,
            is_active=request.POST.get("is_active") == "on",
            created_by=request.user,
        )
        messages.success(request, "Template saved.")
        return redirect(f"/frontoffice/messages/templates/?school={school.id}")
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": _selected_school(request),
            "channel_choices": MessageTemplate.CHANNEL_CHOICES,
            "target_choices": MessageTemplate.TARGET_CHOICES,
        }
    )
    return render(request, "frontoffice/template_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def template_edit(request, template_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage templates.")
        return redirect("/frontoffice/messages/templates/")

    template = get_object_or_404(
        MessageTemplate, id=template_id, school_id__in=_school_ids_for_user(request.user)
    )

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        body = (request.POST.get("body") or "").strip()
        if not name or not body:
            messages.error(request, "Template name and body are required.")
            return redirect(f"/frontoffice/messages/templates/{template.id}/edit/")

        template.name = name
        template.channel = request.POST.get("channel", template.channel)
        template.target = request.POST.get("target", template.target)
        template.subject = (request.POST.get("subject") or "").strip()
        template.body = body
        template.is_active = request.POST.get("is_active") == "on"
        template.save(update_fields=["name", "channel", "target", "subject", "body", "is_active"])
        messages.success(request, "Template updated.")
        return redirect("/frontoffice/messages/templates/")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "mode": "edit",
            "template": template,
            "school_options": _school_scope(request.user),
            "selected_school": template.school,
            "channel_choices": MessageTemplate.CHANNEL_CHOICES,
            "target_choices": MessageTemplate.TARGET_CHOICES,
        }
    )
    return render(request, "frontoffice/template_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def template_delete(request, template_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage templates.")
        return redirect("/frontoffice/messages/templates/")

    template = get_object_or_404(
        MessageTemplate, id=template_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method == "POST":
        template.delete()
        messages.success(request, "Template deleted.")
        return redirect("/frontoffice/messages/templates/")

    messages.error(request, "Invalid delete request.")
    return redirect("/frontoffice/messages/templates/")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def campaign_list(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view campaigns.")
        return redirect("dashboard")
    school = _selected_school(request)
    qs = MessageCampaign.objects.filter(
        school_id__in=_school_ids_for_user(request.user)
    ).select_related("template", "created_by")
    if school:
        qs = qs.filter(school=school)
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "campaigns": qs[:200],
        }
    )
    return render(request, "frontoffice/campaigns_list.html", context)


def _recipients_for_campaign(campaign):
    students = Student.objects.filter(school=campaign.school, is_active=True)
    if campaign.target == "STUDENTS":
        for student in students:
            label = str(student)
            email = (student.email or "").strip()
            phone = (student.student_phone or "").strip()
            yield label, email, phone
    else:
        for student in students:
            label = f"{student.guardian_name} ({student})"
            email = (student.guardian_email or "").strip()
            phone = (student.guardian_phone or "").strip()
            yield label, email, phone


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def campaign_create(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage campaigns.")
        return redirect("/frontoffice/messages/campaigns/")
    if request.method == "POST":
        school, error_redirect = _require_school(
            request, redirect_url="/frontoffice/messages/campaigns/create/"
        )
        if error_redirect:
            return error_redirect

        title = (request.POST.get("title") or "").strip()
        body = (request.POST.get("body") or "").strip()
        if not title or not body:
            messages.error(request, "Title and message body are required.")
            return redirect("/frontoffice/messages/campaigns/create/")

        template = None
        template_id = (request.POST.get("template_id") or "").strip()
        if template_id.isdigit():
            template = MessageTemplate.objects.filter(id=int(template_id), school=school).first()

        campaign = MessageCampaign.objects.create(
            school=school,
            template=template,
            channel=request.POST.get("channel", template.channel if template else "EMAIL"),
            target=request.POST.get("target", template.target if template else "PARENTS"),
            title=title,
            subject=(request.POST.get("subject") or (template.subject if template else "")).strip(),
            body=body,
            created_by=request.user,
        )
        messages.success(request, "Campaign created. You can send it now.")
        return redirect(f"/frontoffice/messages/campaigns/{campaign.id}/")

    school = _selected_school(request)

    notice = None
    notice_id = (request.GET.get("notice_id") or "").strip()
    if notice_id.isdigit():
        from apps.communication.models import Notice

        notice = Notice.objects.filter(
            id=int(notice_id), school_id__in=_school_ids_for_user(request.user), is_published=True
        ).first()
        if notice:
            school = notice.school

    templates = (
        MessageTemplate.objects.filter(school=school, is_active=True)
        if school
        else MessageTemplate.objects.none()
    )
    prefill = {
        "title": (notice.title if notice else ""),
        "subject": (notice.title if notice else ""),
        "body": (notice.body if notice else ""),
    }
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "notice": notice,
            "prefill": prefill,
            "templates": templates,
            "channel_choices": MessageTemplate.CHANNEL_CHOICES,
            "target_choices": MessageTemplate.TARGET_CHOICES,
        }
    )
    return render(request, "frontoffice/campaign_form.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def campaign_detail(request, campaign_id):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view campaigns.")
        return redirect("dashboard")
    campaign = get_object_or_404(
        MessageCampaign, id=campaign_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method == "POST" and has_permission(request.user, "frontoffice.manage"):
        delivery_id = (request.POST.get("delivery_id") or "").strip()
        action = (request.POST.get("action") or "").strip().lower()
        if delivery_id.isdigit():
            delivery = get_object_or_404(campaign.deliveries, id=int(delivery_id))
            if action == "mark_read":
                delivery.read_at = timezone.now()
                delivery.save(update_fields=["read_at"])
                messages.success(request, "Delivery marked as read.")
                return redirect(f"/frontoffice/messages/campaigns/{campaign.id}/")
            if action == "retry" and delivery.status in {"FAILED", "SKIPPED", "QUEUED"}:
                try:
                    if campaign.channel == "EMAIL" and delivery.recipient_contact:
                        comm = SchoolCommunicationSettings.objects.filter(
                            school=campaign.school
                        ).first()
                        if comm and comm.smtp_enabled:
                            send_email_via_school_smtp(
                                settings_obj=comm,
                                to_email=delivery.recipient_contact,
                                subject=campaign.subject or campaign.title,
                                body=campaign.body,
                            )
                        else:
                            EmailMultiAlternatives(
                                subject=campaign.subject or campaign.title,
                                body=campaign.body,
                                to=[delivery.recipient_contact],
                            ).send(fail_silently=False)
                        _log_delivery_event(delivery, status="SENT", error="")
                        messages.success(request, "Delivery retried successfully.")
                    elif campaign.channel == "WHATSAPP":
                        _log_delivery_event(
                            delivery,
                            status="QUEUED",
                            error="WhatsApp provider not configured (placeholder log).",
                        )
                        messages.info(
                            request,
                            "WhatsApp delivery remains queued until provider integration is configured.",
                        )
                    else:
                        messages.error(request, "No retry path is available for this delivery.")
                except Exception as exc:
                    _log_delivery_event(delivery, status="FAILED", error=str(exc))
                    messages.error(request, "Retry failed again.")
                return redirect(f"/frontoffice/messages/campaigns/{campaign.id}/")
    deliveries = campaign.deliveries.all()[:200]
    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "campaign": campaign,
            "deliveries": deliveries,
            "can_manage": has_permission(request.user, "frontoffice.manage"),
            "delivery_stats": {
                "sent": campaign.deliveries.filter(status="SENT").count(),
                "failed": campaign.deliveries.filter(status="FAILED").count(),
                "queued": campaign.deliveries.filter(status="QUEUED").count(),
                "read": campaign.deliveries.filter(read_at__isnull=False).count(),
            },
        }
    )
    return render(request, "frontoffice/campaign_detail.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def campaign_send(request, campaign_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to send campaigns.")
        return redirect("/frontoffice/messages/campaigns/")
    campaign = get_object_or_404(
        MessageCampaign, id=campaign_id, school_id__in=_school_ids_for_user(request.user)
    )
    if request.method != "POST":
        return redirect(f"/frontoffice/messages/campaigns/{campaign.id}/")
    if campaign.status == "SENT":
        messages.error(request, "Campaign already sent.")
        return redirect(f"/frontoffice/messages/campaigns/{campaign.id}/")

    sent = 0
    skipped = 0
    failed = 0
    for label, email, phone in _recipients_for_campaign(campaign):
        if campaign.channel == "EMAIL":
            if not email:
                _log_delivery_event(
                    MessageDeliveryLog.objects.create(
                        campaign=campaign,
                        channel="EMAIL",
                        recipient_label=label,
                        recipient_contact="",
                        status="SKIPPED",
                        error="Missing email",
                    ),
                    status="SKIPPED",
                    error="Missing email",
                )
                skipped += 1
                continue
            try:
                comm = SchoolCommunicationSettings.objects.filter(school=campaign.school).first()
                if comm and comm.smtp_enabled:
                    send_email_via_school_smtp(
                        settings_obj=comm,
                        to_email=email,
                        subject=campaign.subject or campaign.title,
                        body=campaign.body,
                    )
                else:
                    EmailMultiAlternatives(
                        subject=campaign.subject or campaign.title, body=campaign.body, to=[email]
                    ).send(fail_silently=False)
                _log_delivery_event(
                    MessageDeliveryLog.objects.create(
                        campaign=campaign,
                        channel="EMAIL",
                        recipient_label=label,
                        recipient_contact=email,
                        status="SENT",
                    ),
                    status="SENT",
                )
                sent += 1
            except Exception as exc:
                _log_delivery_event(
                    MessageDeliveryLog.objects.create(
                        campaign=campaign,
                        channel="EMAIL",
                        recipient_label=label,
                        recipient_contact=email,
                        status="FAILED",
                        error=str(exc),
                    ),
                    status="FAILED",
                    error=str(exc),
                )
                failed += 1
        else:
            contact = phone or ""
            _log_delivery_event(
                MessageDeliveryLog.objects.create(
                    campaign=campaign,
                    channel="WHATSAPP",
                    recipient_label=label,
                    recipient_contact=contact,
                    status="QUEUED",
                    error="WhatsApp provider not configured (placeholder log).",
                ),
                status="QUEUED",
                error="WhatsApp provider not configured (placeholder log).",
            )
            sent += 1

    campaign.status = "SENT"
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["status", "sent_at"])
    messages.success(
        request, f"Campaign processed: {sent} queued/sent, {skipped} skipped, {failed} failed."
    )
    return redirect(f"/frontoffice/messages/campaigns/{campaign.id}/")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def document_reminders(request):
    if not has_permission(request.user, "frontoffice.view"):
        messages.error(request, "You do not have permission to view document reminders.")
        return redirect("dashboard")

    school = _selected_school(request)
    school_ids = _school_ids_for_user(request.user)
    students = Student.objects.filter(school_id__in=school_ids, is_active=True).order_by(
        "first_name", "last_name"
    )
    if school:
        students = students.filter(school=school)

    required = (request.GET.get("required") or "basic").strip().lower()
    missing = []
    for student in students[:500]:
        missing_items = missing_documents(student, required=required)
        if missing_items:
            missing.append({"student": student, "missing": ", ".join(missing_items)})

    templates = MessageTemplate.objects.filter(
        school_id__in=school_ids, is_active=True, target="PARENTS"
    )
    if school:
        templates = templates.filter(school=school)

    if request.method == "POST":
        if not has_permission(request.user, "frontoffice.manage"):
            messages.error(request, "You do not have permission to send reminders.")
            return redirect("/frontoffice/document-reminders/")
        school_for_send, error_redirect = _require_school(
            request, redirect_url="/frontoffice/document-reminders/"
        )
        if error_redirect:
            return error_redirect

        template = None
        template_id = (request.POST.get("template_id") or "").strip()
        if template_id.isdigit():
            template = MessageTemplate.objects.filter(
                id=int(template_id), school=school_for_send, is_active=True
            ).first()
        if not template:
            messages.error(request, "Select a valid template.")
            return redirect("/frontoffice/document-reminders/")

        channel = request.POST.get("channel", template.channel)
        title = (request.POST.get("title") or "Document reminder").strip()
        subject = (request.POST.get("subject") or template.subject or title).strip()
        body = (request.POST.get("body") or template.body).strip()

        campaign = MessageCampaign.objects.create(
            school=school_for_send,
            template=template,
            channel=channel,
            target="PARENTS",
            title=title,
            subject=subject,
            body=body,
            status="DRAFT",
            created_by=request.user,
        )

        sent = 0
        skipped = 0
        failed = 0
        recipients = Student.objects.filter(school=school_for_send, is_active=True).order_by("id")[
            :500
        ]
        for student in recipients:
            # Only target those missing at least one required document.
            if not missing_documents(student, required=required):
                continue
            label = f"{student.guardian_name} ({student})"
            email = (student.guardian_email or "").strip()
            phone = (student.guardian_phone or "").strip()

            if channel == "EMAIL":
                if not email:
                    _log_delivery_event(
                        MessageDeliveryLog.objects.create(
                            campaign=campaign,
                            channel="EMAIL",
                            recipient_label=label,
                            recipient_contact="",
                            status="SKIPPED",
                            error="Missing email",
                        ),
                        status="SKIPPED",
                        error="Missing email",
                    )
                    skipped += 1
                    continue
                try:
                    comm = SchoolCommunicationSettings.objects.filter(
                        school=school_for_send
                    ).first()
                    if comm and comm.smtp_enabled:
                        send_email_via_school_smtp(
                            settings_obj=comm, to_email=email, subject=subject, body=body
                        )
                    else:
                        EmailMultiAlternatives(subject=subject, body=body, to=[email]).send(
                            fail_silently=False
                        )
                    _log_delivery_event(
                        MessageDeliveryLog.objects.create(
                            campaign=campaign,
                            channel="EMAIL",
                            recipient_label=label,
                            recipient_contact=email,
                            status="SENT",
                        ),
                        status="SENT",
                    )
                    sent += 1
                except Exception as exc:
                    _log_delivery_event(
                        MessageDeliveryLog.objects.create(
                            campaign=campaign,
                            channel="EMAIL",
                            recipient_label=label,
                            recipient_contact=email,
                            status="FAILED",
                            error=str(exc),
                        ),
                        status="FAILED",
                        error=str(exc),
                    )
                    failed += 1
            else:
                _log_delivery_event(
                    MessageDeliveryLog.objects.create(
                        campaign=campaign,
                        channel="WHATSAPP",
                        recipient_label=label,
                        recipient_contact=phone,
                        status="QUEUED",
                        error="WhatsApp provider not configured (placeholder log).",
                    ),
                    status="QUEUED",
                    error="WhatsApp provider not configured (placeholder log).",
                )
                sent += 1

        campaign.status = "SENT"
        campaign.sent_at = timezone.now()
        campaign.save(update_fields=["status", "sent_at"])
        messages.success(
            request, f"Reminder processed: {sent} queued/sent, {skipped} skipped, {failed} failed."
        )
        return redirect(f"/frontoffice/messages/campaigns/{campaign.id}/")

    context = build_layout_context(request.user, current_section="frontoffice")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "missing_rows": missing[:200],
            "required": required,
            "templates": templates[:50],
            "channel_choices": MessageTemplate.CHANNEL_CHOICES,
        }
    )
    return render(request, "frontoffice/document_reminders.html", context)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_create(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage front office enquiries.")
        return redirect("frontoffice-overview")
    if request.method != "POST":
        return redirect("frontoffice-overview")

    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a valid school before saving an enquiry.")
        return redirect("frontoffice-overview")

    student_name = request.POST.get("student_name", "").strip()
    guardian_name = request.POST.get("guardian_name", "").strip()
    phone = request.POST.get("phone", "").strip()
    if not student_name or not guardian_name or not phone:
        messages.error(request, "Student name, guardian name, and phone are required.")
        return redirect(f"/frontoffice/?school={school.id}")

    follow_up_date = request.POST.get("follow_up_date") or None
    Enquiry.objects.create(
        school=school,
        student_name=student_name,
        guardian_name=guardian_name,
        phone=phone,
        email=request.POST.get("email", "").strip(),
        interested_class=request.POST.get("interested_class", "").strip(),
        source=request.POST.get("source", "WALK_IN"),
        status=request.POST.get("status", "NEW"),
        follow_up_date=follow_up_date,
        notes=request.POST.get("notes", "").strip(),
        created_by=request.user,
    )
    messages.success(request, "Enquiry logged successfully.")
    return redirect(f"/frontoffice/?school={school.id}")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_update(request, enquiry_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to update enquiries.")
        return redirect("frontoffice-overview")
    enquiry = get_object_or_404(
        Enquiry, id=enquiry_id, school_id__in=_school_scope(request.user).values("id")
    )
    if request.method != "POST":
        return redirect("frontoffice-overview")
    enquiry.status = request.POST.get("status", enquiry.status)
    enquiry.follow_up_date = request.POST.get("follow_up_date") or None
    enquiry.notes = request.POST.get("notes", enquiry.notes).strip()
    enquiry.save(update_fields=["status", "follow_up_date", "notes", "updated_at"])
    messages.success(request, "Enquiry updated.")
    return _enquiry_redirect(enquiry)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_follow_up_create(request, enquiry_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage enquiry follow-ups.")
        return redirect("frontoffice-overview")
    enquiry = get_object_or_404(
        Enquiry, id=enquiry_id, school_id__in=_school_scope(request.user).values("id")
    )
    if request.method != "POST":
        return _enquiry_redirect(enquiry)

    follow_up = EnquiryFollowUp.objects.create(
        enquiry=enquiry,
        follow_up_on=request.POST.get("follow_up_on") or timezone.localdate(),
        outcome=request.POST.get("outcome", "CALL_BACK"),
        next_follow_up_date=request.POST.get("next_follow_up_date") or None,
        summary=request.POST.get("summary", "").strip(),
        created_by=request.user,
    )
    if follow_up.next_follow_up_date:
        enquiry.follow_up_date = follow_up.next_follow_up_date
    if follow_up.outcome in {"INTERESTED", "VISIT_SCHEDULED"}:
        enquiry.status = "FOLLOW_UP"
    elif follow_up.outcome == "NOT_INTERESTED":
        enquiry.status = "CLOSED"
    enquiry.notes = "\n".join(
        filter(None, [enquiry.notes.strip(), follow_up.summary.strip()])
    ).strip()
    enquiry.save(update_fields=["follow_up_date", "status", "notes", "updated_at"])
    messages.success(request, "Follow-up logged.")
    return _enquiry_redirect(enquiry)


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def enquiry_convert(request, enquiry_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to convert enquiries.")
        return redirect("frontoffice-overview")
    enquiry = get_object_or_404(
        Enquiry, id=enquiry_id, school_id__in=_school_scope(request.user).values("id")
    )
    if request.method != "POST":
        return redirect(f"/frontoffice/enquiries/{enquiry.id}/")
    enquiry.status = "ADMISSION_IN_PROGRESS"
    enquiry.save(update_fields=["status", "updated_at"])
    messages.success(request, "Enquiry moved to admissions. Create an admission application now.")
    return redirect(f"/admissions/create/?enquiry={enquiry.id}")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def visitor_create(request):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to manage visitor logs.")
        return redirect("frontoffice-overview")
    if request.method != "POST":
        return redirect("frontoffice-overview")

    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a valid school before saving a visitor log.")
        return redirect("frontoffice-overview")

    visitor_name = request.POST.get("visitor_name", "").strip()
    if not visitor_name:
        messages.error(request, "Visitor name is required.")
        return redirect(f"/frontoffice/?school={school.id}")

    VisitorLog.objects.create(
        school=school,
        visitor_name=visitor_name,
        phone=request.POST.get("phone", "").strip(),
        person_to_meet=request.POST.get("person_to_meet", "").strip(),
        purpose=request.POST.get("purpose", "OTHER"),
        remarks=request.POST.get("remarks", "").strip(),
        created_by=request.user,
    )
    messages.success(request, "Visitor entry logged.")
    return redirect(f"/frontoffice/?school={school.id}")


@role_required("SUPER_ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR")
def visitor_checkout(request, visitor_id):
    if not has_permission(request.user, "frontoffice.manage"):
        messages.error(request, "You do not have permission to close visitor entries.")
        return redirect("frontoffice-overview")
    visitor = get_object_or_404(
        VisitorLog, id=visitor_id, school_id__in=_school_scope(request.user).values("id")
    )
    if request.method == "POST" and visitor.exit_time is None:
        visitor.exit_time = timezone.now()
        visitor.save(update_fields=["exit_time"])
        messages.success(request, "Visitor checkout recorded.")
    return redirect(f"/frontoffice/?school={visitor.school_id}")
