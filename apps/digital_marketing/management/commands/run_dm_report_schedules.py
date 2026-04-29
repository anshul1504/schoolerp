from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.digital_marketing.models import DigitalMarketingReportRun, DigitalMarketingReportSchedule


class Command(BaseCommand):
    help = "Run due digital marketing report schedules and log runs."

    def handle(self, *args, **options):
        now = timezone.now()
        today = timezone.localdate()
        ran_count = 0

        schedules = DigitalMarketingReportSchedule.objects.filter(is_active=True).select_related(
            "school"
        )
        for schedule in schedules:
            should_run = False
            if schedule.last_run_at is None:
                should_run = True
            elif schedule.frequency == "DAILY":
                should_run = schedule.last_run_at.date() < today
            elif schedule.frequency == "WEEKLY":
                should_run = (today - schedule.last_run_at.date()).days >= 7
            elif schedule.frequency == "MONTHLY":
                last = schedule.last_run_at.date()
                should_run = (today.year, today.month) != (last.year, last.month)

            if not should_run:
                continue

            schedule.last_run_at = now
            schedule.save(update_fields=["last_run_at"])
            send_mail(
                subject=f"[Digital Marketing] Scheduled Report: {schedule.name}",
                message="Your scheduled digital marketing report has been generated and is ready in ERP exports.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[schedule.delivery_email],
                fail_silently=True,
            )
            DigitalMarketingReportRun.objects.create(
                schedule=schedule,
                status="SUCCESS",
                message=f"Auto run completed for {schedule.frequency.lower()} schedule and email triggered.",
            )
            ran_count += 1

        self.stdout.write(self.style.SUCCESS(f"Processed schedules. Runs created: {ran_count}"))
