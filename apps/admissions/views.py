from datetime import date as dt_date
from urllib.parse import urlencode

from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.academics.models import AcademicYear, ClassMaster, SectionMaster
from apps.core.permissions import has_permission, role_required
from apps.core.tenancy import (
    allowed_school_ids_for_user,
    school_scope_for_user,
    selected_school_for_request,
)
from apps.core.ui import build_layout_context
from apps.frontoffice.models import Enquiry

from .models import AdmissionApplication, AdmissionDocument, AdmissionEvent


def _school_scope(user):
    return school_scope_for_user(user)


def _selected_school(request):
    return selected_school_for_request(request)


def _school_ids_for_user(user):
    return allowed_school_ids_for_user(user)


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return dt_date.fromisoformat(value)
    except Exception:
        return None


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_list(request):
    if not has_permission(request.user, "admissions.view"):
        messages.error(request, "You do not have permission to view admissions.")
        return redirect("dashboard")

    school = _selected_school(request)
    school_ids = _school_ids_for_user(request.user)

    qs = AdmissionApplication.objects.select_related("school", "academic_year", "enquiry").filter(
        school_id__in=school_ids
    )
    if school:
        qs = qs.filter(school=school)

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    class_id = (request.GET.get("class") or "").strip()
    from_date = _parse_date(request.GET.get("from"))
    to_date = _parse_date(request.GET.get("to"))

    if q:
        qs = qs.filter(
            models.Q(student_name__icontains=q)
            | models.Q(application_no__icontains=q)
            | models.Q(phone__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if class_id:
        qs = qs.filter(desired_class_master_id=class_id)
    if from_date:
        qs = qs.filter(created_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__date__lte=to_date)

    current_section = (
        "admissions"
        if request.user.role in {"SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL"}
        else "frontoffice"
    )
    context = build_layout_context(request.user, current_section=current_section)
    can_manage_admissions = has_permission(request.user, "admissions.manage")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "applications": qs.order_by("-created_at")[:500],
            "status_choices": AdmissionApplication.STATUS_CHOICES,
            "class_options": ClassMaster.objects.filter(school_id__in=school_ids).order_by("name"),
            "filters": {
                "q": q,
                "status": status,
                "class": class_id,
                "from": request.GET.get("from") or "",
                "to": request.GET.get("to") or "",
            },
            "can_manage_admissions": can_manage_admissions,
        }
    )
    return render(request, "admissions/application_list.html", context)


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_create(request):
    if not has_permission(request.user, "admissions.manage"):
        messages.error(request, "You do not have permission to create admissions.")
        return redirect("admission-list")

    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a school first.")
        return redirect("/frontoffice/")

    school_ids = _school_ids_for_user(request.user)
    if school.id not in school_ids:
        messages.error(request, "Invalid school selection.")
        return redirect("/frontoffice/")

    enquiry = None
    enquiry_id = (request.GET.get("enquiry") or "").strip()
    if enquiry_id:
        enquiry = get_object_or_404(Enquiry, id=enquiry_id, school_id__in=school_ids)
        existing = AdmissionApplication.objects.filter(enquiry=enquiry).first()
        if existing:
            messages.info(request, "Admission application already exists for this enquiry.")
            return redirect("admission-detail", application_id=existing.id)

    if request.method == "POST":
        academic_year_id = (request.POST.get("academic_year_id") or "").strip() or None
        desired_class_master_id = (
            request.POST.get("desired_class_master_id") or ""
        ).strip() or None
        desired_section_master_id = (
            request.POST.get("desired_section_master_id") or ""
        ).strip() or None

        app = AdmissionApplication.objects.create(
            school=school,
            enquiry=enquiry,
            academic_year_id=academic_year_id,
            status=(request.POST.get("status") or "DRAFT").strip().upper() or "DRAFT",
            student_name=(request.POST.get("student_name") or "").strip(),
            guardian_name=(request.POST.get("guardian_name") or "").strip(),
            phone=(request.POST.get("phone") or "").strip(),
            email=(request.POST.get("email") or "").strip(),
            address=(request.POST.get("address") or "").strip(),
            previous_school=(request.POST.get("previous_school") or "").strip(),
            desired_class_master_id=desired_class_master_id,
            desired_class_text=(request.POST.get("desired_class_text") or "").strip(),
            desired_section_master_id=desired_section_master_id,
            desired_section_text=(request.POST.get("desired_section_text") or "").strip(),
            notes=(request.POST.get("notes") or "").strip(),
            created_by=request.user,
            updated_by=request.user,
        )
        AdmissionEvent.objects.create(
            application=app,
            school=school,
            actor=request.user,
            action="CREATED",
            message="Admission application created.",
        )

        if enquiry:
            # Soft signal in frontoffice funnel
            if enquiry.status == "NEW":
                enquiry.status = "ADMISSION_IN_PROGRESS"
                enquiry.updated_at = timezone.now()
                enquiry.save(update_fields=["status", "updated_at"])

        messages.success(request, "Admission application created.")
        return redirect("admission-detail", application_id=app.id)

    initial = {
        "student_name": getattr(enquiry, "student_name", "") if enquiry else "",
        "guardian_name": getattr(enquiry, "guardian_name", "") if enquiry else "",
        "phone": getattr(enquiry, "phone", "") if enquiry else "",
        "email": getattr(enquiry, "email", "") if enquiry else "",
        "address": getattr(enquiry, "address", "") if enquiry else "",
        "previous_school": getattr(enquiry, "previous_school", "") if enquiry else "",
        "desired_class_text": getattr(enquiry, "class_interested", "") if enquiry else "",
        "status": "SUBMITTED" if enquiry else "DRAFT",
    }

    current_section = (
        "admissions"
        if request.user.role in {"SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL"}
        else "frontoffice"
    )
    context = build_layout_context(request.user, current_section=current_section)
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "enquiry": enquiry,
            "initial": initial,
            "status_choices": AdmissionApplication.STATUS_CHOICES,
            "academic_year_options": AcademicYear.objects.filter(school_id__in=school_ids).order_by(
                "-start_date", "-id"
            ),
            "class_options": ClassMaster.objects.filter(school_id__in=school_ids).order_by("name"),
            "section_options": SectionMaster.objects.filter(school_id__in=school_ids).order_by(
                "name"
            ),
        }
    )
    return render(request, "admissions/application_form.html", context)


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_detail(request, application_id):
    if not has_permission(request.user, "admissions.view"):
        messages.error(request, "You do not have permission to view admissions.")
        return redirect("dashboard")

    school_ids = _school_ids_for_user(request.user)
    app = get_object_or_404(
        AdmissionApplication.objects.select_related(
            "school", "academic_year", "enquiry"
        ).prefetch_related("documents", "events"),
        id=application_id,
        school_id__in=school_ids,
    )

    current_section = (
        "admissions"
        if request.user.role in {"SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL"}
        else "frontoffice"
    )
    context = build_layout_context(request.user, current_section=current_section)
    can_manage_admissions = has_permission(request.user, "admissions.manage")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": _selected_school(request),
            "application": app,
            "status_choices": AdmissionApplication.STATUS_CHOICES,
            "can_manage_admissions": can_manage_admissions,
            "can_create_student_from_admission": has_permission(request.user, "students.manage")
            or has_permission(request.user, "students.*"),
        }
    )
    return render(request, "admissions/application_detail.html", context)


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_edit(request, application_id):
    if not has_permission(request.user, "admissions.manage"):
        messages.error(request, "You do not have permission to edit admissions.")
        return redirect("admission-detail", application_id=application_id)

    school_ids = _school_ids_for_user(request.user)
    app = get_object_or_404(AdmissionApplication, id=application_id, school_id__in=school_ids)

    if request.method == "POST":
        app.student_name = (request.POST.get("student_name") or "").strip()
        app.guardian_name = (request.POST.get("guardian_name") or "").strip()
        app.phone = (request.POST.get("phone") or "").strip()
        app.email = (request.POST.get("email") or "").strip()
        app.address = (request.POST.get("address") or "").strip()
        app.previous_school = (request.POST.get("previous_school") or "").strip()
        app.notes = (request.POST.get("notes") or "").strip()

        app.academic_year_id = (request.POST.get("academic_year_id") or "").strip() or None
        app.desired_class_master_id = (
            request.POST.get("desired_class_master_id") or ""
        ).strip() or None
        app.desired_class_text = (request.POST.get("desired_class_text") or "").strip()
        app.desired_section_master_id = (
            request.POST.get("desired_section_master_id") or ""
        ).strip() or None
        app.desired_section_text = (request.POST.get("desired_section_text") or "").strip()
        app.updated_by = request.user
        app.save()

        AdmissionEvent.objects.create(
            application=app,
            school=app.school,
            actor=request.user,
            action="UPDATED",
            message="Application updated.",
        )
        messages.success(request, "Admission application updated.")
        return redirect("admission-detail", application_id=app.id)

    current_section = (
        "admissions"
        if request.user.role in {"SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL"}
        else "frontoffice"
    )
    context = build_layout_context(request.user, current_section=current_section)
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": _selected_school(request),
            "application": app,
            "status_choices": AdmissionApplication.STATUS_CHOICES,
            "academic_year_options": AcademicYear.objects.filter(school_id__in=school_ids).order_by(
                "-start_date", "-id"
            ),
            "class_options": ClassMaster.objects.filter(school_id__in=school_ids).order_by("name"),
            "section_options": SectionMaster.objects.filter(school_id__in=school_ids).order_by(
                "name"
            ),
        }
    )
    return render(request, "admissions/application_edit.html", context)


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_delete(request, application_id):
    if not has_permission(request.user, "admissions.manage"):
        messages.error(request, "You do not have permission to delete admissions.")
        return redirect("admission-detail", application_id=application_id)

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("admission-detail", application_id=application_id)

    school_ids = _school_ids_for_user(request.user)
    app = get_object_or_404(AdmissionApplication, id=application_id, school_id__in=school_ids)
    app.delete()
    messages.success(request, "Admission application deleted.")
    return redirect("admission-list")


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_status(request, application_id):
    if not has_permission(request.user, "admissions.manage"):
        messages.error(request, "You do not have permission to update admissions.")
        return redirect("admission-detail", application_id=application_id)

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("admission-detail", application_id=application_id)

    school_ids = _school_ids_for_user(request.user)
    app = get_object_or_404(AdmissionApplication, id=application_id, school_id__in=school_ids)
    new_status = (request.POST.get("status") or "").strip().upper()
    valid = {c[0] for c in AdmissionApplication.STATUS_CHOICES}
    if new_status not in valid:
        messages.error(request, "Invalid status.")
        return redirect("admission-detail", application_id=application_id)

    old_status = app.status
    app.status = new_status
    app.updated_by = request.user
    app.save(update_fields=["status", "updated_by", "updated_at"])

    AdmissionEvent.objects.create(
        application=app,
        school=app.school,
        actor=request.user,
        action="STATUS_CHANGED",
        message=f"Status: {old_status} -> {new_status}",
        meta={"from": old_status, "to": new_status},
    )
    messages.success(request, "Status updated.")
    return redirect("admission-detail", application_id=application_id)


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_document_add(request, application_id):
    if not has_permission(request.user, "admissions.manage"):
        messages.error(request, "You do not have permission to manage documents.")
        return redirect("admission-detail", application_id=application_id)

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("admission-detail", application_id=application_id)

    school_ids = _school_ids_for_user(request.user)
    app = get_object_or_404(AdmissionApplication, id=application_id, school_id__in=school_ids)

    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "Document title is required.")
        return redirect("admission-detail", application_id=application_id)

    AdmissionDocument.objects.create(application=app, title=title)
    AdmissionEvent.objects.create(
        application=app,
        school=app.school,
        actor=request.user,
        action="UPDATED",
        message="Document checklist updated.",
    )
    messages.success(request, "Document added to checklist.")
    return redirect("admission-detail", application_id=application_id)


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_document_toggle_received(request, application_id, document_id):
    if not has_permission(request.user, "admissions.manage"):
        messages.error(request, "You do not have permission to manage documents.")
        return redirect("admission-detail", application_id=application_id)

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("admission-detail", application_id=application_id)

    school_ids = _school_ids_for_user(request.user)
    app = get_object_or_404(AdmissionApplication, id=application_id, school_id__in=school_ids)
    doc = get_object_or_404(AdmissionDocument, id=document_id, application=app)

    doc.is_received = not doc.is_received
    doc.received_at = timezone.now() if doc.is_received else None
    doc.save(update_fields=["is_received", "received_at"])

    AdmissionEvent.objects.create(
        application=app,
        school=app.school,
        actor=request.user,
        action="DOCUMENT_RECEIVED",
        message=f"{doc.title}: {'received' if doc.is_received else 'not received'}",
        meta={"document_id": doc.id, "received": doc.is_received},
    )
    messages.success(request, "Document status updated.")
    return redirect("admission-detail", application_id=application_id)


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST", "ADMISSION_COUNSELOR"
)
def admission_create_student(request, application_id):
    if not has_permission(request.user, "students.manage") and not has_permission(
        request.user, "students.*"
    ):
        messages.error(request, "You do not have permission to create students.")
        return redirect("admission-detail", application_id=application_id)

    school_ids = _school_ids_for_user(request.user)
    app = get_object_or_404(
        AdmissionApplication.objects.select_related("enquiry", "school"),
        id=application_id,
        school_id__in=school_ids,
    )

    # Redirect to existing student create page with prefill query params.
    # (We keep student creation logic centralized in students app.)
    params = {
        "school": app.school_id,
        "first_name": (app.student_name.split(" ", 1)[0] if app.student_name else ""),
        "last_name": (
            app.student_name.split(" ", 1)[1]
            if app.student_name and " " in app.student_name
            else ""
        ),
        "guardian_name": app.guardian_name,
        "guardian_phone": app.phone,
        "email": app.email,
        "previous_school": app.previous_school,
        "class_name": app.desired_class_label,
        "section": app.desired_section_label,
        "admission_status": "Confirmed" if app.status in {"APPROVED", "ADMITTED"} else "Pending",
    }
    query = urlencode({k: v for k, v in params.items() if str(v).strip()})
    messages.info(request, "Student form pre-filled from admission application.")
    return redirect(f"/students/create/?{query}")
