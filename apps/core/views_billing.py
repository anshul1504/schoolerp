import calendar
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import math
import csv
import hashlib
import hmac
import time

from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.cache import cache
from django.utils.crypto import constant_time_compare

from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context
from apps.schools.models import PlanFeature, School, SchoolSubscription, SubscriptionCoupon, SubscriptionInvoice, SubscriptionPayment, SubscriptionPlan
from apps.students.models import Student
from apps.core.models import BillingWebhookEvent, ActivityLog


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def plan_list(request):
    plans = SubscriptionPlan.objects.all().order_by("name")
    context = build_layout_context(request.user, current_section="billing")
    context["plans"] = plans
    return render(request, "billing/plans_list.html", context)


def ensure_default_plans():
    feature_defs = [
        {"code": "STUDENTS", "name": "Students", "description": "Student records & admissions"},
        {"code": "ACADEMICS", "name": "Academics", "description": "Classes, subjects, allocations"},
        {"code": "ATTENDANCE", "name": "Attendance", "description": "Sessions, marking, summaries"},
        {"code": "FEES", "name": "Fees", "description": "Structures, dues, collections"},
        {"code": "EXAMS", "name": "Exams", "description": "Exam setup, marks, results"},
        {"code": "COMMUNICATION", "name": "Communication", "description": "Notices & notifications"},
        {"code": "REPORTS", "name": "Reports", "description": "Exports and reporting views"},
    ]

    created_features = 0
    for feature in feature_defs:
        _, created = PlanFeature.objects.get_or_create(
            code=feature["code"],
            defaults={"name": feature["name"], "description": feature["description"], "is_active": True},
        )
        if created:
            created_features += 1

    plan_defs = [
        {
            "code": "SILVER",
            "name": "Silver",
            "tier": "SILVER",
            "billing_mode": "PER_500",
            "unit_price": Decimal("500"),
            "feature_codes": {"STUDENTS", "ACADEMICS", "ATTENDANCE", "COMMUNICATION"},
        },
        {
            "code": "GOLD",
            "name": "Gold",
            "tier": "GOLD",
            "billing_mode": "PER_500",
            "unit_price": Decimal("750"),
            "feature_codes": {"STUDENTS", "ACADEMICS", "ATTENDANCE", "FEES", "EXAMS", "COMMUNICATION"},
        },
        {
            "code": "PLATINUM",
            "name": "Platinum",
            "tier": "PLATINUM",
            "billing_mode": "PER_500",
            "unit_price": Decimal("1000"),
            "feature_codes": {"STUDENTS", "ACADEMICS", "ATTENDANCE", "FEES", "EXAMS", "COMMUNICATION", "REPORTS"},
        },
    ]

    created_plans = 0
    updated_plans = 0
    for plan_def in plan_defs:
        plan, created = SubscriptionPlan.objects.get_or_create(
            code=plan_def["code"],
            defaults={
                "name": plan_def["name"],
                "tier": plan_def["tier"],
                "billing_mode": plan_def["billing_mode"],
                "unit_price": plan_def["unit_price"],
                "price_monthly": Decimal("0"),
                "max_students": 1000,
                "max_campuses": 1,
                "is_active": True,
            },
        )
        if created:
            created_plans += 1
        else:
            updated = False
            if plan.tier != plan_def["tier"]:
                plan.tier = plan_def["tier"]
                updated = True
            if not plan.billing_mode:
                plan.billing_mode = plan_def["billing_mode"]
                updated = True
            if (plan.unit_price or Decimal("0")) <= 0:
                plan.unit_price = plan_def["unit_price"]
                updated = True
            if updated:
                plan.save(update_fields=["tier", "billing_mode", "unit_price"])
                updated_plans += 1

        features = list(PlanFeature.objects.filter(code__in=plan_def["feature_codes"]))
        if features:
            plan.features.add(*features)

    return {
        "created_features": created_features,
        "created_plans": created_plans,
        "updated_plans": updated_plans,
    }


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def seed_default_plans(request):
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("/billing/plans/")

    result = ensure_default_plans()
    messages.success(
        request,
        "Defaults ensured. "
        f"Plans created: {result['created_plans']}. "
        f"Plans updated: {result['updated_plans']}. "
        f"Features created: {result['created_features']}.",
    )
    return redirect("/billing/plans/")


