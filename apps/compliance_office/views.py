import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context
from apps.students.models import Student

from .forms import ComplianceInspectionForm, CompliancePolicyForm, SchoolCertificationForm
from .models import ComplianceInspection, CompliancePolicy, SchoolCertification

ALLOWED_ROLES = ("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "COMPLIANCE_OFFICER")


@login_required
@role_required(*ALLOWED_ROLES)
def overview(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    context = {
        "active_policies": CompliancePolicy.objects.filter(school=school, status="ACTIVE").count(),
        "pending_inspections": ComplianceInspection.objects.filter(
            school=school, status__in=["SCHEDULED", "IN_PROGRESS"]
        ).count(),
        "valid_certifications": SchoolCertification.objects.filter(
            school=school, status="VALID"
        ).count(),
        "recent_inspections": ComplianceInspection.objects.filter(school=school).order_by(
            "-inspection_date"
        )[:5],
        "recent_certifications": SchoolCertification.objects.filter(school=school).order_by(
            "-issue_date"
        )[:5],
    }
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/overview.html", context)


# --- Policies ---


@login_required
@role_required(*ALLOWED_ROLES)
def policy_list(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    policies = CompliancePolicy.objects.filter(school=school).order_by("-created_at")
    q = request.GET.get("q", "")
    if q:
        policies = policies.filter(title__icontains=q)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="compliance_policies.csv"'
        writer = csv.writer(response)
        writer.writerow(["Title", "Category", "Effective Date", "Status"])
        for p in policies:
            writer.writerow([p.title, p.category, p.effective_date, p.get_status_display()])
        return response

    context = {"policies": policies, "filters": {"q": q}}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/policy_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def policy_create(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    if request.method == "POST":
        form = CompliancePolicyForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "Policy added successfully.")
            return redirect("compliance_office:policy_list")
    else:
        form = CompliancePolicyForm()

    context = {"form": form, "title": "Compliance Policy", "is_edit": False}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def policy_detail(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    policy = get_object_or_404(CompliancePolicy, pk=pk, school=school)
    inspections = ComplianceInspection.objects.filter(
        school=school, related_policy=policy
    ).order_by("-inspection_date")

    context = {"policy": policy, "inspections": inspections}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/policy_detail.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def policy_edit(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    obj = get_object_or_404(CompliancePolicy, pk=pk, school=school)
    if request.method == "POST":
        form = CompliancePolicyForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Policy updated successfully.")
            return redirect("compliance_office:policy_list")
    else:
        form = CompliancePolicyForm(instance=obj)

    context = {"form": form, "title": "Compliance Policy", "is_edit": True}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def policy_delete(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response
    obj = get_object_or_404(CompliancePolicy, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Policy deleted.")
    return redirect("compliance_office:policy_list")


# --- Inspections ---


@login_required
@role_required(*ALLOWED_ROLES)
def inspection_list(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    inspections = (
        ComplianceInspection.objects.filter(school=school)
        .select_related("related_policy")
        .order_by("-inspection_date")
    )
    q = request.GET.get("q", "")
    if q:
        inspections = inspections.filter(title__icontains=q)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="compliance_inspections.csv"'
        writer = csv.writer(response)
        writer.writerow(["Title", "Date", "Inspector", "Status"])
        for i in inspections:
            writer.writerow([i.title, i.inspection_date, i.inspector_name, i.get_status_display()])
        return response

    context = {"inspections": inspections, "filters": {"q": q}}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/inspection_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def inspection_create(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    if request.method == "POST":
        form = ComplianceInspectionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "Inspection added successfully.")
            return redirect("compliance_office:inspection_list")
    else:
        form = ComplianceInspectionForm()
        # limit policy choices
        form.fields["related_policy"].queryset = CompliancePolicy.objects.filter(school=school)

    context = {"form": form, "title": "Inspection/Audit", "is_edit": False}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def inspection_edit(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    obj = get_object_or_404(ComplianceInspection, pk=pk, school=school)
    if request.method == "POST":
        form = ComplianceInspectionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Inspection updated successfully.")
            return redirect("compliance_office:inspection_list")
    else:
        form = ComplianceInspectionForm(instance=obj)
        form.fields["related_policy"].queryset = CompliancePolicy.objects.filter(school=school)

    context = {"form": form, "title": "Inspection/Audit", "is_edit": True}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def inspection_delete(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response
    obj = get_object_or_404(ComplianceInspection, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Inspection deleted.")
    return redirect("compliance_office:inspection_list")


# --- Certifications ---


@login_required
@role_required(*ALLOWED_ROLES)
def certification_list(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    certs = SchoolCertification.objects.filter(school=school).order_by("expiry_date")
    q = request.GET.get("q", "")
    if q:
        certs = certs.filter(name__icontains=q)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="school_certifications.csv"'
        writer = csv.writer(response)
        writer.writerow(["Name", "Authority", "Issue Date", "Expiry Date", "Status"])
        for c in certs:
            writer.writerow(
                [c.name, c.issuing_authority, c.issue_date, c.expiry_date, c.get_status_display()]
            )
        return response

    context = {"certifications": certs, "filters": {"q": q}}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/certification_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def certification_create(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    if request.method == "POST":
        form = SchoolCertificationForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "Certification added successfully.")
            return redirect("compliance_office:certification_list")
    else:
        form = SchoolCertificationForm()

    context = {"form": form, "title": "School Certification", "is_edit": False}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def certification_detail(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    cert = get_object_or_404(SchoolCertification, pk=pk, school=school)

    context = {"cert": cert}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/certification_detail.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def certification_edit(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    obj = get_object_or_404(SchoolCertification, pk=pk, school=school)
    if request.method == "POST":
        form = SchoolCertificationForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Certification updated successfully.")
            return redirect("compliance_office:certification_list")
    else:
        form = SchoolCertificationForm(instance=obj)

    context = {"form": form, "title": "School Certification", "is_edit": True}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def certification_delete(request, pk):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response
    obj = get_object_or_404(SchoolCertification, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Certification deleted.")
    return redirect("compliance_office:certification_list")


# --- Student Compliance ---


@login_required
@role_required(*ALLOWED_ROLES)
def student_compliance_list(request):
    school, error_response = get_selected_school_or_redirect(request)
    if error_response:
        return error_response

    students = Student.objects.filter(school=school, is_active=True).prefetch_related(
        "compliance_reminders"
    )
    q = request.GET.get("q", "")
    if q:
        students = (
            students.filter(first_name__icontains=q)
            | students.filter(last_name__icontains=q)
            | students.filter(admission_no__icontains=q)
        )

    context = {"students": students[:100], "filters": {"q": q}}
    context.update(build_layout_context(request.user, current_section="compliance_office"))
    return render(request, "compliance_office/student_compliance_list.html", context)
