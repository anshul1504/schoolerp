import csv
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import permission_required, role_required
from apps.core.permissions import has_permission
from apps.core.tenancy import allowed_school_ids_for_user, selected_school_for_request, school_scope_for_user
from apps.core.ui import build_layout_context
from apps.core.models import ActivityLog
from apps.schools.models import School

from .forms import StaffMemberForm
from .models import StaffMember


def _selected_school(request):
    return selected_school_for_request(request)


STAFF_IMPORT_HEADERS = ["full_name", "staff_role", "employee_id", "designation", "phone", "email", "joined_on", "is_active"]
STAFF_IMPORT_SESSION_KEY = "staff_import_preview_v1"


def _sanitize_csv_cell(value) -> str:
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _parse_bool(value, default=False) -> bool:
    raw = (str(value or "")).strip().lower()
    if raw in {"1", "true", "yes", "y", "active"}:
        return True
    if raw in {"0", "false", "no", "n", "inactive"}:
        return False
    return default


def _read_csv_upload(upload) -> list[dict]:
    data = upload.read()
    try:
        text = data.decode("utf-8-sig")
    except Exception:
        text = data.decode("utf-8", errors="ignore")
    reader = csv.DictReader(text.splitlines())
    rows: list[dict] = []
    for row in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in (row or {}).items()})
    return rows


def _read_xlsx_upload(upload) -> list[dict]:
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    with ZipFile(upload) as workbook:
        shared_strings = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(node.itertext()) for node in root.findall("main:si", ns)]
        sheet_root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        parsed_rows = []
        for row in sheet_root.findall(".//main:sheetData/main:row", ns):
            values = []
            for cell in row.findall("main:c", ns):
                value = cell.find("main:v", ns)
                cell_value = value.text if value is not None else ""
                if cell.get("t") == "s" and cell_value:
                    cell_value = shared_strings[int(cell_value)]
                values.append(cell_value)
            parsed_rows.append(values)
        if not parsed_rows:
            return rows
        headers = [header.strip() for header in parsed_rows[0]]
        for values in parsed_rows[1:]:
            padded = values + [""] * (len(headers) - len(values))
            rows.append(dict(zip(headers, padded)))
    return rows


def _validate_staff_import_row(row: dict) -> tuple[dict, list[str]]:
    errors: list[str] = []
    full_name = (row.get("full_name") or "").strip()
    staff_role = (row.get("staff_role") or "").strip().upper()
    employee_id = (row.get("employee_id") or "").strip()
    designation = (row.get("designation") or "").strip()
    phone = (row.get("phone") or "").strip()
    email = (row.get("email") or "").strip()
    joined_on = (row.get("joined_on") or "").strip()  # YYYY-MM-DD
    is_active = _parse_bool(row.get("is_active"), default=True)

    if not full_name:
        errors.append("full_name is required")
    if staff_role not in {"TEACHER", "STAFF"}:
        errors.append("staff_role must be TEACHER or STAFF")
    if joined_on and len(joined_on) != 10:
        errors.append("joined_on must be YYYY-MM-DD")

    payload = {
        "full_name": full_name,
        "staff_role": staff_role or "STAFF",
        "employee_id": employee_id,
        "designation": designation,
        "phone": phone,
        "email": email,
        "joined_on": joined_on,
        "is_active": is_active,
    }
    return payload, errors


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.view")
def staff_list(request):
    school = _selected_school(request)
    school_ids = allowed_school_ids_for_user(request.user)
    qs = StaffMember.objects.select_related("school").filter(school_id__in=school_ids)
    if school:
        qs = qs.filter(school=school)

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip().upper()
    if q:
        qs = qs.filter(full_name__icontains=q)
    if role in {"TEACHER", "STAFF"}:
        qs = qs.filter(staff_role=role)

    context = build_layout_context(request.user, current_section="staff")
    context.update(
        {
            "school_options": school_scope_for_user(request.user),
            "selected_school": school,
            "members": qs.order_by("full_name")[:500],
            "filters": {"q": q, "role": role},
            "can_manage": has_permission(request.user, "staff.manage"),
        }
    )
    return render(request, "staff/list.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.manage")