def _plan_payload(request):
    feature_ids = [value for value in request.POST.getlist("feature_ids") if str(value).isdigit()]
    return {
        "name": request.POST.get("name", "").strip(),
        "code": request.POST.get("code", "").strip().upper(),
        "tier": request.POST.get("tier") or "SILVER",
        "price_monthly": request.POST.get("price_monthly") or 0,
        "billing_mode": request.POST.get("billing_mode") or "FLAT",
        "unit_price": request.POST.get("unit_price") or 0,
        "max_students": request.POST.get("max_students") or 1000,
        "max_campuses": request.POST.get("max_campuses") or 1,
        "is_active": request.POST.get("is_active") == "on",
        "feature_ids": feature_ids,
    }


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def plan_create(request):
    if request.method == "POST":
        payload = _plan_payload(request)
        if not payload["name"] or not payload["code"]:
            messages.error(request, "Name and code are required.")
        elif SubscriptionPlan.objects.filter(code=payload["code"]).exists():
            messages.error(request, "That plan code already exists.")
        else:
            feature_ids = payload.pop("feature_ids", [])
            plan = SubscriptionPlan.objects.create(**payload)
            if feature_ids:
                plan.features.set(PlanFeature.objects.filter(id__in=feature_ids))
            messages.success(request, "Plan created.")
            return redirect("/billing/plans/")

    context = build_layout_context(request.user, current_section="billing")
    context["features"] = PlanFeature.objects.filter(is_active=True).order_by("name")
    context["tier_choices"] = SubscriptionPlan.TIER_CHOICES
    context["billing_mode_choices"] = SubscriptionPlan.BILLING_MODE_CHOICES
    return render(request, "billing/plan_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def plan_update(request, id):
    plan = get_object_or_404(SubscriptionPlan, id=id)
    if request.method == "POST":
        payload = _plan_payload(request)
        if not payload["name"] or not payload["code"]:
            messages.error(request, "Name and code are required.")
        elif SubscriptionPlan.objects.filter(code=payload["code"]).exclude(id=plan.id).exists():
            messages.error(request, "That plan code already exists.")
        else:
            feature_ids = payload.pop("feature_ids", [])
            for field, value in payload.items():
                setattr(plan, field, value)
            plan.save()
            plan.features.set(PlanFeature.objects.filter(id__in=feature_ids))
            messages.success(request, "Plan updated.")
            return redirect("/billing/plans/")

    context = build_layout_context(request.user, current_section="billing")
    context["plan"] = plan
    context["features"] = PlanFeature.objects.filter(is_active=True).order_by("name")
    context["selected_feature_ids"] = set(plan.features.values_list("id", flat=True))
    context["tier_choices"] = SubscriptionPlan.TIER_CHOICES
    context["billing_mode_choices"] = SubscriptionPlan.BILLING_MODE_CHOICES
    return render(request, "billing/plan_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def feature_list(request):
    features = PlanFeature.objects.all().order_by("name")
    context = build_layout_context(request.user, current_section="billing")
    context["features"] = features
    return render(request, "billing/features_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def feature_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        code = (request.POST.get("code") or "").strip().upper()
        description = (request.POST.get("description") or "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not name or not code:
            messages.error(request, "Name and code are required.")
        elif PlanFeature.objects.filter(code=code).exists():
            messages.error(request, "That feature code already exists.")
        else:
            PlanFeature.objects.create(name=name, code=code, description=description, is_active=is_active)
            messages.success(request, "Feature created.")
            return redirect("/billing/features/")

    context = build_layout_context(request.user, current_section="billing")
    return render(request, "billing/feature_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def plan_delete(request, id):
    plan = get_object_or_404(SubscriptionPlan, id=id)
    if request.method == "POST":
        in_use = SchoolSubscription.objects.filter(plan=plan).exists() or SubscriptionInvoice.objects.filter(plan=plan).exists()
        if in_use:
            messages.error(request, "Plan cannot be deleted because it is assigned to schools/invoices.")
        else:
            plan.delete()
            messages.success(request, "Plan deleted.")
    return redirect("/billing/plans/")


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def school_subscriptions(request):
    schools = School.objects.all().order_by("name").prefetch_related("subscription")
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("name")
    context = build_layout_context(request.user, current_section="billing")
    context.update({"schools": schools, "plans": plans, "status_choices": SchoolSubscription.STATUS_CHOICES})
    return render(request, "billing/schools.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def school_subscription_update(request, school_id):
    school = get_object_or_404(School, id=school_id)
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("/billing/schools/")

    plan_id = request.POST.get("plan_id")
    status = request.POST.get("status") or "TRIAL"
    starts_on_raw = (request.POST.get("starts_on") or "").strip()
    ends_on_raw = (request.POST.get("ends_on") or "").strip()

    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    starts_on = _parse_date(starts_on_raw) or subscription_default_date()
    ends_on = _parse_date(ends_on_raw)

    SchoolSubscription.objects.update_or_create(
        school=school,
        defaults={"plan": plan, "status": status, "starts_on": starts_on, "ends_on": ends_on},
    )
    messages.success(request, f"Subscription updated for {school.name}.")
    return redirect("/billing/schools/")


def subscription_default_date():
    from django.utils import timezone

    return timezone.now().date()


def _parse_date(value):
    if not value:
        return None
    try:
        from datetime import date

        parsed = date.fromisoformat(value)
        return parsed
    except Exception:
        return None


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def invoice_list(request):
    invoices = SubscriptionInvoice.objects.select_related("school", "plan").all().order_by("-id")
    query = (request.GET.get("q") or "").strip()
    school_id = (request.GET.get("school_id") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()

    if query:
        invoices = invoices.filter(Q(school__name__icontains=query) | Q(plan__code__icontains=query) | Q(id__icontains=query))
    if school_id.isdigit():
        invoices = invoices.filter(school_id=int(school_id))
    if status in {"DRAFT", "ISSUED", "PAID", "VOID"}:
        invoices = invoices.filter(status=status)
    if date_from:
        invoices = invoices.filter(period_start__gte=date_from)
    if date_to:
        invoices = invoices.filter(period_end__lte=date_to)

    raw_ids = (request.GET.get("invoice_ids") or request.GET.get("ids") or "").strip()
    if raw_ids:
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if ids:
            invoices = invoices.filter(id__in=sorted(set(ids)))

    def sanitize_cell(value) -> str:
        text = str(value or "")
        if text and text[0] in ("=", "+", "-", "@"):
            return f"'{text}"
        return text

    export_format = (request.GET.get("export") or "").strip().lower()
    if export_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="invoices_export.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "school", "plan", "period_start", "period_end", "amount", "status", "due_date", "issued_at"])
        for inv in invoices[:10000]:
            writer.writerow(
                [
                    inv.id,
                    sanitize_cell(inv.school.name if inv.school else ""),
                    sanitize_cell(inv.plan.code if inv.plan else ""),
                    sanitize_cell(inv.period_start),
                    sanitize_cell(inv.period_end),
                    sanitize_cell(inv.amount),
                    sanitize_cell(inv.status),
                    sanitize_cell(inv.due_date),
                    sanitize_cell(inv.issued_at),
                ]
            )
        return response

    if export_format == "excel":
        response = HttpResponse(content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = 'attachment; filename="invoices_export.xls"'

        def esc(value):
            return (
                sanitize_cell(value)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        rows = []
        for inv in invoices[:10000]:
            rows.append(
                "<tr>"
                f"<td>{esc(inv.id)}</td>"
                f"<td>{esc(inv.school.name if inv.school else '')}</td>"
                f"<td>{esc(inv.plan.code if inv.plan else '')}</td>"
                f"<td>{esc(inv.period_start)}</td>"
                f"<td>{esc(inv.period_end)}</td>"
                f"<td>{esc(inv.amount)}</td>"
                f"<td>{esc(inv.status)}</td>"
                f"<td>{esc(inv.due_date)}</td>"
                f"<td>{esc(inv.issued_at)}</td>"
                "</tr>"
            )

        response.write(
            "<table><thead><tr>"
            "<th>id</th><th>school</th><th>plan</th><th>period_start</th><th>period_end</th>"
            "<th>amount</th><th>status</th><th>due_date</th><th>issued_at</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        )
        return response

    context = build_layout_context(request.user, current_section="billing")
    context.update(
        {
            "invoices": invoices[:500],
            "schools": School.objects.all().order_by("name"),
            "filters": {"q": query, "school_id": school_id, "status": status, "date_from": date_from, "date_to": date_to},
        }
    )
    return render(request, "billing/invoices_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def invoice_create(request):
    schools = School.objects.all().order_by("name")
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        school_id = request.POST.get("school_id")
        plan_id = request.POST.get("plan_id")
        period_start = _parse_date(request.POST.get("period_start"))
        period_end = _parse_date(request.POST.get("period_end"))
        due_date = _parse_date(request.POST.get("due_date"))
        amount_raw = (request.POST.get("amount") or "").strip()
        amount = Decimal(amount_raw) if amount_raw else Decimal("0")
        tax_percent_raw = (request.POST.get("tax_percent") or "").strip()
        try:
            tax_percent = Decimal(tax_percent_raw) if tax_percent_raw else Decimal("0")
        except Exception:
            tax_percent = Decimal("0")
        status = (request.POST.get("status") or "ISSUED").strip().upper()
        coupon_code = (request.POST.get("coupon_code") or "").strip().upper()

        if not school_id or not plan_id or not period_start or not period_end:
            messages.error(request, "School, plan, and period dates are required.")
        elif period_end < period_start:
            messages.error(request, "Period end date cannot be before start date.")
        elif due_date and due_date < period_start:
            messages.error(request, "Due date cannot be before period start date.")
        elif status not in {"DRAFT", "ISSUED", "PAID", "VOID"}:
            messages.error(request, "Invalid invoice status.")
        elif status in {"PAID", "VOID"}:
            messages.error(request, "Create invoice as DRAFT or ISSUED first.")
        else:
            if amount <= 0:
                amount = _calculate_invoice_amount(school_id=school_id, plan_id=plan_id, period_start=period_start, period_end=period_end)

            applied_coupon = None
            if coupon_code:
                today = date.today()
                applied_coupon = SubscriptionCoupon.objects.filter(code=coupon_code, is_active=True).first()
                if not applied_coupon:
                    messages.error(request, "Invalid coupon code.")
                    return redirect("/billing/invoices/create/")
                if applied_coupon.starts_on and today < applied_coupon.starts_on:
                    messages.error(request, "Coupon is not active yet.")
                    return redirect("/billing/invoices/create/")
                if applied_coupon.ends_on and today > applied_coupon.ends_on:
                    messages.error(request, "Coupon has expired.")
                    return redirect("/billing/invoices/create/")
                if applied_coupon.max_uses and applied_coupon.used_count >= applied_coupon.max_uses:
                    messages.error(request, "Coupon usage limit reached.")
                    return redirect("/billing/invoices/create/")

                if applied_coupon.discount_type == "PERCENT":
                    discount = (amount * (applied_coupon.value / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    amount = max(amount - discount, Decimal("0"))
                else:
                    amount = max(amount - (applied_coupon.value or Decimal("0")), Decimal("0"))

            if tax_percent < 0:
                tax_percent = Decimal("0")
            if tax_percent > 100:
                tax_percent = Decimal("100")
            tax_amount = (amount * (tax_percent / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_amount = (amount + tax_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            invoice = SubscriptionInvoice.objects.create(
                school_id=school_id,
                plan_id=plan_id,
                period_start=period_start,
                period_end=period_end,
                amount=amount,
                tax_percent=tax_percent,
                tax_amount=tax_amount,
                total_amount=total_amount,
                due_date=due_date,
                status=status,
                issued_at=subscription_default_datetime() if status == "ISSUED" else None,
            )
            if applied_coupon:
                SubscriptionCoupon.objects.filter(id=applied_coupon.id).update(used_count=applied_coupon.used_count + 1)
            messages.success(request, f"Invoice created (#{invoice.id}).")
            return redirect("/billing/invoices/")

    context = build_layout_context(request.user, current_section="billing")
    context.update({"schools": schools, "plans": plans, "status_choices": SubscriptionInvoice.STATUS_CHOICES, "today": date.today()})
    return render(request, "billing/invoice_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def invoice_payments(request, invoice_id):
    invoice = get_object_or_404(SubscriptionInvoice.objects.select_related("school", "plan"), id=invoice_id)
    payments = invoice.payments.all()
    total_paid = sum((p.amount or Decimal("0")) for p in payments)
    due_total = invoice.total_amount or invoice.amount or Decimal("0")
    remaining = max(due_total - total_paid, Decimal("0"))
    context = build_layout_context(request.user, current_section="billing")
    context.update(
        {
            "invoice": invoice,
            "payments": payments,
            "method_choices": SubscriptionPayment.METHOD_CHOICES,
            "total_paid": total_paid,
            "remaining": remaining,
            "due_total": due_total,
        }
    )
    return render(request, "billing/invoice_payments.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def payment_create(request, invoice_id):
    invoice = get_object_or_404(SubscriptionInvoice, id=invoice_id)
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    if invoice.status in {"VOID", "DRAFT"}:
        messages.error(request, f"Payments cannot be recorded for {invoice.get_status_display} invoices.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    amount_raw = (request.POST.get("amount") or "").strip()
    method = request.POST.get("method") or "BANK"
    transaction_ref = (request.POST.get("transaction_ref") or "").strip()
    paid_at = _parse_datetime(request.POST.get("paid_at")) or subscription_default_datetime()

    try:
        amount = Decimal(amount_raw)
    except Exception:
        amount = Decimal("0")
    if amount <= 0:
        messages.error(request, "Payment amount must be greater than 0.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    SubscriptionPayment.objects.create(invoice=invoice, amount=amount, method=method, transaction_ref=transaction_ref, paid_at=paid_at)

    total_paid = sum((p.amount or Decimal("0")) for p in invoice.payments.all())
    due_total = invoice.total_amount or invoice.amount or Decimal("0")
    if invoice.status != "VOID":
        if total_paid >= due_total:
            invoice.status = "PAID"
            if not invoice.issued_at:
                invoice.issued_at = subscription_default_datetime()
            invoice.save(update_fields=["status", "issued_at"])
        else:
            if invoice.status == "DRAFT":
                invoice.status = "ISSUED"
                if not invoice.issued_at:
                    invoice.issued_at = subscription_default_datetime()
                invoice.save(update_fields=["status", "issued_at"])

    messages.success(request, "Payment recorded.")
    return redirect(f"/billing/invoices/{invoice_id}/")


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def invoice_status_update(request, invoice_id):
    invoice = get_object_or_404(SubscriptionInvoice.objects.select_related("school", "plan"), id=invoice_id)
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    next_status = (request.POST.get("status") or "").strip().upper()
    if next_status not in {"DRAFT", "ISSUED", "PAID", "VOID"}:
        messages.error(request, "Invalid invoice status.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    total_paid = sum((p.amount or Decimal("0")) for p in invoice.payments.all())
    amount = invoice.total_amount or invoice.amount or Decimal("0")

    current = (invoice.status or "DRAFT").strip().upper()
    if current == "VOID":
        messages.error(request, "Void invoices cannot be changed.")
        return redirect(f"/billing/invoices/{invoice_id}/")
    if current == "PAID" and next_status != "PAID":
        messages.error(request, "Paid invoices cannot be downgraded.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    if next_status == "PAID" and total_paid < amount:
        messages.error(request, f"Cannot mark as Paid until total payments reach Rs {amount}.")
        return redirect(f"/billing/invoices/{invoice_id}/")
    if next_status == "VOID" and total_paid > 0:
        messages.error(request, "Cannot void an invoice that has payments.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    if next_status == "DRAFT":
        invoice.status = "DRAFT"
        invoice.issued_at = None
        invoice.save(update_fields=["status", "issued_at"])
        messages.success(request, "Invoice moved to Draft.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    if next_status == "ISSUED":
        invoice.status = "ISSUED"
        if not invoice.issued_at:
            invoice.issued_at = subscription_default_datetime()
        invoice.save(update_fields=["status", "issued_at"])
        messages.success(request, "Invoice marked as Issued.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    if next_status == "PAID":
        invoice.status = "PAID"
        if not invoice.issued_at:
            invoice.issued_at = subscription_default_datetime()
        invoice.save(update_fields=["status", "issued_at"])
        messages.success(request, "Invoice marked as Paid.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    if next_status == "VOID":
        invoice.status = "VOID"
        invoice.save(update_fields=["status"])
        messages.success(request, "Invoice voided.")
        return redirect(f"/billing/invoices/{invoice_id}/")

    messages.error(request, "No changes applied.")
    return redirect(f"/billing/invoices/{invoice_id}/")


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def billing_webhook_events(request):
    events = BillingWebhookEvent.objects.all().order_by("-created_at")
    context = build_layout_context(request.user, current_section="billing")
    context["events"] = events[:200]
    return render(request, "billing/webhook_events.html", context)


@csrf_exempt
def billing_webhook_generic(request):
    # Minimal generic webhook receiver for payment providers.
    # Expected JSON:
    # {
    #   "event_id": "unique",
    #   "event_type": "payment.captured",
    #   "invoice_id": 123,
    #   "amount": "1000.00",
    #   "method": "UPI",
    #   "transaction_ref": "abc",
    #   "status": "PAID"
    # }
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    body = request.body or b""
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    provider = str(data.get("provider") or "GENERIC").strip().upper()[:40]
    require_sig = bool(getattr(settings, "BILLING_WEBHOOK_REQUIRE_SIGNATURE", True))
    secret_key = (
        getattr(settings, f"BILLING_WEBHOOK_SECRET_{provider}", "")
        or getattr(settings, "BILLING_WEBHOOK_SECRET", "")
        or ""
    )
    if require_sig and not secret_key:
        return JsonResponse({"error": "webhook secret not configured"}, status=503)
    if secret_key:
        timestamp = (request.headers.get("X-Webhook-Timestamp") or "").strip()
        signature = (request.headers.get("X-Webhook-Signature") or "").strip()
        if not timestamp or not signature:
            return JsonResponse({"error": "signature headers required"}, status=401)
        if signature.lower().startswith("sha256="):
            signature = signature.split("=", 1)[1].strip()
        if not timestamp.isdigit():
            return JsonResponse({"error": "invalid timestamp"}, status=401)

        max_skew = int(getattr(settings, "BILLING_WEBHOOK_MAX_SKEW_SECONDS", 300) or 300)
        now_ts = int(time.time())
        ts = int(timestamp)
        if abs(now_ts - ts) > max_skew:
            return JsonResponse({"error": "stale timestamp"}, status=401)

        signed_payload = f"{timestamp}.{body.decode('utf-8', errors='replace')}".encode("utf-8")
        expected = hmac.new(secret_key.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if not constant_time_compare(signature, expected):
            return JsonResponse({"error": "invalid signature"}, status=401)

        replay_ttl = int(getattr(settings, "BILLING_WEBHOOK_REPLAY_TTL_SECONDS", 600) or 600)
        replay_key = f"billing_webhook_sig:{provider}:{timestamp}:{signature}"
        if not cache.add(replay_key, "1", timeout=replay_ttl):
            return JsonResponse({"error": "replay detected"}, status=409)

    event_id = str(data.get("event_id") or "").strip()
    if not event_id:
        return JsonResponse({"error": "event_id required"}, status=400)

    obj, created = BillingWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            "provider": provider,
            "event_type": str(data.get("event_type") or "")[:80],
            "invoice_id": int(data.get("invoice_id")) if str(data.get("invoice_id") or "").isdigit() else None,
            "status": str(data.get("status") or "")[:40],
            "payload": data,
        },
    )
    if not created and obj.processed_at:
        return JsonResponse({"ok": True, "idempotent": True})

    now = timezone.now()
    try:
        invoice_id = obj.invoice_id
        if invoice_id:
            invoice = SubscriptionInvoice.objects.select_related("school", "plan").get(id=invoice_id)
            amount_raw = str(data.get("amount") or "").strip()
            amount = Decimal(amount_raw) if amount_raw else (invoice.total_amount or invoice.amount)
            method = str(data.get("method") or "OTHER").strip().upper()
            transaction_ref = str(data.get("transaction_ref") or "").strip()[:120]
            SubscriptionPayment.objects.create(invoice=invoice, amount=amount, method=method if method in dict(SubscriptionPayment.METHOD_CHOICES) else "OTHER", transaction_ref=transaction_ref, paid_at=timezone.now())
            paid_total = sum((p.amount for p in invoice.payments.all()), Decimal("0"))
            due_total = invoice.total_amount or invoice.amount or Decimal("0")
            if paid_total >= due_total and invoice.status != "PAID":
                invoice.status = "PAID"
                invoice.save(update_fields=["status"])
        obj.processed_at = now
        obj.process_error = ""
        obj.save(update_fields=["processed_at", "process_error"])
        try:
            ActivityLog.objects.create(
                actor=None,
                school_id=None,
                view_name="billing.webhook",
                action="billing.webhook",
                method="POST",
                path="/billing/webhooks/generic/",
                status_code=200,
                ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
                message=f"Webhook {provider} event_id={event_id} invoice_id={obj.invoice_id} processed",
            )
        except Exception:
            pass
    except Exception as exc:
        obj.process_error = str(exc)[:2000]
        obj.save(update_fields=["process_error"])
        return JsonResponse({"ok": False, "error": obj.process_error}, status=500)

    return JsonResponse({"ok": True})


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def coupon_list(request):
    coupons = SubscriptionCoupon.objects.all().order_by("-created_at")
    context = build_layout_context(request.user, current_section="billing")
    context["coupons"] = coupons[:200]
    return render(request, "billing/coupons_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("billing.manage")
def coupon_create(request):
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip().upper()
        discount_type = (request.POST.get("discount_type") or "PERCENT").strip().upper()
        value_raw = (request.POST.get("value") or "").strip()
        starts_on = _parse_date(request.POST.get("starts_on"))
        ends_on = _parse_date(request.POST.get("ends_on"))
        is_active = request.POST.get("is_active") == "on"
        max_uses_raw = (request.POST.get("max_uses") or "").strip()

        try:
            value = Decimal(value_raw) if value_raw else Decimal("0")
        except Exception:
            value = Decimal("0")
        try:
            max_uses = int(max_uses_raw) if max_uses_raw else 0
        except Exception:
            max_uses = 0

        if not code:
            messages.error(request, "Coupon code is required.")
        elif SubscriptionCoupon.objects.filter(code=code).exists():
            messages.error(request, "Coupon code already exists.")
        elif discount_type not in dict(SubscriptionCoupon.DISCOUNT_TYPE_CHOICES):
            messages.error(request, "Invalid discount type.")
        else:
            SubscriptionCoupon.objects.create(
                code=code,
                discount_type=discount_type,
                value=value,
                starts_on=starts_on,
                ends_on=ends_on,
                is_active=is_active,
                max_uses=max(0, max_uses),
            )
            messages.success(request, "Coupon created.")
            return redirect("/billing/coupons/")

    context = build_layout_context(request.user, current_section="billing")
    context["discount_type_choices"] = SubscriptionCoupon.DISCOUNT_TYPE_CHOICES
    context["today"] = date.today()
    return render(request, "billing/coupon_form.html", context)


def subscription_default_datetime():
    from django.utils import timezone

    return timezone.now()


def _parse_datetime(value):
    if not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(value)
    except Exception:
        return None


def _prorate_amount(monthly_amount, *, period_start, period_end):
    if not monthly_amount or monthly_amount <= 0:
        return Decimal("0.00")

    if period_end < period_start:
        return Decimal("0.00")

    total = Decimal("0")
    cursor = period_start
    while cursor <= period_end:
        days_in_month = calendar.monthrange(cursor.year, cursor.month)[1]
        month_end = cursor.replace(day=days_in_month)
        segment_end = month_end if month_end <= period_end else period_end
        segment_days = (segment_end - cursor).days + 1
        total += (monthly_amount * Decimal(segment_days) / Decimal(days_in_month))
        cursor = segment_end + timedelta(days=1)

    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calculate_invoice_amount(*, school_id, plan_id, period_start=None, period_end=None):
    plan = SubscriptionPlan.objects.filter(id=plan_id).first()
    if not plan:
        return Decimal("0")

    active_students = Student.objects.filter(school_id=school_id, is_active=True).count()

    if plan.billing_mode == "FLAT":
        base = Decimal(str(plan.price_monthly or 0))
        if period_start and period_end:
            return _prorate_amount(base, period_start=period_start, period_end=period_end)
        return base

    unit = Decimal(str(plan.unit_price or 0))
    if plan.billing_mode == "PER_STUDENT":
        base = unit * Decimal(active_students)
        if period_start and period_end:
            return _prorate_amount(base, period_start=period_start, period_end=period_end)
        return base

    if plan.billing_mode == "PER_500":
        slabs = int(math.ceil(active_students / 500.0)) if active_students else 1
        base = unit * Decimal(slabs)
        if period_start and period_end:
            return _prorate_amount(base, period_start=period_start, period_end=period_end)
        return base

    return Decimal("0")
