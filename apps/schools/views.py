import csv
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import AcademicClass, AcademicYear, ClassMaster, SectionMaster
from apps.attendance.models import AttendanceSession
from apps.communication.models import Notice
from apps.core.permissions import has_permission, permission_required, role_required
from apps.core.throttle import throttle_hit
from apps.core.ui import build_layout_context
from apps.exams.models import Exam
from apps.fees.models import StudentFeeLedger
from apps.schools.email_utils import send_email_via_school_smtp
from apps.schools.feature_access import enabled_feature_codes_for_school
from apps.schools.limits import campus_limit_for_school
from apps.students.models import Student

from .forms import CampusForm, SchoolCommunicationSettingsForm, SchoolForm, SchoolTeamInviteForm
from .models import (
    Campus,
    ImplementationProject,
    ImplementationTask,
    School,
    SchoolCommunicationSettings,
    SchoolSubscription,
    SubscriptionPlan,
)

STATE_CITY_MAP = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati"],
    "Arunachal Pradesh": ["Itanagar", "Naharlagun", "Pasighat", "Tawang"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur"],
    "Chhattisgarh": ["Raipur", "Bilaspur", "Durg", "Korba"],
    "Delhi": ["New Delhi", "Central Delhi", "North Delhi", "Dwarka"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat", "Ambala"],
    "Himachal Pradesh": ["Shimla", "Dharamshala", "Solan", "Mandi"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur", "Gwalior"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Sambalpur"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem"],
    "Telangana": ["Hyderabad", "Warangal", "Karimnagar", "Nizamabad"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Noida", "Varanasi"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Haldwani", "Roorkee"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri"],
}


def _school_queryset_for_user(user):
    if user.role == "SUPER_ADMIN":
        return School.objects.all()

    if user.school_id:
        return School.objects.filter(id=user.school_id)

    return School.objects.none()


def _campus_limit_for_school(school):
    plan_limit = campus_limit_for_school(school.id)
    school_limit = int(getattr(school, "allowed_campuses", 0) or 0) or None
    if plan_limit and school_limit:
        return min(plan_limit, school_limit)
    return plan_limit or school_limit


SCHOOL_IMPORT_HEADERS = [
    "name",
    "code",
    "email",
    "phone",
    "support_email",
    "website",
    "principal_name",
    "board",
    "medium",
    "established_year",
    "address",
    "address_line2",
    "city",
    "state",
    "pincode",
    "student_capacity",
    "allowed_campuses",
    "is_active",
]
SCHOOL_IMPORT_SESSION_KEY = "schools_import_preview_v1"


def _sanitize_csv_cell(value) -> str:
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _parse_bool(value, default=False) -> bool:
    raw = (str(value or "")).strip().lower()
    if raw in {"1", "true", "yes", "y", "active"}:
        return True
    if raw in {"0", "false", "no", "n", "inactive"}:
        return False
    return default


def _read_csv_upload(upload) -> list[dict]:
    data = upload.read()
    try:
        text = data.decode("utf-8-sig")
    except Exception:
        text = data.decode("utf-8", errors="ignore")
    reader = csv.DictReader(text.splitlines())
    rows: list[dict] = []
    for row in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in (row or {}).items()})
    return rows


def _parse_int(raw: str, field: str, errors: list[str], *, min_value: int | None = None) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        errors.append(f"{field} must be a number")
        return None
    value = int(raw)
    if min_value is not None and value < min_value:
        errors.append(f"{field} must be >= {min_value}")
        return None
    return value


def _validate_school_import_row(row: dict) -> tuple[dict, list[str]]:
    errors: list[str] = []
    name = (row.get("name") or "").strip()
    code = (row.get("code") or "").strip()
    email = (row.get("email") or "").strip()
    phone = (row.get("phone") or "").strip()
    principal_name = (row.get("principal_name") or "").strip()
    address = (row.get("address") or "").strip()
    city = (row.get("city") or "").strip()
    state = (row.get("state") or "").strip()

    support_email = (row.get("support_email") or "").strip()
    website = (row.get("website") or "").strip()
    board = (row.get("board") or "").strip()
    medium = (row.get("medium") or "").strip()
    address_line2 = (row.get("address_line2") or "").strip()
    pincode = (row.get("pincode") or "").strip()

    established_year_raw = (row.get("established_year") or "").strip()
    established_year = _parse_int(established_year_raw, "established_year", errors, min_value=1800)
    student_capacity = _parse_int(row.get("student_capacity") or "", "student_capacity", errors, min_value=1)
    allowed_campuses = _parse_int(row.get("allowed_campuses") or "", "allowed_campuses", errors, min_value=1)
    is_active = _parse_bool(row.get("is_active"), default=True)

    if not name:
        errors.append("name is required")
    if not code:
        errors.append("code is required")
    if not email:
        errors.append("email is required")
    if not phone:
        errors.append("phone is required")
    if not principal_name:
        errors.append("principal_name is required")
    if not address:
        errors.append("address is required")
    if not city:
        errors.append("city is required")
    if not state:
        errors.append("state is required")
    if not established_year_raw:
        errors.append("established_year is required")

    payload = {
        "name": name,
        "code": code,
        "email": email,
        "phone": phone,
        "support_email": support_email,
        "website": website,
        "principal_name": principal_name,
        "board": board,
        "medium": medium,
        "established_year": established_year,
        "address": address,
        "address_line2": address_line2,
        "city": city,
        "state": state,
        "pincode": pincode,
        "student_capacity": student_capacity or 1000,
        "allowed_campuses": allowed_campuses or 1,
        "is_active": is_active,
    }
    return payload, errors


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.view")
def school_list(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    state = (request.GET.get("state") or "").strip()
    context = build_layout_context(request.user, current_section="schools")
    schools = _school_queryset_for_user(request.user)
    if query:
        schools = schools.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(city__icontains=query)
            | Q(state__icontains=query)
        )
    if status in {"active", "inactive"}:
        schools = schools.filter(is_active=(status == "active"))
    if state:
        schools = schools.filter(state__icontains=state)
    context["schools"] = schools
    context["stats"] = schools.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    context["can_manage_schools"] = has_permission(request.user, "schools.manage")
    context["can_create_schools"] = True # let's just make it true if user has manage permission, wait, let's keep request.user.role == 'SUPER_ADMIN' for import. Or let's pass state choices here.
    context["can_create_schools"] = request.user.role == "SUPER_ADMIN" and context["can_manage_schools"]
    context["can_edit_school_profile"] = context["can_manage_schools"]
    context["show_bulk_school_actions"] = request.user.role == "SUPER_ADMIN"
    context["state_choices"] = sorted(STATE_CITY_MAP.keys())
    context["filters"] = {"q": query, "status": status, "state": state}
    return render(request, "schools/list.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.view")
def school_detail(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    context = build_layout_context(request.user, current_section="schools")
    context["school"] = school
    context["can_manage_schools"] = has_permission(request.user, "schools.manage")
    context["can_manage_comm_settings"] = has_permission(request.user, "schools.comm_settings")
    context["can_edit_school_profile"] = context["can_manage_schools"]
    context["can_toggle_school_status"] = request.user.role == "SUPER_ADMIN" and context["can_manage_schools"]
    context["show_advanced_school_panels"] = request.user.role == "SUPER_ADMIN"
    context["active_students"] = Student.objects.filter(school=school, is_active=True).count()
    context["total_students"] = Student.objects.filter(school=school).count()
    context["classes"] = AcademicClass.objects.filter(school=school).count()
    context["attendance_sessions"] = AttendanceSession.objects.filter(school=school).count()
    context["fee_ledgers"] = StudentFeeLedger.objects.filter(school=school).count()
    context["exams"] = Exam.objects.filter(school=school).count()
    context["notices"] = Notice.objects.filter(school=school, is_published=True).count()
    User = get_user_model()
    context["teacher_count"] = User.objects.filter(role="TEACHER", school=school, is_active=True).count()
    context["staff_count"] = User.objects.filter(school=school, is_active=True).count()
    from apps.accounts.models import UserInvitation
    context["pending_invites"] = UserInvitation.objects.filter(user__school=school, accepted_at__isnull=True).count()

    subscription = (
        SchoolSubscription.objects.select_related("plan")
        .prefetch_related("plan__features")
        .filter(school=school)
        .first()
    )
    context["subscription"] = subscription
    context["enabled_features"] = sorted(enabled_feature_codes_for_school(school.id))
    context["campus_count"] = Campus.objects.filter(school=school, is_active=True).count()
    comm = SchoolCommunicationSettings.objects.filter(school=school).first()
    smtp_ok = bool(comm and comm.smtp_enabled and comm.smtp_host and comm.smtp_username and comm.smtp_from_email)
    wa_ok = bool(comm and comm.whatsapp_enabled and comm.whatsapp_provider and comm.whatsapp_provider != "NONE" and comm.whatsapp_access_token and comm.whatsapp_phone_number_id)
    current_year = AcademicYear.objects.filter(school=school, is_current=True).order_by("-start_date").first()
    class_master_count = ClassMaster.objects.filter(school=school, is_active=True).count()
    section_master_count = SectionMaster.objects.filter(school=school, is_active=True).count()
    setup_checks = [
        bool(context["campus_count"] > 0),
        bool(smtp_ok or wa_ok),
        bool(smtp_ok),
        bool(current_year),
        bool(class_master_count > 0),
        bool(section_master_count > 0),
        bool(context["classes"] > 0),
        bool(context["teacher_count"] > 0),
    ]
    setup_completed = sum(1 for item in setup_checks if item)
    setup_total = len(setup_checks)
    context["setup_completed"] = setup_completed
    context["setup_total"] = setup_total
    context["setup_completion_percent"] = int(round((setup_completed / setup_total) * 100)) if setup_total else 0
    impl = ImplementationProject.objects.filter(school=school).first()
    context["implementation_project"] = impl
    if impl:
        context["implementation_task_counts"] = {
            "total": ImplementationTask.objects.filter(project=impl).count(),
            "todo": ImplementationTask.objects.filter(project=impl, status="TODO").count(),
            "in_progress": ImplementationTask.objects.filter(project=impl, status="IN_PROGRESS").count(),
            "blocked": ImplementationTask.objects.filter(project=impl, status="BLOCKED").count(),
            "done": ImplementationTask.objects.filter(project=impl, status="DONE").count(),
        }
    return render(request, "schools/detail.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.manage")
def school_implementation(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    project, _ = ImplementationProject.objects.get_or_create(school=school)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "update_project":
            status = (request.POST.get("status") or "").strip()
            notes = (request.POST.get("notes") or "").strip()
            if status in dict(ImplementationProject.STATUS_CHOICES):
                project.status = status
            project.notes = notes
            project.save(update_fields=["status", "notes", "updated_at"])
            messages.success(request, "Implementation project updated.")
            return redirect(f"/schools/{school.id}/implementation/")

        if action == "create_task":
            title = (request.POST.get("title") or "").strip()
            if not title:
                messages.error(request, "Task title is required.")
                return redirect(f"/schools/{school.id}/implementation/")
            due_date = (request.POST.get("due_date") or "").strip() or None
            owner_id_raw = (request.POST.get("owner_id") or "").strip()
            owner_id = int(owner_id_raw) if owner_id_raw.isdigit() else None
            owner = get_user_model().objects.filter(id=owner_id).first() if owner_id else None
            ImplementationTask.objects.create(
                project=project,
                title=title,
                description=(request.POST.get("description") or "").strip(),
                status=(request.POST.get("task_status") or "TODO").strip() or "TODO",
                due_date=due_date,
                owner=owner,
                sort_order=int(request.POST.get("sort_order") or 0),
            )
            messages.success(request, "Task created.")
            return redirect(f"/schools/{school.id}/implementation/")

        if action == "update_task":
            task_id_raw = (request.POST.get("task_id") or "").strip()
            if not task_id_raw.isdigit():
                messages.error(request, "Invalid task update.")
                return redirect(f"/schools/{school.id}/implementation/")
            task = get_object_or_404(ImplementationTask.objects.select_related("project"), id=int(task_id_raw), project=project)
            task.title = (request.POST.get("title") or "").strip() or task.title
            task.description = (request.POST.get("description") or "").strip()
            status = (request.POST.get("task_status") or "").strip()
            if status in dict(ImplementationTask.STATUS_CHOICES):
                task.status = status
            due_date = (request.POST.get("due_date") or "").strip() or None
            task.due_date = due_date
            owner_id_raw = (request.POST.get("owner_id") or "").strip()
            owner_id = int(owner_id_raw) if owner_id_raw.isdigit() else None
            task.owner = get_user_model().objects.filter(id=owner_id).first() if owner_id else None
            sort_order_raw = (request.POST.get("sort_order") or "").strip()
            if sort_order_raw.isdigit():
                task.sort_order = int(sort_order_raw)
            task.save()
            messages.success(request, "Task updated.")
            return redirect(f"/schools/{school.id}/implementation/")

        if action == "delete_task":
            task_id_raw = (request.POST.get("task_id") or "").strip()
            if task_id_raw.isdigit():
                ImplementationTask.objects.filter(id=int(task_id_raw), project=project).delete()
                messages.success(request, "Task deleted.")
            return redirect(f"/schools/{school.id}/implementation/")

        messages.error(request, "Invalid action.")
        return redirect(f"/schools/{school.id}/implementation/")

    tasks = list(ImplementationTask.objects.select_related("owner").filter(project=project).order_by("sort_order", "id"))
    owner_qs = get_user_model().objects.filter(is_active=True)
    if request.user.role != "SUPER_ADMIN":
        owner_qs = owner_qs.filter(school_id=school.id)
    owners = list(owner_qs.only("id", "username").order_by("username")[:500])

    context = build_layout_context(request.user, current_section="schools")
    context.update({"school": school, "project": project, "tasks": tasks, "owners": owners})
    return render(request, "schools/implementation.html", context)


@role_required("SUPER_ADMIN")
@permission_required("schools.manage")
def school_toggle_status(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect(f"/schools/{school.id}/")

    action = (request.POST.get("action") or "").strip().lower()
    reason = (request.POST.get("reason") or "").strip()

    if action == "suspend":
        school.is_active = False
        school.save(update_fields=["is_active"])
        messages.success(request, f"School suspended. {('Reason: ' + reason) if reason else ''}".strip())
        return redirect(f"/schools/{school.id}/")

    if action == "resume":
        school.is_active = True
        school.save(update_fields=["is_active"])
        messages.success(request, "School resumed (active).")
        return redirect(f"/schools/{school.id}/")

    messages.error(request, "Invalid action.")
    return redirect(f"/schools/{school.id}/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.view")
def school_setup_checklist(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)

    comm = SchoolCommunicationSettings.objects.filter(school=school).first()
    smtp_ok = bool(comm and comm.smtp_enabled and comm.smtp_host and comm.smtp_username and comm.smtp_from_email)
    wa_ok = bool(comm and comm.whatsapp_enabled and comm.whatsapp_provider and comm.whatsapp_provider != "NONE" and comm.whatsapp_access_token and comm.whatsapp_phone_number_id)

    current_year = AcademicYear.objects.filter(school=school, is_current=True).order_by("-start_date").first()
    class_master_count = ClassMaster.objects.filter(school=school, is_active=True).count()
    section_master_count = SectionMaster.objects.filter(school=school, is_active=True).count()
    class_count = AcademicClass.objects.filter(school=school, is_active=True).count()
    campus_count = Campus.objects.filter(school=school, is_active=True).count()
    campus_limit = _campus_limit_for_school(school)

    User = get_user_model()
    teacher_count = User.objects.filter(role="TEACHER", school=school, is_active=True).count() if hasattr(User, "school") else User.objects.filter(role="TEACHER").count()

    campaign_url = f"/frontoffice/messages/campaigns/create/?school={school.id}" if request.user.role == "SUPER_ADMIN" else "/communication/manage/"
    campaign_cta = "Create campaign" if request.user.role == "SUPER_ADMIN" else "Open notices"

    checks = [
        {
            "label": "Campuses / Branches",
            "status": campus_count > 0,
            "meta": f"{campus_count} active{f' (limit {campus_limit})' if campus_limit else ''}",
            "url": f"/schools/{school.id}/campuses/",
            "cta": "Manage campuses",
        },
        {
            "label": "Email/WhatsApp setup",
            "status": smtp_ok or wa_ok,
            "meta": f"SMTP: {'OK' if smtp_ok else 'Not configured'} | WhatsApp: {'OK' if wa_ok else 'Not configured'}",
            "url": f"/schools/{school.id}/communication/",
            "cta": "Open settings",
        },
        {
            "label": "Send a test campaign",
            "status": smtp_ok,
            "meta": "Recommended after SMTP is enabled",
            "url": campaign_url,
            "cta": campaign_cta,
        },
        {
            "label": "Current academic year",
            "status": bool(current_year),
            "meta": current_year.name if current_year else "Not set",
            "url": "/academics/years/",
            "cta": "Set year",
        },
        {
            "label": "Class master",
            "status": class_master_count > 0,
            "meta": f"{class_master_count} items",
            "url": "/academics/masters/classes/",
            "cta": "Add classes",
        },
        {
            "label": "Section master",
            "status": section_master_count > 0,
            "meta": f"{section_master_count} items",
            "url": "/academics/masters/sections/",
            "cta": "Add sections",
        },
        {
            "label": "Academic classes created",
            "status": class_count > 0,
            "meta": f"{class_count} class-section records",
            "url": "/academics/",
            "cta": "Create class",
        },
        {
            "label": "Teachers onboarded",
            "status": teacher_count > 0,
            "meta": f"{teacher_count} teachers",
            "url": f"/schools/{school.id}/team/",
            "cta": "Invite teachers",
        },
    ]

    completed = sum(1 for c in checks if c["status"])
    context = build_layout_context(request.user, current_section="schools")
    context.update(
        {
            "school": school,
            "checks": checks,
            "completed": completed,
            "total": len(checks),
        }
    )
    return render(request, "schools/setup_checklist.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.team", redirect_to="dashboard")
def school_team(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    User = get_user_model()
    members = User.objects.filter(school=school).order_by("role", "username")

    from apps.accounts.models import UserInvitation

    raw_invites = UserInvitation.objects.select_related("user").filter(user__school=school).order_by("-created_at")[:100]
    invitations = []
    for inv in raw_invites:
        invitations.append(
            {
                "obj": inv,
                "activation_path": f"/activate/{inv.token}/",
                "activation_url": request.build_absolute_uri(f"/activate/{inv.token}/"),
            }
        )

    context = build_layout_context(request.user, current_section="schools")
    context.update(
        {
            "school": school,
            "members": members,
            "role_choices": list(SchoolTeamInviteForm.base_fields["role"].choices),
            "invitations": invitations,
            "prefill_role": (request.GET.get("role") or "").strip().upper(),
            "invite_form": SchoolTeamInviteForm(initial={"role": (request.GET.get("role") or "").strip().upper()}),
            "can_view_all_invitations": request.user.role == "SUPER_ADMIN",
        }
    )
    return render(request, "schools/team.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.manage")
def campus_list(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    campuses = Campus.objects.filter(school=school).order_by("-is_main", "name", "id")
    context = build_layout_context(request.user, current_section="schools")
    context.update(
        {
            "school": school,
            "campuses": campuses,
            "campus_limit": _campus_limit_for_school(school),
            "active_campus_count": Campus.objects.filter(school=school, is_active=True).count(),
        }
    )
    return render(request, "schools/campuses/list.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN")
@permission_required("schools.manage")
def campus_create(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    campus_limit = _campus_limit_for_school(school)
    active_count = Campus.objects.filter(school=school, is_active=True).count()
    if campus_limit and active_count >= campus_limit:
        messages.error(request, f"Campus limit reached (max {campus_limit}).")
        return redirect(f"/schools/{school.id}/campuses/")

    if request.method == "POST":
        form = CampusForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please fix the errors and try again.")
        else:
            campus = form.save(commit=False)
            campus.school = school
            if campus.is_main or not Campus.objects.filter(school=school, is_main=True).exists():
                Campus.objects.filter(school=school, is_main=True).update(is_main=False)
                campus.is_main = True
            campus.save()
            messages.success(request, "Campus created.")
            return redirect(f"/schools/{school.id}/campuses/")
    else:
        form = CampusForm()

    context = build_layout_context(request.user, current_section="schools")
    context.update({"school": school, "form": form, "campus_limit": campus_limit, "active_campus_count": active_count})
    return render(request, "schools/campuses/create.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN")
@permission_required("schools.manage")
def campus_edit(request, id, campus_id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    campus = get_object_or_404(Campus.objects.filter(school=school), id=campus_id)

    if request.method == "POST":
        form = CampusForm(request.POST, instance=campus)
        if not form.is_valid():
            messages.error(request, "Please fix the errors and try again.")
        else:
            updated = form.save(commit=False)
            if updated.is_main or not Campus.objects.filter(school=school, is_main=True).exclude(id=campus.id).exists():
                Campus.objects.filter(school=school, is_main=True).exclude(id=campus.id).update(is_main=False)
                updated.is_main = True
            updated.save()
            messages.success(request, "Campus updated.")
            return redirect(f"/schools/{school.id}/campuses/")
    else:
        form = CampusForm(instance=campus)

    context = build_layout_context(request.user, current_section="schools")
    context.update({"school": school, "campus": campus, "form": form})
    return render(request, "schools/campuses/edit.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN")
@permission_required("schools.manage")
def campus_delete(request, id, campus_id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    campus = get_object_or_404(Campus.objects.filter(school=school), id=campus_id)

    if request.method == "POST":
        if campus.is_main:
            remaining = Campus.objects.filter(school=school).exclude(id=campus.id).order_by("-is_active", "id")
            if not remaining.exists():
                messages.error(request, "You cannot delete the only (main) campus. Create another campus first.")
                return redirect(f"/schools/{school.id}/campuses/")
            promoted = remaining.first()
            promoted.is_main = True
            promoted.save(update_fields=["is_main"])
        campus.delete()
        messages.success(request, "Campus deleted.")
        return redirect(f"/schools/{school.id}/campuses/")

    messages.error(request, "Invalid delete request.")
    return redirect(f"/schools/{school.id}/campuses/")


def _send_team_invite_email(request, invitation, recipient_email):
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    user = invitation.user
    activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
    subject = "Activate your School ERP account"
    context = {"user": user, "activation_url": activation_url}
    text_body = render_to_string("emails/invitation.txt", context)
    html_body = render_to_string("emails/invitation.html", context)
    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[recipient_email])
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    return activation_url


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.team", redirect_to="dashboard")
def school_team_invite(request, id):
    from datetime import timedelta

    from django.utils import timezone

    from apps.accounts.models import User, UserInvitation

    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    if request.method != "POST":
        messages.error(request, "Invalid invite request.")
        return redirect(f"/schools/{school.id}/team/")

    ip = (request.META.get("REMOTE_ADDR") or "")[:64]
    if throttle_hit(
        f"throttle:school_team_invite:uid:{request.user.id}:school:{school.id}:ip:{ip}",
        limit=int(getattr(settings, "THROTTLE_SCHOOL_TEAM_INVITES_PER_15M", 40)),
        window_seconds=15 * 60,
    ):
        messages.error(request, "Too many invitation attempts. Please wait a few minutes and try again.")
        return redirect(f"/schools/{school.id}/team/")

    form = SchoolTeamInviteForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please fix the invite form errors and try again.")
        return redirect(f"/schools/{school.id}/team/")

    username = form.cleaned_data["username"].strip()
    email = (form.cleaned_data.get("email") or "").strip()
    first_name = (form.cleaned_data.get("first_name") or "").strip()
    last_name = (form.cleaned_data.get("last_name") or "").strip()
    role = form.cleaned_data["role"].strip()

    if User.objects.filter(username=username).exists():
        messages.error(request, "That username already exists.")
        return redirect(f"/schools/{school.id}/team/")

    user = User.objects.create(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        school=school,
        is_active=False,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])

    expires_at = timezone.now() + timedelta(days=7)
    invitation = UserInvitation.objects.create(user=user, created_by=request.user, expires_at=expires_at)

    if email:
        try:
            activation_url = _send_team_invite_email(request, invitation, email)
            invitation.sent_to = email
            invitation.sent_at = timezone.now()
            invitation.send_error = ""
            invitation.save(update_fields=["sent_to", "sent_at", "send_error"])
            messages.success(request, f"Invitation emailed to {email}.")
        except Exception as exc:
            activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
            invitation.sent_to = email
            invitation.sent_at = None
            invitation.send_error = str(exc)
            invitation.save(update_fields=["sent_to", "sent_at", "send_error"])
            messages.warning(request, f"Invitation created but email failed. Activation link: {activation_url}")
    else:
        activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
        messages.success(request, f"Invitation created. Activation link: {activation_url}")

    return redirect(f"/schools/{school.id}/team/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.team", redirect_to="dashboard")
def school_team_resend_invite(request, id, invitation_id):
    from datetime import timedelta

    from django.utils import timezone

    from apps.accounts.models import UserInvitation

    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)
    invitation = get_object_or_404(UserInvitation.objects.select_related("user"), id=invitation_id, user__school=school)

    if request.method != "POST":
        messages.error(request, "Invalid resend request.")
        return redirect(f"/schools/{school.id}/team/")

    ip = (request.META.get("REMOTE_ADDR") or "")[:64]
    if throttle_hit(
        f"throttle:school_team_resend:uid:{request.user.id}:school:{school.id}:ip:{ip}",
        limit=int(getattr(settings, "THROTTLE_SCHOOL_TEAM_RESENDS_PER_15M", 80)),
        window_seconds=15 * 60,
    ):
        messages.error(request, "Too many resend attempts. Please wait a few minutes and try again.")
        return redirect(f"/schools/{school.id}/team/")

    if invitation.is_accepted():
        messages.info(request, "This invitation was already accepted.")
        return redirect(f"/schools/{school.id}/team/")

    recipient_email = (invitation.sent_to or invitation.user.email or "").strip()
    invitation.token = uuid.uuid4()
    invitation.expires_at = timezone.now() + timedelta(days=7)
    invitation.sent_at = None
    invitation.send_error = ""
    invitation.save(update_fields=["token", "expires_at", "sent_at", "send_error"])

    activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
    if recipient_email:
        try:
            _send_team_invite_email(request, invitation, recipient_email)
            invitation.sent_at = timezone.now()
            invitation.sent_to = recipient_email
            invitation.save(update_fields=["sent_at", "sent_to"])
            messages.success(request, f"Invitation resent to {recipient_email}.")
        except Exception as exc:
            invitation.send_error = str(exc)
            invitation.sent_to = recipient_email
            invitation.save(update_fields=["send_error", "sent_to"])
            messages.warning(request, f"Resend failed. Activation link: {activation_url}")
    else:
        messages.success(request, f"Activation link refreshed: {activation_url}")

    return redirect(f"/schools/{school.id}/team/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.comm_settings")
def school_communication_settings(request, id=None):
    if request.user.role == "SUPER_ADMIN":
        if id is None:
            messages.error(request, "Choose a school first to manage communication settings.")
            return redirect("/schools/")
        school = get_object_or_404(School.objects.filter(is_active=True), id=id)
    else:
        if not request.user.school_id:
            messages.error(request, "Your account is not linked to any school.")
            return redirect("dashboard")
        school = get_object_or_404(School.objects.filter(id=request.user.school_id, is_active=True), id=request.user.school_id)

    settings_obj = SchoolCommunicationSettings.objects.filter(school=school).first()
    if not settings_obj:
        settings_obj = SchoolCommunicationSettings.objects.create(school=school)

    form = SchoolCommunicationSettingsForm(instance=settings_obj)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "test_email":
            to_email = (request.POST.get("to_email") or "").strip()
            if not to_email:
                messages.error(request, "Recipient email is required for test.")
                return redirect(request.path)
            try:
                send_email_via_school_smtp(
                    settings_obj=settings_obj,
                    to_email=to_email,
                    subject=f"{school.name} SMTP Test",
                    body="This is a test email from your SchoolFlow school SMTP settings.",
                )
                messages.success(request, f"Test email sent to {to_email}.")
            except Exception as exc:
                messages.error(request, f"Test email failed: {exc}")
            return redirect(request.path)

        form = SchoolCommunicationSettingsForm(request.POST, instance=settings_obj)
        if not form.is_valid():
            messages.error(request, "Please fix the errors and try again.")
        else:
            updated = form.save(commit=False)
            password = (request.POST.get("smtp_password") or "").strip()
            if password:
                updated.smtp_password = password
            else:
                updated.smtp_password = settings_obj.smtp_password
            wa_token = (request.POST.get("whatsapp_access_token") or "").strip()
            if wa_token:
                updated.whatsapp_access_token = wa_token
            else:
                updated.whatsapp_access_token = settings_obj.whatsapp_access_token
            wa_secret = (request.POST.get("whatsapp_webhook_secret") or "").strip()
            if wa_secret:
                updated.whatsapp_webhook_secret = wa_secret
            else:
                updated.whatsapp_webhook_secret = settings_obj.whatsapp_webhook_secret
            updated.save()
            messages.success(request, "Communication settings updated.")
            return redirect(request.path)

    context = build_layout_context(request.user, current_section="schools")
    context.update(
        {
            "school": school,
            "comm": settings_obj,
            "form": form,
            "whatsapp_provider_choices": SchoolCommunicationSettings.WHATSAPP_PROVIDER_CHOICES,
        }
    )
    return render(request, "schools/communication_settings.html", context)


@role_required("SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.view")
def school_profile(request):
    if not request.user.school_id:
        messages.error(request, "Your account is not linked to any school.")
        return redirect("dashboard")
    return redirect(f"/schools/{request.user.school_id}/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.view")
def school_export_csv(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    state = (request.GET.get("state") or "").strip()

    schools = _school_queryset_for_user(request.user)
    if query:
        schools = schools.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(city__icontains=query)
            | Q(state__icontains=query)
        )
    if status in {"active", "inactive"}:
        schools = schools.filter(is_active=(status == "active"))
    if state:
        schools = schools.filter(state__icontains=state)

    raw_ids = (request.GET.get("school_ids") or request.GET.get("ids") or "").strip()
    if raw_ids:
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if ids:
            schools = schools.filter(id__in=sorted(set(ids)))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="schools_export.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "name",
            "code",
            "email",
            "phone",
            "principal_name",
            "established_year",
            "city",
            "state",
            "student_capacity",
            "allowed_campuses",
            "is_active",
        ]
    )
    for school in schools.order_by("name"):
        writer.writerow(
            [
                school.name,
                school.code,
                school.email,
                school.phone,
                school.principal_name,
                school.established_year,
                school.city,
                school.state,
                school.student_capacity,
                school.allowed_campuses,
                "True" if school.is_active else "False",
            ]
        )
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.view")
def school_export_excel(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    state = (request.GET.get("state") or "").strip()

    schools = _school_queryset_for_user(request.user)
    if query:
        schools = schools.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(city__icontains=query)
            | Q(state__icontains=query)
        )
    if status in {"active", "inactive"}:
        schools = schools.filter(is_active=(status == "active"))
    if state:
        schools = schools.filter(state__icontains=state)

    raw_ids = (request.GET.get("school_ids") or request.GET.get("ids") or "").strip()
    if raw_ids:
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if ids:
            schools = schools.filter(id__in=sorted(set(ids)))

    # No extra deps: send an Excel-friendly HTML table as .xls
    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="schools.xls"'

    def esc(value):
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    rows = [
        "<table>",
        "<thead><tr>",
        "<th>name</th><th>code</th><th>email</th><th>phone</th><th>principal_name</th>"
        "<th>established_year</th><th>city</th><th>state</th><th>student_capacity</th><th>allowed_campuses</th><th>is_active</th>",
        "</tr></thead>",
        "<tbody>",
    ]

    for school in schools.order_by("name"):
        rows.append(
            "<tr>"
            f"<td>{esc(school.name)}</td>"
            f"<td>{esc(school.code)}</td>"
            f"<td>{esc(school.email)}</td>"
            f"<td>{esc(school.phone)}</td>"
            f"<td>{esc(school.principal_name)}</td>"
            f"<td>{esc(school.established_year)}</td>"
            f"<td>{esc(school.city)}</td>"
            f"<td>{esc(school.state)}</td>"
            f"<td>{esc(school.student_capacity)}</td>"
            f"<td>{esc(school.allowed_campuses)}</td>"
            f"<td>{'yes' if school.is_active else 'no'}</td>"
            "</tr>"
        )

    rows.append("</tbody></table>")
    response.write("".join(rows))
    return response


@role_required("SUPER_ADMIN")
@permission_required("schools.manage")
def school_import(request):
    if request.method == "POST":
        ip = (request.META.get("REMOTE_ADDR") or "")[:64]
        if throttle_hit(
            f"throttle:schools_import:uid:{request.user.id}:ip:{ip}",
            limit=int(getattr(settings, "THROTTLE_SCHOOLS_IMPORT_PER_15M", 10)),
            window_seconds=15 * 60,
        ):
            messages.error(request, "Too many school imports. Please wait a few minutes and try again.")
            return redirect("/schools/import/")

        stage = (request.POST.get("stage") or "preview").strip().lower()
        if stage == "confirm":
            preview = request.session.get(SCHOOL_IMPORT_SESSION_KEY) or {}
            rows = preview.get("rows") or []
            if not rows:
                messages.error(request, "Import preview expired. Please upload the file again.")
                return redirect("/schools/import/")

            created = 0
            updated = 0
            skipped = 0
            errors_out: list[dict] = []

            for row in rows:
                payload = row.get("payload") or {}
                row_errors = row.get("errors") or []
                if row_errors:
                    skipped += 1
                    errors_out.append({"row": row.get("row_index"), "errors": "; ".join(row_errors), **(row.get("raw") or {})})
                    continue

                code = (payload.get("code") or "").strip()
                existing = School.objects.filter(code=code).only("id").first()
                if existing:
                    School.objects.filter(id=existing.id).update(**payload)
                    school_obj = School.objects.get(id=existing.id)
                    updated += 1
                else:
                    school_obj = School.objects.create(**payload)
                    created += 1

                Campus.objects.get_or_create(
                    school=school_obj,
                    is_main=True,
                    defaults={
                        "name": f"{school_obj.name} (Main Campus)",
                        "code": f"{school_obj.code}-MAIN",
                        "email": school_obj.email,
                        "phone": school_obj.phone,
                        "address": school_obj.address,
                        "city": school_obj.city,
                        "state": school_obj.state,
                        "pincode": school_obj.pincode,
                        "is_active": True,
                    },
                )

                default_plan = (
                    SubscriptionPlan.objects.filter(code="SILVER", is_active=True).first()
                    or SubscriptionPlan.objects.filter(is_active=True).order_by("id").first()
                )
                if default_plan:
                    SchoolSubscription.objects.get_or_create(
                        school=school_obj,
                        defaults={
                            "plan": default_plan,
                            "status": "TRIAL",
                            "starts_on": timezone.localdate(),
                            "ends_on": timezone.localdate() + timedelta(days=14),
                        },
                    )

            request.session[SCHOOL_IMPORT_SESSION_KEY] = {"errors": errors_out}
            parts = []
            if created:
                parts.append(f"{created} created")
            if updated:
                parts.append(f"{updated} updated")
            if skipped:
                parts.append(f"{skipped} skipped")
            if parts:
                messages.success(request, "Schools import summary: " + ", ".join(parts) + ".")
            else:
                messages.info(request, "No rows were imported.")

            return redirect("/schools/import/")

        import_file = request.FILES.get("import_file")
        if not import_file:
            messages.error(request, "Choose a CSV file to import.")
            return redirect("/schools/import/")

        extension = import_file.name.lower().rsplit(".", 1)[-1]
        if extension != "csv":
            messages.error(request, "Only CSV is supported for Schools import right now.")
            return redirect("/schools/import/")

        try:
            raw_rows = _read_csv_upload(import_file)
        except Exception:
            messages.error(request, "We could not read that file. Please check headers and try again.")
            return redirect("/schools/import/")

        preview_rows: list[dict] = []
        invalid_count = 0
        for idx, raw in enumerate(raw_rows[:5000], start=1):
            payload, row_errors = _validate_school_import_row(raw)
            if row_errors:
                invalid_count += 1
            preview_rows.append(
                {
                    "row_index": idx,
                    "raw": raw,
                    "cells": [raw.get(h, "") for h in SCHOOL_IMPORT_HEADERS],
                    "payload": payload,
                    "errors": row_errors,
                }
            )

        request.session[SCHOOL_IMPORT_SESSION_KEY] = {"rows": preview_rows, "errors": []}

        context = build_layout_context(request.user, current_section="schools")
        context.update(
            {
                "headers": SCHOOL_IMPORT_HEADERS,
                "preview_rows": preview_rows[:50],
                "total_rows": len(preview_rows),
                "invalid_count": invalid_count,
            }
        )
        return render(request, "schools/import_preview.html", context)

    context = build_layout_context(request.user, current_section="schools")
    context.update({"headers": SCHOOL_IMPORT_HEADERS})
    return render(request, "schools/import.html", context)


@role_required("SUPER_ADMIN")
@permission_required("schools.manage")
def school_import_errors_csv(request):
    preview = request.session.get(SCHOOL_IMPORT_SESSION_KEY) or {}
    errors_out = preview.get("errors") or []
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="schools_import_errors.csv"'
    writer = csv.writer(response)
    writer.writerow(["row", "errors", *SCHOOL_IMPORT_HEADERS])
    for item in errors_out[:20000]:
        writer.writerow(
            [
                item.get("row") or "",
                _sanitize_csv_cell(item.get("errors") or ""),
                *[_sanitize_csv_cell(item.get(h) or "") for h in SCHOOL_IMPORT_HEADERS],
            ]
        )
    return response


@role_required("SUPER_ADMIN")
@permission_required("schools.manage")
def school_import_sample(request, file_type):
    if file_type != "csv":
        messages.error(request, "Unsupported sample file type.")
        return redirect("/schools/import/")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="schools-import-sample.csv"'
    writer = csv.writer(response)
    writer.writerow(SCHOOL_IMPORT_HEADERS)
    writer.writerow(
        [
            "Beta School",
            "BETA01",
            "beta@example.com",
            "9999999999",
            "support@example.com",
            "https://betaschool.example.com",
            "Principal Beta",
            "CBSE",
            "English",
            "2005",
            "Main road",
            "",
            "Bhopal",
            "Madhya Pradesh",
            "462001",
            "1200",
            "1",
            "yes",
        ]
    )
    return response


@role_required("SUPER_ADMIN")
@permission_required("schools.manage")
def school_create(request):
    if request.method == "POST":
        form = SchoolForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Please fix the errors and try again.")
            context = build_layout_context(request.user, current_section="schools")
            context["state_city_map"] = STATE_CITY_MAP
            context["form"] = form
            return render(request, "schools/create.html", context)

        school = form.save(commit=False)
        allowed_campuses = int(form.cleaned_data.get("allowed_campuses") or 1)

        if request.user.role != "SUPER_ADMIN":
            campus_limit = campus_limit_for_school(request.user.school_id)
            if campus_limit and allowed_campuses > campus_limit:
                messages.error(request, f"Campus limit exceeded for your plan (max {campus_limit}).")
                context = build_layout_context(request.user, current_section="schools")
                context["state_city_map"] = STATE_CITY_MAP
                context["form"] = form
                return render(request, "schools/create.html", context)

        school.allowed_campuses = allowed_campuses
        school.save()

        Campus.objects.get_or_create(
            school=school,
            is_main=True,
            defaults={
                "name": f"{school.name} (Main Campus)",
                "code": f"{school.code}-MAIN",
                "email": school.email,
                "phone": school.phone,
                "address": school.address,
                "city": school.city,
                "state": school.state,
                "pincode": school.pincode,
                "is_active": True,
            },
        )
        default_plan = (
            SubscriptionPlan.objects.filter(code="SILVER", is_active=True).first()
            or SubscriptionPlan.objects.filter(is_active=True).order_by("id").first()
        )
        if default_plan:
            SchoolSubscription.objects.get_or_create(
                school=school,
                defaults={
                    "plan": default_plan,
                    "status": "TRIAL",
                    "starts_on": timezone.localdate(),
                    "ends_on": timezone.localdate() + timedelta(days=14),
                },
            )
        messages.success(request, "School profile created successfully.")
        return redirect(reverse("school-list"))

    context = build_layout_context(request.user, current_section="schools")
    context["state_city_map"] = STATE_CITY_MAP
    context["form"] = SchoolForm()
    return render(request, "schools/create.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL")
@permission_required("schools.manage")
def school_update(request, id):
    school = get_object_or_404(_school_queryset_for_user(request.user), id=id)

    if request.method == "POST":
        form = SchoolForm(request.POST, request.FILES, instance=school)
        if not form.is_valid():
            messages.error(request, "Please fix the errors and try again.")
            context = build_layout_context(request.user, current_section="schools")
            context["school"] = school
            context["state_city_map"] = STATE_CITY_MAP
            context["form"] = form
            return render(request, "schools/edit.html", context)

        allowed_campuses = int(form.cleaned_data.get("allowed_campuses") or school.allowed_campuses or 1)

        if request.user.role != "SUPER_ADMIN":
            campus_limit = campus_limit_for_school(school.id)
            if campus_limit and allowed_campuses > campus_limit:
                messages.error(request, f"Campus limit exceeded for your plan (max {campus_limit}).")
                context = build_layout_context(request.user, current_section="schools")
                context["school"] = school
                context["state_city_map"] = STATE_CITY_MAP
                context["form"] = form
                return render(request, "schools/edit.html", context)

        school = form.save(commit=False)
        school.allowed_campuses = allowed_campuses
        school.save()
        messages.success(request, "School profile updated.")
        return redirect(reverse("school-list"))

    context = build_layout_context(request.user, current_section="schools")
    context["school"] = school
    context["state_city_map"] = STATE_CITY_MAP
    context["form"] = SchoolForm(instance=school)
    return render(request, "schools/edit.html", context)


@role_required("SUPER_ADMIN")
@permission_required("schools.manage")
def school_delete(request, id):
    school = get_object_or_404(School, id=id)

    if request.method == "POST":
        school.delete()
        messages.success(request, "School removed successfully.")
        return redirect(reverse("school-list"))

    messages.error(request, "Invalid delete request.")
    return redirect(reverse("school-list"))
