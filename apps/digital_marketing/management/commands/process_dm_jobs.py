from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.digital_marketing.models import DigitalMarketingJob


class Command(BaseCommand):
    help = "Process queued digital marketing jobs with retry/dead-letter handling."

    def handle(self, *args, **options):
        now = timezone.now()
        jobs = DigitalMarketingJob.objects.filter(
            status__in=["QUEUED", "FAILED"], run_at__lte=now
        ).order_by("run_at", "id")[:50]
        processed = 0
        for job in jobs:
            if job.status == "DEAD_LETTER":
                continue
            job.status = "RUNNING"
            job.attempts += 1
            job.save(update_fields=["status", "attempts", "updated_at"])
            try:
                # Placeholder execution hooks; replace with celery/external adapters as needed.
                if job.job_type not in {"PUBLISH_POST", "INGEST_LEAD", "SEND_REPORT"}:
                    raise ValueError("Unsupported job type")
                job.status = "SUCCESS"
                job.last_error = ""
            except Exception as exc:
                job.last_error = str(exc)[:255]
                if job.attempts >= job.max_attempts:
                    job.status = "DEAD_LETTER"
                else:
                    job.status = "FAILED"
                    job.run_at = now + timezone.timedelta(minutes=5)
            job.save(update_fields=["status", "last_error", "run_at", "updated_at"])
            processed += 1

        self.stdout.write(self.style.SUCCESS(f"Processed jobs: {processed}"))