def staff_create(request):
    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a school first.")
        return redirect("/staff/")

    if school.id not in allowed_school_ids_for_user(request.user):
        messages.error(request, "Invalid school selection.")
        return redirect("/staff/")

    if request.method == "POST":
        form = StaffMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.school = school
            member.save()
            messages.success(request, "Staff member created.")
            return redirect("/staff/?school=%s" % school.id)
        messages.error(request, "Please fix the errors and try again.")
    else:
        form = StaffMemberForm()

    context = build_layout_context(request.user, current_section="staff")
    context.update({"selected_school": school, "form": form})
    return render(request, "staff/form.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.manage")
def staff_edit(request, id):
    school_ids = allowed_school_ids_for_user(request.user)
    member = get_object_or_404(StaffMember, id=id, school_id__in=school_ids)

    if request.method == "POST":
        form = StaffMemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, "Staff member updated.")
            return redirect("/staff/?school=%s" % member.school_id)
        messages.error(request, "Please fix the errors and try again.")
    else:
        form = StaffMemberForm(instance=member)

    context = build_layout_context(request.user, current_section="staff")
    context.update({"member": member, "form": form})
    return render(request, "staff/form.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.manage")
def staff_delete(request, id):
    school_ids = allowed_school_ids_for_user(request.user)
    member = get_object_or_404(StaffMember, id=id, school_id__in=school_ids)

    if request.method == "POST":
        school_id = member.school_id
        member.delete()
        messages.success(request, "Staff member deleted.")
        return redirect("/staff/?school=%s" % school_id)

    messages.error(request, "Invalid delete request.")
    return redirect("/staff/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.manage")
