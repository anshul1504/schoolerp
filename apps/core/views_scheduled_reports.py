import json
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import ScheduledReport, ScheduledReportRun
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context


def _parse_filters(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _recipients_list(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _next_run_at(*, frequency: str, now):
    if frequency == "DAILY":
        return now + timedelta(days=1)
    if frequency == "MONTHLY":
        return now + timedelta(days=30)
    return now + timedelta(days=7)


def _run_now(report: ScheduledReport) -> ScheduledReportRun:
    from apps.core.management.commands.run_scheduled_reports import _report_csv, _recipients  # local import to avoid cycles
    from django.core.mail import EmailMultiAlternatives

    now = timezone.now()
    started_at = now
    recipients = _recipients(report.recipients)
    if not recipients:
        report.is_active = False
        report.save(update_fields=["is_active"])
        return ScheduledReportRun.objects.create(
            report=report,
            status="SKIPPED",
            recipients="",
            filename="",
            row_count=0,
            error="No recipients configured; report was deactivated.",
            started_at=started_at,
            finished_at=timezone.now(),
        )

    filename, content, row_count = _report_csv(report)
    subject = f"[School ERP] Scheduled Report: {report.name}"
    body = f"Report: {report.get_report_type_display()}\nGenerated at: {now.isoformat()}\n"
    status = "SUCCESS"
    error = ""
    try:
        msg = EmailMultiAlternatives(subject=subject, body=body, to=recipients)
        msg.attach(filename, content, "text/csv")
        msg.send(fail_silently=False)
    except Exception as exc:
        status = "FAILED"
        error = str(exc)

    report.last_run_at = now
    report.next_run_at = _next_run_at(frequency=report.frequency, now=now)
    report.save(update_fields=["last_run_at", "next_run_at"])

    return ScheduledReportRun.objects.create(
        report=report,
        status=status,
        recipients=",".join(recipients),
        filename=filename,
        row_count=row_count,
        error=error,
        started_at=started_at,
        finished_at=timezone.now(),
    )


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def scheduled_report_list(request):
    qs = ScheduledReport.objects.all()
    context = build_layout_context(request.user, current_section="reports")
    context["scheduled_reports"] = qs[:200]
    return render(request, "reports/scheduled_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def scheduled_report_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        report_type = (request.POST.get("report_type") or "").strip()
        frequency = (request.POST.get("frequency") or "").strip()
        recipients = (request.POST.get("recipients") or "").strip()
        filters = _parse_filters(request.POST.get("filters") or "")
        is_active = request.POST.get("is_active") == "on"

        if not name or report_type not in dict(ScheduledReport.REPORT_CHOICES) or frequency not in dict(ScheduledReport.FREQUENCY_CHOICES):
            messages.error(request, "Please fill all required fields.")
        elif not _recipients_list(recipients):
            messages.error(request, "At least one recipient email is required.")
        else:
            ScheduledReport.objects.create(
                name=name,
                report_type=report_type,
                frequency=frequency,
                recipients=recipients,
                filters=filters,
                is_active=is_active,
                next_run_at=_next_run_at(frequency=frequency, now=timezone.now()) if is_active else None,
            )
            messages.success(request, "Scheduled report created.")
            return redirect("/reports/scheduled/")

    context = build_layout_context(request.user, current_section="reports")
    context.update(
        {
            "mode": "create",
            "report_choices": ScheduledReport.REPORT_CHOICES,
            "frequency_choices": ScheduledReport.FREQUENCY_CHOICES,
        }
    )
    return render(request, "reports/scheduled_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def scheduled_report_update(request, report_id):
    report = get_object_or_404(ScheduledReport, id=report_id)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        report_type = (request.POST.get("report_type") or "").strip()
        frequency = (request.POST.get("frequency") or "").strip()
        recipients = (request.POST.get("recipients") or "").strip()
        filters = _parse_filters(request.POST.get("filters") or "")
        is_active = request.POST.get("is_active") == "on"

        if not name or report_type not in dict(ScheduledReport.REPORT_CHOICES) or frequency not in dict(ScheduledReport.FREQUENCY_CHOICES):
            messages.error(request, "Please fill all required fields.")
        elif not _recipients_list(recipients):
            messages.error(request, "At least one recipient email is required.")
        else:
            report.name = name
            report.report_type = report_type
            report.frequency = frequency
            report.recipients = recipients
            report.filters = filters
            report.is_active = is_active
            report.next_run_at = _next_run_at(frequency=frequency, now=timezone.now()) if is_active else None
            report.save()
            messages.success(request, "Scheduled report updated.")
            return redirect("/reports/scheduled/")

    context = build_layout_context(request.user, current_section="reports")
    context.update(
        {
            "mode": "edit",
            "report": report,
            "filters_json": json.dumps(report.filters or {}, indent=2),
            "report_choices": ScheduledReport.REPORT_CHOICES,
            "frequency_choices": ScheduledReport.FREQUENCY_CHOICES,
        }
    )
    return render(request, "reports/scheduled_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def scheduled_report_delete(request, report_id):
    report = get_object_or_404(ScheduledReport, id=report_id)
    if request.method == "POST":
        report.delete()
        messages.success(request, "Scheduled report deleted.")
        return redirect("/reports/scheduled/")
    messages.error(request, "Invalid delete request.")
    return redirect("/reports/scheduled/")


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def scheduled_report_run_now(request, report_id):
    report = get_object_or_404(ScheduledReport, id=report_id)
    if request.method != "POST":
        messages.error(request, "Invalid run request.")
        return redirect("/reports/scheduled/")
    run = _run_now(report)
    if run.status == "SUCCESS":
        messages.success(request, "Report sent successfully.")
    elif run.status == "SKIPPED":
        messages.warning(request, "Report was skipped (missing recipients).")
    else:
        messages.error(request, f"Report failed: {run.error or 'Unknown error'}")
    return redirect("/reports/scheduled/")
