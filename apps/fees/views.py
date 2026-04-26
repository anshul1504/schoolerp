from decimal import Decimal

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.permissions import role_required
from apps.core.permissions import has_permission
from apps.core.ui import build_layout_context
from apps.schools.models import School
from apps.core.tenancy import school_scope_for_user, selected_school_for_request
from apps.students.models import Student

from .models import FeePayment, FeeStructure, StudentFeeLedger

import csv


PAYMENT_MODE_OPTIONS = [choice[0] for choice in FeePayment.PAYMENT_MODE_CHOICES]
FREQUENCY_OPTIONS = ["MONTHLY", "QUARTERLY", "YEARLY", "ONE_TIME"]


def _school_scope(user):
    return school_scope_for_user(user)


def _selected_school(request):
    return selected_school_for_request(request)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "ACCOUNTANT", "STUDENT", "PARENT")
def fees_overview(request):
    is_owner = request.user.role == "SCHOOL_OWNER"

    if request.method == "POST" and not has_permission(request.user, "fees.manage"):
        messages.error(request, "You do not have permission to manage fees.")
        return redirect("/fees/")

    if not has_permission(request.user, "fees.view"):
        messages.error(request, "You do not have permission to view fees.")
        return redirect("dashboard")

    school = _selected_school(request)
    if request.user.role == "SUPER_ADMIN" and school is None:
        if request.method == "POST":
            messages.error(request, "Select a school before managing fees.")
            return redirect("/fees/")
    structures = FeeStructure.objects.select_related("school")
    ledgers = StudentFeeLedger.objects.select_related("school", "student", "fee_structure")
    payments = FeePayment.objects.select_related("school", "student", "ledger", "collected_by")

    if school:
      structures = structures.filter(school=school)
      ledgers = ledgers.filter(school=school)
      payments = payments.filter(school=school)
      students = Student.objects.filter(school=school, is_active=True).order_by("first_name", "last_name")
    elif request.user.school_id:
      structures = structures.filter(school_id=request.user.school_id)
      ledgers = ledgers.filter(school_id=request.user.school_id)
      payments = payments.filter(school_id=request.user.school_id)
      students = Student.objects.filter(school_id=request.user.school_id, is_active=True).order_by("first_name", "last_name")
    else:
      structures = structures.none()
      ledgers = ledgers.none()
      payments = payments.none()
      students = Student.objects.none()

    def sanitize_cell(value) -> str:
        text = str(value or "")
        if text and text[0] in ("=", "+", "-", "@"):
            return f"'{text}"
        return text

    def esc(value) -> str:
        return (
            sanitize_cell(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    export_format = (request.GET.get("export") or "").strip().lower()
    dataset = (request.GET.get("dataset") or "").strip().lower()
    if export_format in {"csv", "excel"}:
        if is_owner:
            messages.error(request, "Export access is restricted for School Owner in this workspace.")
            return redirect("/fees/")

        if school is None:
            messages.error(request, "Select a school before exporting fees data.")
            return redirect("/fees/")

        if dataset not in {"ledgers", "payments"}:
            messages.error(request, "Invalid export dataset.")
            return redirect(f"/fees/?school={school.id}")

        if dataset == "ledgers":
            qs = ledgers.order_by("-due_date", "-id")
            raw_ids = (request.GET.get("ledger_ids") or request.GET.get("ids") or "").strip()
            if raw_ids:
                ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
                if ids:
                    qs = qs.filter(id__in=sorted(set(ids)))

            if export_format == "csv":
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="fee_ledgers.csv"'
                writer = csv.writer(response)
                writer.writerow(["id", "student", "billing_month", "fee_structure", "amount_due", "amount_paid", "due_date", "status"])
                for row in qs[:10000]:
                    writer.writerow(
                        [
                            row.id,
                            sanitize_cell(f"{row.student.first_name} {row.student.last_name}".strip()),
                            sanitize_cell(row.billing_month),
                            sanitize_cell(row.fee_structure.name if row.fee_structure else ""),
                            sanitize_cell(row.amount_due),
                            sanitize_cell(row.amount_paid),
                            sanitize_cell(row.due_date),
                            sanitize_cell(row.status),
                        ]
                    )
                return response

            response = HttpResponse(content_type="application/vnd.ms-excel")
            response["Content-Disposition"] = 'attachment; filename="fee_ledgers.xls"'
            rows_html = []
            for row in qs[:10000]:
                rows_html.append(
                    "<tr>"
                    f"<td>{esc(row.id)}</td>"
                    f"<td>{esc(f'{row.student.first_name} {row.student.last_name}'.strip())}</td>"
                    f"<td>{esc(row.billing_month)}</td>"
                    f"<td>{esc(row.fee_structure.name if row.fee_structure else '')}</td>"
                    f"<td>{esc(row.amount_due)}</td>"
                    f"<td>{esc(row.amount_paid)}</td>"
                    f"<td>{esc(row.due_date)}</td>"
                    f"<td>{esc(row.status)}</td>"
                    "</tr>"
                )
            response.write(
                "<table><thead><tr>"
                "<th>id</th><th>student</th><th>billing_month</th><th>fee_structure</th>"
                "<th>amount_due</th><th>amount_paid</th><th>due_date</th><th>status</th>"
                f"</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"
            )
            return response

        if dataset == "payments":
            qs = payments.order_by("-payment_date", "-created_at", "-id")
            raw_ids = (request.GET.get("payment_ids") or request.GET.get("ids") or "").strip()
            if raw_ids:
                ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
                if ids:
                    qs = qs.filter(id__in=sorted(set(ids)))

            if export_format == "csv":
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="fee_payments.csv"'
                writer = csv.writer(response)
                writer.writerow(["id", "student", "billing_month", "amount", "payment_date", "payment_mode", "reference_no", "collector"])
                for row in qs[:10000]:
                    collector = row.collected_by.get_full_name() if row.collected_by else ""
                    if not collector and row.collected_by:
                        collector = row.collected_by.username
                    writer.writerow(
                        [
                            row.id,
                            sanitize_cell(f"{row.student.first_name} {row.student.last_name}".strip()),
                            sanitize_cell(row.ledger.billing_month if row.ledger else ""),
                            sanitize_cell(row.amount),
                            sanitize_cell(row.payment_date),
                            sanitize_cell(row.payment_mode),
                            sanitize_cell(row.reference_no),
                            sanitize_cell(collector),
                        ]
                    )
                return response

            response = HttpResponse(content_type="application/vnd.ms-excel")
            response["Content-Disposition"] = 'attachment; filename="fee_payments.xls"'
            rows_html = []
            for row in qs[:10000]:
                collector = row.collected_by.get_full_name() if row.collected_by else ""
                if not collector and row.collected_by:
                    collector = row.collected_by.username
                rows_html.append(
                    "<tr>"
                    f"<td>{esc(row.id)}</td>"
                    f"<td>{esc(f'{row.student.first_name} {row.student.last_name}'.strip())}</td>"
                    f"<td>{esc(row.ledger.billing_month if row.ledger else '')}</td>"
                    f"<td>{esc(row.amount)}</td>"
                    f"<td>{esc(row.payment_date)}</td>"
                    f"<td>{esc(row.payment_mode)}</td>"
                    f"<td>{esc(row.reference_no)}</td>"
                    f"<td>{esc(collector)}</td>"
                    "</tr>"
                )
            response.write(
                "<table><thead><tr>"
                "<th>id</th><th>student</th><th>billing_month</th><th>amount</th><th>payment_date</th>"
                "<th>payment_mode</th><th>reference_no</th><th>collector</th>"
                f"</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"
            )
            return response

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if school is None:
            messages.error(request, "Select a valid school before managing fees.")
            return redirect("/fees/")

        if action == "create_structure":
            name = request.POST.get("name", "").strip()
            class_name = request.POST.get("class_name", "").strip()
            amount = request.POST.get("amount", "").strip()
            if not name or not class_name or not amount:
                messages.error(request, "Fee structure needs name, class, and amount.")
            else:
                try:
                    amount_value = Decimal(amount)
                    due_day = int(request.POST.get("due_day") or 10)
                except (ArithmeticError, ValueError):
                    messages.error(request, "Enter a valid amount and due day.")
                    return redirect(f"/fees/?school={school.id}")

                if amount_value <= 0:
                    messages.error(request, "Fee amount must be greater than zero.")
                    return redirect(f"/fees/?school={school.id}")

                if due_day < 1 or due_day > 31:
                    messages.error(request, "Due day must be between 1 and 31.")
                    return redirect(f"/fees/?school={school.id}")

                FeeStructure.objects.get_or_create(
                    school=school,
                    name=name,
                    class_name=class_name,
                    defaults={
                        "amount": amount_value,
                        "frequency": request.POST.get("frequency", "MONTHLY"),
                        "due_day": due_day,
                    },
                )
                messages.success(request, "Fee structure created successfully.")
            return redirect(f"/fees/?school={school.id}")

        if action == "create_due":
            student = get_object_or_404(Student, id=request.POST.get("student"), school=school)
            fee_structure = get_object_or_404(FeeStructure, id=request.POST.get("fee_structure"), school=school)
            billing_month = request.POST.get("billing_month", "").strip()
            due_date = request.POST.get("due_date")
            amount_due_raw = (request.POST.get("amount_due") or "").strip()
            if not billing_month or not due_date:
                messages.error(request, "Billing month and due date are required.")
            else:
                if amount_due_raw:
                    try:
                        amount_due = Decimal(amount_due_raw)
                    except (ArithmeticError, ValueError):
                        messages.error(request, "Amount due must be a valid number.")
                        return redirect(f"/fees/?school={school.id}")
                else:
                    amount_due = fee_structure.amount

                if amount_due <= 0:
                    messages.error(request, "Amount due must be greater than zero.")
                    return redirect(f"/fees/?school={school.id}")

                StudentFeeLedger.objects.get_or_create(
                    school=school,
                    student=student,
                    fee_structure=fee_structure,
                    billing_month=billing_month,
                    defaults={
                        "amount_due": amount_due,
                        "due_date": due_date,
                    },
                )
                messages.success(request, "Student fee due created successfully.")
            return redirect(f"/fees/?school={school.id}")

        if action == "collect_payment":
            ledger = get_object_or_404(StudentFeeLedger, id=request.POST.get("ledger"), school=school)
            try:
                amount = Decimal(request.POST.get("amount") or "0")
            except (ArithmeticError, ValueError):
                messages.error(request, "Payment amount must be a valid number.")
                return redirect(f"/fees/?school={school.id}")

            if amount <= 0:
                messages.error(request, "Payment amount must be greater than zero.")
            else:
                FeePayment.objects.create(
                    ledger=ledger,
                    school=school,
                    student=ledger.student,
                    amount=amount,
                    payment_date=request.POST.get("payment_date") or timezone.localdate(),
                    payment_mode=request.POST.get("payment_mode", "CASH"),
                    reference_no=request.POST.get("reference_no", "").strip(),
                    collected_by=request.user,
                )
                ledger.amount_paid = (ledger.amount_paid or Decimal("0")) + amount
                if ledger.amount_paid >= ledger.amount_due:
                    ledger.status = "PAID"
                elif ledger.amount_paid > 0:
                    ledger.status = "PARTIAL"
                else:
                    ledger.status = "DUE"
                ledger.save(update_fields=["amount_paid", "status"])
                messages.success(request, "Payment collected successfully.")
            return redirect(f"/fees/?school={school.id}")

    context = build_layout_context(request.user, current_section="fees")
    context["school_options"] = _school_scope(request.user)
    context["selected_school"] = school
    context["fee_structures"] = structures.order_by("class_name", "name")
    context["fee_ledgers"] = ledgers.order_by("-due_date")[:12]
    context["fee_payments"] = payments.order_by("-payment_date", "-created_at")[:12]
    context["student_options"] = students
    context["payment_mode_options"] = PAYMENT_MODE_OPTIONS
    context["frequency_options"] = FREQUENCY_OPTIONS
    context["today"] = timezone.localdate()
    context["fees_stats"] = {
        "structures": structures.count(),
        "dues": ledgers.count(),
        "paid": ledgers.filter(status="PAID").count(),
        "outstanding": sum(max((ledger.amount_due - ledger.amount_paid), Decimal("0")) for ledger in ledgers),
    }
    return render(request, "fees/overview.html", context)