def staff_import(request):
    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a school first.")
        return redirect("/staff/")

    if school.id not in allowed_school_ids_for_user(request.user):
        messages.error(request, "Invalid school selection.")
        return redirect("/staff/")

    if request.method == "POST":
        stage = (request.POST.get("stage") or "preview").strip().lower()
        if stage == "confirm":
            preview = request.session.get(STAFF_IMPORT_SESSION_KEY) or {}
            rows = preview.get("rows") or []
            if not rows:
                messages.error(request, "Import preview expired. Please upload the file again.")
                return redirect(f"/staff/import/?school={school.id}")

            created = 0
            updated = 0
            skipped = 0
            errors_out: list[dict] = []

            for row in rows:
                payload = row.get("payload") or {}
                row_errors = row.get("errors") or []
                if row_errors:
                    skipped += 1
                    errors_out.append({"row": row.get("row_index"), "errors": "; ".join(row_errors), **(row.get("raw") or {})})
                    continue

                employee_id = (payload.get("employee_id") or "").strip()
                defaults = {
                    "full_name": payload.get("full_name") or "",
                    "staff_role": payload.get("staff_role") or "STAFF",
                    "designation": payload.get("designation") or "",
                    "phone": payload.get("phone") or "",
                    "email": payload.get("email") or "",
                    "joined_on": payload.get("joined_on") or None,
                    "is_active": bool(payload.get("is_active", True)),
                }

                # Update by employee_id when provided; otherwise create new row.
                if employee_id:
                    obj = StaffMember.objects.filter(school=school, employee_id=employee_id).only("id").first()
                    if obj:
                        StaffMember.objects.filter(id=obj.id).update(**defaults)
                        updated += 1
                    else:
                        StaffMember.objects.create(school=school, employee_id=employee_id, **defaults)
                        created += 1
                else:
                    StaffMember.objects.create(school=school, **defaults)
                    created += 1

            request.session[STAFF_IMPORT_SESSION_KEY] = {"errors": errors_out}
            parts = []
            if created:
                parts.append(f"{created} created")
            if updated:
                parts.append(f"{updated} updated")
            if skipped:
                parts.append(f"{skipped} skipped")
            if parts:
                messages.success(request, "Staff import summary: " + ", ".join(parts) + ".")
            else:
                messages.info(request, "No rows were imported.")

            try:
                ActivityLog.objects.create(
                    actor=request.user,
                    school_id=school.id,
                    view_name="staff.import",
                    action="staff.import",
                    method="POST",
                    path="/staff/import/",
                    status_code=200,
                    ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                    user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
                    message=f"Staff import: school_id={school.id}, created={created}, updated={updated}, skipped={skipped}",
                )
            except Exception:
                pass

            return redirect(f"/staff/import/?school={school.id}")

        import_file = request.FILES.get("import_file")
        if not import_file:
            messages.error(request, "Choose a CSV file to import.")
            return redirect(f"/staff/import/?school={school.id}")
        extension = import_file.name.lower().rsplit(".", 1)[-1]
        if extension not in {"csv", "xlsx"}:
            messages.error(request, "Only CSV and XLSX are supported for Staff import right now.")
            return redirect(f"/staff/import/?school={school.id}")

        try:
            if extension == "csv":
                raw_rows = _read_csv_upload(import_file)
            else:
                raw_rows = _read_xlsx_upload(import_file)
        except Exception:
            messages.error(request, "We could not read that file. Please check headers and try again.")
            return redirect(f"/staff/import/?school={school.id}")

        preview_rows: list[dict] = []
        invalid_count = 0
        for idx, raw in enumerate(raw_rows[:5000], start=1):
            payload, row_errors = _validate_staff_import_row(raw)
            if row_errors:
                invalid_count += 1
            payload["joined_on"] = (payload.get("joined_on") or "").strip() or None
            preview_rows.append(
                {
                    "row_index": idx,
                    "raw": raw,
                    "cells": [raw.get(h, "") for h in STAFF_IMPORT_HEADERS],
                    "payload": payload,
                    "errors": row_errors,
                }
            )

        request.session[STAFF_IMPORT_SESSION_KEY] = {"rows": preview_rows, "errors": []}

        context = build_layout_context(request.user, current_section="staff")
        context.update(
            {
                "selected_school": school,
                "headers": STAFF_IMPORT_HEADERS,
                "preview_rows": preview_rows[:50],
                "total_rows": len(preview_rows),
                "invalid_count": invalid_count,
                "school_options": school_scope_for_user(request.user),
            }
        )
        return render(request, "staff/import_preview.html", context)

    context = build_layout_context(request.user, current_section="staff")
    context.update({"selected_school": school, "headers": STAFF_IMPORT_HEADERS, "school_options": school_scope_for_user(request.user)})
    return render(request, "staff/import.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.manage")
