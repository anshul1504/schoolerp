import csv
import hashlib
import io
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.http import FileResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile

from apps.core.models import ActivityLog, AuditLogExport, EntityChangeLog
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context


def _sanitize_export_cell(value) -> str:
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _esc_html(value) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _filtered_logs(request):
    params = request.POST if request.method == "POST" else request.GET
    logs = ActivityLog.objects.select_related("actor", "school").all()

    query = (params.get("q") or "").strip()
    if query:
        logs = logs.filter(
            Q(actor__username__icontains=query)
            | Q(actor__email__icontains=query)
            | Q(path__icontains=query)
            | Q(view_name__icontains=query)
            | Q(action__icontains=query)
        )

    actor = (params.get("actor") or "").strip()
    if actor:
        logs = logs.filter(Q(actor__username__icontains=actor) | Q(actor__email__icontains=actor))

    school_id = (params.get("school_id") or "").strip()
    if school_id.isdigit():
        logs = logs.filter(school_id=int(school_id))

    action = (params.get("action") or "").strip()
    if action:
        logs = logs.filter(action__icontains=action)

    method = (params.get("method") or "").strip().upper()
    if method:
        logs = logs.filter(method=method)

    date_from = (params.get("date_from") or "").strip()
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)

    date_to = (params.get("date_to") or "").strip()
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    filters = {
        "q": query,
        "actor": actor,
        "school_id": school_id,
        "action": action,
        "method": method,
        "date_from": date_from,
        "date_to": date_to,
    }
    return logs, filters


def _export_csv_bytes(logs_qs):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["created_at", "actor", "actor_email", "school", "action", "method", "path", "status_code", "ip_address", "view_name"])
    row_count = 0
    for log in logs_qs.order_by("-created_at")[:100000]:
        writer.writerow(
            [
                _sanitize_export_cell(log.created_at.isoformat(sep=" ", timespec="seconds")),
                _sanitize_export_cell(getattr(log.actor, "username", "") if log.actor else ""),
                _sanitize_export_cell(getattr(log.actor, "email", "") if log.actor else ""),
                _sanitize_export_cell(getattr(log.school, "name", "") if log.school else ""),
                _sanitize_export_cell(log.action),
                _sanitize_export_cell(log.method),
                _sanitize_export_cell(log.path),
                _sanitize_export_cell(log.status_code or ""),
                _sanitize_export_cell(log.ip_address),
                _sanitize_export_cell(log.view_name),
            ]
        )
        row_count += 1
    return output.getvalue().encode("utf-8"), row_count


@role_required("SUPER_ADMIN")
@permission_required("activity.view")
def activity_list(request):
    logs, filters = _filtered_logs(request)

    if (request.GET.get("export") or "").lower() == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="activity_log.csv"'
        body, _row_count = _export_csv_bytes(logs)
        response.write(body)
        return response
    if (request.GET.get("export") or "").lower() == "excel":
        response = HttpResponse(content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = 'attachment; filename="activity_log.xls"'
        header_cells = "".join(
            f"<th>{column.replace('_', ' ').title()}</th>"
            for column in ["created_at", "actor", "actor_email", "school", "action", "method", "path", "status_code", "ip_address", "view_name"]
        )
        rows = []
        for log in logs.order_by("-created_at")[:10000]:
            rows.append(
                "<tr>"
                f"<td>{_esc_html(_sanitize_export_cell(log.created_at.isoformat(sep=' ', timespec='seconds')))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(getattr(log.actor, 'username', '') if log.actor else ''))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(getattr(log.actor, 'email', '') if log.actor else ''))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(getattr(log.school, 'name', '') if log.school else ''))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(log.action))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(log.method))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(log.path))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(log.status_code or ''))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(log.ip_address))}</td>"
                f"<td>{_esc_html(_sanitize_export_cell(log.view_name))}</td>"
                "</tr>"
            )
        response.write(f"<table><thead><tr>{header_cells}</tr></thead><tbody>{''.join(rows)}</tbody></table>")
        return response

    paginator = Paginator(logs, 50)
    page = paginator.get_page(request.GET.get("page") or 1)

    context = build_layout_context(request.user, current_section="activity")
    context.update(
        {
            "page_obj": page,
            "filters": filters,
        }
    )
    return render(request, "activity/list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("activity.view")
def activity_exports_list(request):
    exports = AuditLogExport.objects.select_related("created_by").all()[:200]
    context = build_layout_context(request.user, current_section="activity")
    context.update({"exports": exports})
    return render(request, "activity/exports.html", context)


@require_http_methods(["POST"])
@role_required("SUPER_ADMIN")
@permission_required("activity.view")
def activity_exports_create(request):
    logs, filters = _filtered_logs(request)
    csv_bytes, row_count = _export_csv_bytes(logs)

    sha256 = hashlib.sha256(csv_bytes).hexdigest()
    prev = AuditLogExport.objects.order_by("-id").first()
    prev_sha256 = prev.sha256 if prev else ""

    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"activity_log_{ts}_{sha256[:12]}.csv"

    immutable_copy_path = ""
    immutable_dir = str(getattr(settings, "AUDIT_EXPORT_IMMUTABLE_DIR", "") or "").strip()
    if immutable_dir:
        try:
            base = Path(immutable_dir)
            base.mkdir(parents=True, exist_ok=True)
            target = base / filename
            with target.open("xb") as f:
                f.write(csv_bytes)
            immutable_copy_path = str(target)
        except Exception:
            immutable_copy_path = ""

    export = AuditLogExport.objects.create(
        created_by=request.user,
        filters=filters,
        row_count=row_count,
        prev_sha256=prev_sha256,
        sha256=sha256,
        file=ContentFile(csv_bytes, name=filename),
        immutable_copy_path=immutable_copy_path,
    )
    return redirect("activity-exports-download", id=export.id)


@role_required("SUPER_ADMIN")
@permission_required("activity.view")
def activity_exports_download(request, id):
    export = get_object_or_404(AuditLogExport.objects.select_related("created_by"), id=id)

    verify = (request.GET.get("verify") or "").lower() in {"1", "true", "yes"}
    if verify:
        file_bytes = export.file.read()
        export.file.seek(0)
        actual = hashlib.sha256(file_bytes).hexdigest()
        if actual != export.sha256:
            context = build_layout_context(request.user, current_section="activity")
            context.update({"export": export, "actual_sha256": actual})
            return render(request, "activity/export_tampered.html", context, status=409)

    resp = FileResponse(export.file.open("rb"), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{export.file.name.split("/")[-1]}"'
    resp["X-Audit-Export-SHA256"] = export.sha256
    resp["X-Audit-Export-Prev-SHA256"] = export.prev_sha256 or ""
    return resp


@role_required("SUPER_ADMIN")
@permission_required("activity.view")
def activity_change_log_list(request):
    entity = (request.GET.get("entity") or "").strip()
    object_id = (request.GET.get("object_id") or "").strip()

    logs = EntityChangeLog.objects.select_related("actor").all()
    if entity:
        logs = logs.filter(entity__icontains=entity)
    if object_id:
        logs = logs.filter(object_id=object_id)

    context = build_layout_context(request.user, current_section="activity")
    context.update({"logs": logs[:200], "filters": {"entity": entity, "object_id": object_id}})
    return render(request, "activity/change_logs.html", context)
