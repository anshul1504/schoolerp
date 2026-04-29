import csv

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.permissions import role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context

from .forms import (
    GatePassForm,
    GuardRosterForm,
    PatrolCheckpointLogForm,
    SecurityIncidentForm,
    VisitorEntryForm,
)
from .models import GatePass, GuardRoster, PatrolCheckpointLog, SecurityIncident, VisitorEntry

ALLOWED_ROLES = ("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "SECURITY_OFFICER")


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


@login_required
@role_required(*ALLOWED_ROLES)
def overview(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect

    incidents = SecurityIncident.objects.filter(school=school)
    visitors = VisitorEntry.objects.filter(school=school)
    gate_passes = GatePass.objects.filter(school=school)
    patrol_logs = PatrolCheckpointLog.objects.filter(school=school)
    today = timezone.localdate()

    context = {
        "stats": {
            "open_incidents": incidents.filter(status__in=["OPEN", "INVESTIGATING"]).count(),
            "critical_incidents": incidents.filter(severity="CRITICAL").count(),
            "visitors_inside": visitors.filter(check_out_at__isnull=True).count(),
            "verified_visitors": visitors.filter(is_verified=True).count(),
            "active_gate_passes": gate_passes.filter(status="ISSUED").count(),
            "active_guards_today": GuardRoster.objects.filter(school=school, duty_date=today, is_active=True).count(),
            "patrol_alerts_today": patrol_logs.filter(logged_at__date=today, is_alert=True).count(),
        },
        "recent_incidents": incidents[:6],
        "recent_visitors": visitors[:6],
        "recent_gate_passes": gate_passes[:6],
        "recent_patrol_logs": patrol_logs[:6],
    }

    # Chart 1: Incidents by Severity
    severity_labels = ["Low", "Medium", "High", "Critical"]
    severity_counts = [
        incidents.filter(severity="LOW").count(),
        incidents.filter(severity="MEDIUM").count(),
        incidents.filter(severity="HIGH").count(),
        incidents.filter(severity="CRITICAL").count(),
    ]

    # Chart 2: Visitor Trends (Last 7 Days)
    from datetime import timedelta
    visitor_dates = [(today - timedelta(days=i)).strftime('%b %d') for i in range(6, -1, -1)]
    visitor_counts = [
        visitors.filter(check_in_at__date=(today - timedelta(days=i))).count()
        for i in range(6, -1, -1)
    ]

    context["chart_data"] = {
        "severity_labels": severity_labels,
        "severity_counts": severity_counts,
        "visitor_dates": visitor_dates,
        "visitor_counts": visitor_counts
    }

    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/overview.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def incident_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    qs = SecurityIncident.objects.filter(school=school)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(incident_type__icontains=q) | Q(location__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if request.GET.get("export") == "csv":
        return _csv_response(
            "security_incidents.csv",
            ["Title", "Type", "Severity", "Status", "Location", "Reported At"],
            [(i.title, i.incident_type, i.get_severity_display(), i.get_status_display(), i.location, i.reported_at) for i in qs],
        )
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    context = {"incidents": page, "filters": {"q": q, "status": status}, "status_choices": SecurityIncident.STATUS_CHOICES}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/incident_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def incident_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(SecurityIncident, pk=pk, school=school) if pk else None
    form = SecurityIncidentForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("security_office:incident_list")
    context = {"form": form, "is_edit": bool(instance), "title": "Security Incident"}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def incident_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(SecurityIncident, pk=pk, school=school)
    if request.method == "POST":
        instance.delete()
    return redirect("security_office:incident_list")


@login_required
@role_required(*ALLOWED_ROLES)
def visitor_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    qs = VisitorEntry.objects.filter(school=school)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(person_to_meet__icontains=q) | Q(purpose__icontains=q))
    if request.GET.get("export") == "csv":
        return _csv_response(
            "visitor_register.csv",
            ["Name", "Phone", "Purpose", "Person to Meet", "Check In", "Check Out", "Verified"],
            [(v.name, v.phone, v.purpose, v.person_to_meet, v.check_in_at, v.check_out_at or "", "Yes" if v.is_verified else "No") for v in qs],
        )
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    context = {"visitors": page, "filters": {"q": q}}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/visitor_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def visitor_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(VisitorEntry, pk=pk, school=school) if pk else None
    form = VisitorEntryForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("security_office:visitor_list")
    context = {"form": form, "is_edit": bool(instance), "title": "Visitor Entry"}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def visitor_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(VisitorEntry, pk=pk, school=school)
    if request.method == "POST":
        instance.delete()
    return redirect("security_office:visitor_list")


@login_required
@role_required(*ALLOWED_ROLES)
def roster_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    qs = GuardRoster.objects.filter(school=school)
    shift = (request.GET.get("shift") or "").strip()
    if shift:
        qs = qs.filter(shift=shift)
    if request.GET.get("export") == "csv":
        return _csv_response(
            "guard_roster.csv",
            ["Guard", "Shift", "Area", "Duty Date", "Active"],
            [(r.guard_name, r.get_shift_display(), r.area, r.duty_date, "Yes" if r.is_active else "No") for r in qs],
        )
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    context = {"rows": page, "filters": {"shift": shift}, "shift_choices": GuardRoster.SHIFT_CHOICES}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/roster_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def roster_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(GuardRoster, pk=pk, school=school) if pk else None
    form = GuardRosterForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("security_office:roster_list")
    context = {"form": form, "is_edit": bool(instance), "title": "Guard Roster"}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def roster_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(GuardRoster, pk=pk, school=school)
    if request.method == "POST":
        instance.delete()
    return redirect("security_office:roster_list")


@login_required
@role_required(*ALLOWED_ROLES)
def gate_pass_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    qs = GatePass.objects.filter(school=school)
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    if request.GET.get("export") == "csv":
        return _csv_response(
            "gate_passes.csv",
            ["Type", "Person", "Reason", "Issued At", "Valid Till", "Status", "Issued By"],
            [(p.get_pass_type_display(), p.person_name, p.reason, p.issued_at, p.valid_till or "", p.get_status_display(), p.issued_by) for p in qs],
        )
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    context = {"rows": page, "filters": {"status": status}, "status_choices": GatePass.STATUS_CHOICES}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/gate_pass_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def gate_pass_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(GatePass, pk=pk, school=school) if pk else None
    form = GatePassForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("security_office:gate_pass_list")
    context = {"form": form, "is_edit": bool(instance), "title": "Gate Pass"}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def gate_pass_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(GatePass, pk=pk, school=school)
    if request.method == "POST":
        instance.delete()
    return redirect("security_office:gate_pass_list")


@login_required
@role_required(*ALLOWED_ROLES)
def patrol_log_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    qs = PatrolCheckpointLog.objects.filter(school=school)
    alert = (request.GET.get("alert") or "").strip()
    if alert in ["1", "0"]:
        qs = qs.filter(is_alert=(alert == "1"))
    if request.GET.get("export") == "csv":
        return _csv_response(
            "patrol_logs.csv",
            ["Checkpoint", "Guard", "Logged At", "Note", "Alert"],
            [
                (
                    log.checkpoint_name,
                    log.guard_name,
                    log.logged_at,
                    log.status_note,
                    "Yes" if log.is_alert else "No",
                )
                for log in qs
            ],
        )
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    context = {"rows": page, "filters": {"alert": alert}}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/patrol_log_list.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def patrol_log_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(PatrolCheckpointLog, pk=pk, school=school) if pk else None
    form = PatrolCheckpointLogForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("security_office:patrol_log_list")
    context = {"form": form, "is_edit": bool(instance), "title": "Patrol Log"}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "security_office/generic_form.html", context)


@login_required
@role_required(*ALLOWED_ROLES)
def patrol_log_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Security Office")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(PatrolCheckpointLog, pk=pk, school=school)
    if request.method == "POST":
        instance.delete()
    return redirect("security_office:patrol_log_list")