def staff_import_errors_csv(request):
    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a school first.")
        return redirect("/staff/")
    if school.id not in allowed_school_ids_for_user(request.user):
        messages.error(request, "Invalid school selection.")
        return redirect("/staff/")

    preview = request.session.get(STAFF_IMPORT_SESSION_KEY) or {}
    errors_out = preview.get("errors") or []
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="staff_import_errors.csv"'
    writer = csv.writer(response)
    writer.writerow(["row", "errors", *STAFF_IMPORT_HEADERS])
    for item in errors_out[:20000]:
        writer.writerow(
            [
                item.get("row") or "",
                _sanitize_csv_cell(item.get("errors") or ""),
                _sanitize_csv_cell(item.get("full_name") or ""),
                _sanitize_csv_cell(item.get("staff_role") or ""),
                _sanitize_csv_cell(item.get("employee_id") or ""),
                _sanitize_csv_cell(item.get("designation") or ""),
                _sanitize_csv_cell(item.get("phone") or ""),
                _sanitize_csv_cell(item.get("email") or ""),
                _sanitize_csv_cell(item.get("joined_on") or ""),
                _sanitize_csv_cell(item.get("is_active") or ""),
            ]
        )
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.manage")
def staff_import_sample(request, file_type):
    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a school first.")
        return redirect("/staff/")
    if school.id not in allowed_school_ids_for_user(request.user):
        messages.error(request, "Invalid school selection.")
        return redirect("/staff/")

    if file_type != "csv":
        messages.error(request, "Unsupported sample file type.")
        return redirect(f"/staff/import/?school={school.id}")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="staff-import-sample.csv"'
    writer = csv.writer(response)
    writer.writerow(STAFF_IMPORT_HEADERS)
    writer.writerow(["Rahul Mehta", "TEACHER", "EMP-001", "Math Teacher", "9876543210", "rahul@example.com", "2026-04-01", "yes"])
    writer.writerow(["Priya Singh", "STAFF", "EMP-002", "Office Admin", "9876543222", "priya@example.com", "2026-04-10", "yes"])
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.view")
def staff_export_csv(request):
    school = _selected_school(request)
    school_ids = allowed_school_ids_for_user(request.user)
    qs = StaffMember.objects.select_related("school").filter(school_id__in=school_ids)
    if school:
        qs = qs.filter(school=school)

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip().upper()
    if q:
        qs = qs.filter(full_name__icontains=q)
    if role in {"TEACHER", "STAFF"}:
        qs = qs.filter(staff_role=role)

    raw_ids = (request.GET.get("staff_ids") or request.GET.get("ids") or "").strip()
    if raw_ids:
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if ids:
            qs = qs.filter(id__in=sorted(set(ids)))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="staff_export.csv"'
    writer = csv.writer(response)
    writer.writerow(["id", "school", "full_name", "staff_role", "employee_id", "designation", "phone", "email", "joined_on", "is_active"])
    for m in qs.order_by("full_name", "id")[:20000]:
        writer.writerow(
            [
                m.id,
                _sanitize_csv_cell(m.school.name if m.school else ""),
                _sanitize_csv_cell(m.full_name),
                _sanitize_csv_cell(m.staff_role),
                _sanitize_csv_cell(m.employee_id),
                _sanitize_csv_cell(m.designation),
                _sanitize_csv_cell(m.phone),
                _sanitize_csv_cell(m.email),
                _sanitize_csv_cell(m.joined_on),
                _sanitize_csv_cell("yes" if m.is_active else "no"),
            ]
        )
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
@permission_required("staff.view")
def staff_export_excel(request):
    school = _selected_school(request)
    school_ids = allowed_school_ids_for_user(request.user)
    qs = StaffMember.objects.select_related("school").filter(school_id__in=school_ids)
    if school:
        qs = qs.filter(school=school)

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip().upper()
    if q:
        qs = qs.filter(full_name__icontains=q)
    if role in {"TEACHER", "STAFF"}:
        qs = qs.filter(staff_role=role)

    raw_ids = (request.GET.get("staff_ids") or request.GET.get("ids") or "").strip()
    if raw_ids:
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if ids:
            qs = qs.filter(id__in=sorted(set(ids)))

    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="staff_export.xls"'

    def esc(value) -> str:
        return (
            _sanitize_csv_cell(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    rows = []
    for m in qs.order_by("full_name", "id")[:20000]:
        rows.append(
            "<tr>"
            f"<td>{esc(m.id)}</td>"
            f"<td>{esc(m.school.name if m.school else '')}</td>"
            f"<td>{esc(m.full_name)}</td>"
            f"<td>{esc(m.staff_role)}</td>"
            f"<td>{esc(m.employee_id)}</td>"
            f"<td>{esc(m.designation)}</td>"
            f"<td>{esc(m.phone)}</td>"
            f"<td>{esc(m.email)}</td>"
            f"<td>{esc(m.joined_on)}</td>"
            f"<td>{esc('yes' if m.is_active else 'no')}</td>"
            "</tr>"
        )

    response.write(
        "<table><thead><tr>"
        "<th>id</th><th>school</th><th>full_name</th><th>staff_role</th><th>employee_id</th>"
        "<th>designation</th><th>phone</th><th>email</th><th>joined_on</th><th>is_active</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    return response
