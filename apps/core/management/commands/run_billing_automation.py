from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.schools.models import SchoolSubscription, SubscriptionInvoice


class Command(BaseCommand):
    help = "Run billing automation jobs: mark subscriptions past-due/active using invoice signals."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Compute actions but do not write changes.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        today = timezone.now().date()

        marked_past_due = 0
        reactivated = 0
        checked = 0

        subscriptions = SchoolSubscription.objects.select_related("school").all()
        for sub in subscriptions:
            checked += 1
            invoices = SubscriptionInvoice.objects.filter(school=sub.school).exclude(status="VOID")
            has_overdue_issued = invoices.filter(status="ISSUED", due_date__isnull=False, due_date__lt=today).exists()
            recent_paid = invoices.filter(status="PAID", created_at__gte=timezone.now() - timedelta(days=45)).exists()

            if has_overdue_issued and sub.status in {"ACTIVE", "TRIAL"}:
                if not dry_run:
                    sub.status = "PAST_DUE"
                    sub.save(update_fields=["status"])
                marked_past_due += 1
                continue

            if (not has_overdue_issued) and recent_paid and sub.status == "PAST_DUE":
                if not dry_run:
                    sub.status = "ACTIVE"
                    sub.save(update_fields=["status"])
                reactivated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Billing automation complete | checked={checked} | marked_past_due={marked_past_due} | reactivated={reactivated} | dry_run={dry_run}"
            )
        )
