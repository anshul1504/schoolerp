from __future__ import annotations

import csv
from datetime import timedelta
from io import StringIO

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import ActivityLog, ScheduledReport, ScheduledReportRun
from apps.schools.models import SubscriptionInvoice
from apps.students.models import Student


def _recipients(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _next_run_at(*, frequency: str, now):
    if frequency == "DAILY":
        return now + timedelta(days=1)
    if frequency == "MONTHLY":
        return now + timedelta(days=30)
    return now + timedelta(days=7)


def _csv_string(headers: list[str], rows: list[list]) -> str:
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _report_csv(report: ScheduledReport) -> tuple[str, str, int]:
    filters = report.filters or {}
    if report.report_type == "INVOICES":
        qs = SubscriptionInvoice.objects.select_related("school", "plan").order_by("-id")
        school_id = str(filters.get("school_id") or "").strip()
        status = str(filters.get("status") or "").strip().upper()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        if status in {"DRAFT", "ISSUED", "PAID", "VOID"}:
            qs = qs.filter(status=status)
        qs = qs[:5000]
        rows = [
            [
                inv.id,
                inv.school.name if inv.school else "",
                inv.plan.code if inv.plan else "",
                inv.period_start,
                inv.period_end,
                inv.amount,
                inv.status,
                inv.due_date,
                inv.issued_at,
            ]
            for inv in qs
        ]
        content = _csv_string(
            [
                "id",
                "school",
                "plan",
                "period_start",
                "period_end",
                "amount",
                "status",
                "due_date",
                "issued_at",
            ],
            rows,
        )
        return "invoices.csv", content, len(rows)

    if report.report_type == "ACTIVITY":
        qs = ActivityLog.objects.select_related("actor", "school").order_by("-created_at")
        school_id = str(filters.get("school_id") or "").strip()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        qs = qs[:5000]
        rows = [
            [
                log.created_at,
                getattr(log.actor, "username", "") if log.actor else "",
                getattr(log.actor, "email", "") if log.actor else "",
                log.school.name if log.school else "",
                log.action,
                log.method,
                log.path,
                log.status_code,
                log.ip_address,
            ]
            for log in qs
        ]
        content = _csv_string(
            [
                "created_at",
                "actor",
                "actor_email",
                "school",
                "action",
                "method",
                "path",
                "status_code",
                "ip_address",
            ],
            rows,
        )
        return "activity.csv", content, len(rows)

    if report.report_type == "STUDENTS":
        qs = Student.objects.select_related("school").order_by("-id")
        school_id = str(filters.get("school_id") or "").strip()
        status = str(filters.get("status") or "").strip().lower()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        qs = qs[:5000]
        rows = [
            [
                s.school.name if s.school else "",
                s.admission_no,
                s.first_name,
                s.last_name,
                s.class_name,
                s.section,
                s.guardian_name,
                s.guardian_phone,
                "yes" if s.is_active else "no",
            ]
            for s in qs
        ]
        content = _csv_string(
            [
                "school",
                "admission_no",
                "first_name",
                "last_name",
                "class",
                "section",
                "guardian_name",
                "guardian_phone",
                "is_active",
            ],
            rows,
        )
        return "students.csv", content, len(rows)

    content = _csv_string(["note"], [["Unsupported report type"]])
    return "report.csv", content, 1


class Command(BaseCommand):
    help = "Send due scheduled reports via email (CSV attachments)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Do not send emails; only update next_run_at."
        )

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = bool(options.get("dry_run"))

        qs = ScheduledReport.objects.filter(is_active=True)
        due = qs.filter(next_run_at__lte=now) | qs.filter(next_run_at__isnull=True)

        sent = 0
        for report in due.order_by("id")[:200]:
            started_at = timezone.now()
            recipients = _recipients(report.recipients)
            if not recipients:
                report.is_active = False
                report.save(update_fields=["is_active"])
                ScheduledReportRun.objects.create(
                    report=report,
                    status="SKIPPED",
                    recipients="",
                    filename="",
                    row_count=0,
                    error="No recipients configured; report was deactivated.",
                    started_at=started_at,
                    finished_at=timezone.now(),
                )
                continue

            filename, content, row_count = _report_csv(report)
            subject = f"[School ERP] Scheduled Report: {report.name}"
            body = f"Report: {report.get_report_type_display()}\nGenerated at: {now.isoformat()}\n"

            run_status = "SUCCESS"
            run_error = ""
            if not dry_run:
                try:
                    msg = EmailMultiAlternatives(subject=subject, body=body, to=recipients)
                    msg.attach(filename, content, "text/csv")
                    msg.send(fail_silently=False)
                    sent += 1
                except Exception as exc:
                    run_status = "FAILED"
                    run_error = str(exc)

            report.last_run_at = now
            report.next_run_at = _next_run_at(frequency=report.frequency, now=now)
            report.save(update_fields=["last_run_at", "next_run_at"])

            ScheduledReportRun.objects.create(
                report=report,
                status=run_status,
                recipients=",".join(recipients),
                filename=filename,
                row_count=row_count,
                error=run_error,
                started_at=started_at,
                finished_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS(f"Processed {sent} scheduled report(s)."))
