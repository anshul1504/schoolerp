import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import User
from apps.core.models import ActivityLog, ReportTemplate
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context
from apps.fees.models import FeePayment, StudentFeeLedger
from apps.schools.models import School
from apps.students.models import Student


def _sanitize_cell(value) -> str:
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _parse_json_dict(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_json_list(raw: str) -> list:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _export_report(template: ReportTemplate) -> tuple[list[str], list[list]]:
    filters = template.filters or {}
    columns = template.columns or []

    def pick_columns(default_cols: list[str]) -> list[str]:
        return [c for c in columns if c in default_cols] or default_cols

    if template.dataset == "SCHOOLS":
        default_cols = ["id", "name", "code", "email", "phone", "city", "state", "is_active", "created_at"]
        cols = pick_columns(default_cols)
        qs = School.objects.all().order_by("-created_at")
        if str(filters.get("is_active") or "").lower() in {"true", "1", "yes"}:
            qs = qs.filter(is_active=True)
        rows = [[getattr(s, c, "") for c in cols] for s in qs[:5000]]
        return cols, rows

    if template.dataset == "USERS":
        default_cols = ["id", "username", "email", "first_name", "last_name", "role", "school_id", "is_active", "date_joined"]
        cols = pick_columns(default_cols)
        qs = User.objects.all().order_by("-date_joined")
        role = (filters.get("role") or "").strip().upper()
        if role:
            qs = qs.filter(role=role)
        school_id = str(filters.get("school_id") or "").strip()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        rows = [[getattr(u, c, "") for c in cols] for u in qs[:5000]]
        return cols, rows

    if template.dataset == "ACTIVITY":
        default_cols = ["created_at", "actor", "school", "action", "method", "path", "status_code", "ip_address"]
        cols = pick_columns(default_cols)
        qs = ActivityLog.objects.select_related("actor", "school").all().order_by("-created_at")
        school_id = str(filters.get("school_id") or "").strip()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        rows = []
        for log in qs[:5000]:
            actor = getattr(log.actor, "username", "") if log.actor else ""
            school = getattr(log.school, "name", "") if log.school else ""
            mapping = {
                "created_at": log.created_at,
                "actor": actor,
                "school": school,
                "action": log.action,
                "method": log.method,
                "path": log.path,
                "status_code": log.status_code,
                "ip_address": log.ip_address,
            }
            rows.append([mapping.get(c, "") for c in cols])
        return cols, rows

    if template.dataset == "STUDENTS":
        default_cols = ["id", "school_id", "admission_no", "first_name", "last_name", "class_name", "section", "guardian_name", "guardian_phone", "is_active"]
        cols = pick_columns(default_cols)
        qs = Student.objects.all().order_by("-id")
        school_id = str(filters.get("school_id") or "").strip()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        status = str(filters.get("status") or "").strip().lower()
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        rows = [[getattr(s, c, "") for c in cols] for s in qs[:5000]]
        return cols, rows

    if template.dataset == "FEES_PAYMENTS":
        default_cols = ["id", "school_id", "student_id", "amount", "payment_date", "payment_mode", "reference_no", "collected_by_id", "created_at"]
        cols = pick_columns(default_cols)
        qs = FeePayment.objects.all().order_by("-payment_date", "-id")
        school_id = str(filters.get("school_id") or "").strip()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        rows = [[getattr(p, c, "") for c in cols] for p in qs[:5000]]
        return cols, rows

    if template.dataset == "FEES_LEDGER":
        default_cols = ["id", "school_id", "student_id", "billing_month", "amount_due", "amount_paid", "due_date", "status", "created_at"]
        cols = pick_columns(default_cols)
        qs = StudentFeeLedger.objects.all().order_by("-due_date", "-id")
        school_id = str(filters.get("school_id") or "").strip()
        if school_id.isdigit():
            qs = qs.filter(school_id=int(school_id))
        rows = [[getattr(l, c, "") for c in cols] for l in qs[:5000]]
        return cols, rows

    return ["note"], [["Unsupported dataset"]]


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def report_builder_list(request):
    templates = ReportTemplate.objects.all()
    context = build_layout_context(request.user, current_section="reports")
    context["templates"] = templates[:200]
    context["dataset_choices"] = ReportTemplate.DATASET_CHOICES
    return render(request, "reports/builder_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def report_builder_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        dataset = (request.POST.get("dataset") or "").strip().upper()
        filters = _parse_json_dict(request.POST.get("filters") or "")
        columns = _parse_json_list(request.POST.get("columns") or "")
        is_active = request.POST.get("is_active") == "on"

        if not name or dataset not in dict(ReportTemplate.DATASET_CHOICES):
            messages.error(request, "Name and dataset are required.")
        else:
            ReportTemplate.objects.create(name=name, dataset=dataset, filters=filters, columns=columns, is_active=is_active)
            messages.success(request, "Report template created.")
            return redirect("/reports/builder/")

    context = build_layout_context(request.user, current_section="reports")
    context.update({"mode": "create", "dataset_choices": ReportTemplate.DATASET_CHOICES})
    return render(request, "reports/builder_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def report_builder_update(request, id):
    template = get_object_or_404(ReportTemplate, id=id)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        dataset = (request.POST.get("dataset") or template.dataset).strip().upper()
        filters = _parse_json_dict(request.POST.get("filters") or "")
        columns = _parse_json_list(request.POST.get("columns") or "")
        is_active = request.POST.get("is_active") == "on"

        if not name or dataset not in dict(ReportTemplate.DATASET_CHOICES):
            messages.error(request, "Name and dataset are required.")
        else:
            template.name = name
            template.dataset = dataset
            template.filters = filters
            template.columns = columns
            template.is_active = is_active
            template.save()
            messages.success(request, "Report template updated.")
            return redirect("/reports/builder/")

    context = build_layout_context(request.user, current_section="reports")
    context.update(
        {
            "mode": "edit",
            "template": template,
            "filters_json": json.dumps(template.filters or {}, indent=2),
            "columns_json": json.dumps(template.columns or [], indent=2),
            "dataset_choices": ReportTemplate.DATASET_CHOICES,
        }
    )
    return render(request, "reports/builder_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def report_builder_delete(request, id):
    template = get_object_or_404(ReportTemplate, id=id)
    if request.method != "POST":
        messages.error(request, "Invalid delete request.")
        return redirect("/reports/builder/")
    template.delete()
    messages.success(request, "Report template deleted.")
    return redirect("/reports/builder/")


@role_required("SUPER_ADMIN")
@permission_required("reports.view")
def report_builder_export_csv(request, id):
    template = get_object_or_404(ReportTemplate, id=id, is_active=True)
    headers, rows = _export_report(template)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="report_{template.id}.csv"'
    out = []
    out.append(",".join(_sanitize_cell(h) for h in headers))
    for row in rows:
        out.append(",".join(_sanitize_cell(v) for v in row))
    response.write("\n".join(out))
    return response

