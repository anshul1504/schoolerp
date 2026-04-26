from datetime import timedelta
import uuid
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.mail import EmailMultiAlternatives
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
import csv
from django.conf import settings

from apps.accounts.models import User
from apps.accounts.models import UserInvitation
from apps.accounts.roles import grouped_role_choices
from apps.core.permissions import permission_required, role_required
from apps.core.models import ActivityLog
from apps.core.ui import build_layout_context
from apps.schools.models import School
from apps.core.throttle import throttle_hit


USER_IMPORT_HEADERS = ["username", "email", "first_name", "last_name", "role", "school_id", "is_active"]
USER_IMPORT_SESSION_KEY = "users_import_preview_v1"
IMPERSONATE_SESSION_KEY = "impersonate_original_user_id_v1"


def _role_context():
    return {
        "role_choices": User.ROLE_CHOICES,
        "grouped_role_choices": grouped_role_choices(User.ROLE_CHOICES),
    }


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
    # Accept only UTF-8 CSV for now.
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


def _validate_user_import_row(row: dict, schools_by_id: dict[int, School]) -> tuple[dict, list[str]]:
    errors: list[str] = []
    username = (row.get("username") or "").strip()
    role = (row.get("role") or "").strip()
    email = (row.get("email") or "").strip()
    first_name = (row.get("first_name") or "").strip()
    last_name = (row.get("last_name") or "").strip()
    school_id_raw = (row.get("school_id") or "").strip()
    is_active = _parse_bool(row.get("is_active"), default=True)

    if not username:
        errors.append("username is required")
    if role and role not in _role_values():
        errors.append("invalid role")
    if not role:
        errors.append("role is required")
    school_id = None
    if school_id_raw:
        if not school_id_raw.isdigit():
            errors.append("school_id must be a number")
        else:
            school_id = int(school_id_raw)
            if school_id not in schools_by_id:
                errors.append("school_id not found")

    payload = {
        "username": username,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "role": role,
        "school_id": school_id,
        "is_active": is_active,
    }
    return payload, errors


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_list(request):
    users = User.objects.select_related("school").all().order_by("username")
    schools = School.objects.filter(is_active=True).order_by("name")

    role = (request.GET.get("role") or "").strip()
    school_id = (request.GET.get("school_id") or "").strip()
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    page = request.GET.get("page") or "1"
    page_size = request.GET.get("page_size") or "25"

    if role:
        users = users.filter(role=role)
    if school_id:
        users = users.filter(school_id=school_id)
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    try:
        page_size_int = max(10, min(100, int(page_size)))
    except ValueError:
        page_size_int = 25

    paginator = Paginator(users, page_size_int)
    page_obj = paginator.get_page(page)

    context = build_layout_context(request.user, current_section="users")
    context.update(
        {
            "users": page_obj.object_list,
            "page_obj": page_obj,
            "page_size": page_size_int,
            "schools": schools,
            **_role_context(),
            "filters": {"role": role, "school_id": school_id, "q": query, "status": status},
        }
    )
    return render(request, "users/list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_import(request):
    if request.method == "POST":
        ip = (request.META.get("REMOTE_ADDR") or "")[:64]
        if throttle_hit(
            f"throttle:users_import:uid:{request.user.id}:ip:{ip}",
            limit=int(getattr(settings, "THROTTLE_USERS_IMPORT_PER_15M", 20)),
            window_seconds=15 * 60,
        ):
            messages.error(request, "Too many import attempts. Please wait a few minutes and try again.")
            return redirect("/users/import/")

        stage = (request.POST.get("stage") or "preview").strip().lower()
        if stage == "confirm":
            preview = request.session.get(USER_IMPORT_SESSION_KEY) or {}
            rows = preview.get("rows") or []
            if not rows:
                messages.error(request, "Import preview expired. Please upload the file again.")
                return redirect("/users/import/")

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

                username = payload.get("username") or ""
                defaults = {
                    "email": payload.get("email") or "",
                    "first_name": payload.get("first_name") or "",
                    "last_name": payload.get("last_name") or "",
                    "role": payload.get("role") or "",
                    "school_id": payload.get("school_id"),
                    "is_active": bool(payload.get("is_active", True)),
                }

                user_obj = User.objects.filter(username=username).only("id").first()
                if user_obj:
                    User.objects.filter(id=user_obj.id).update(**defaults)
                    updated += 1
                else:
                    user_obj = User.objects.create(**defaults)
                    user_obj.set_unusable_password()
                    user_obj.save(update_fields=["password"])
                    created += 1

            request.session[USER_IMPORT_SESSION_KEY] = {"errors": errors_out}
            parts = []
            if created:
                parts.append(f"{created} created")
            if updated:
                parts.append(f"{updated} updated")
            if skipped:
                parts.append(f"{skipped} skipped")
            if parts:
                messages.success(request, "Users import summary: " + ", ".join(parts) + ".")
            else:
                messages.info(request, "No rows were imported.")

            try:
                ActivityLog.objects.create(
                    actor=request.user,
                    school_id=getattr(request.user, "school_id", None),
                    view_name="users.import",
                    action="users.import",
                    method="POST",
                    path="/users/import/",
                    status_code=200,
                    ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                    user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
                    message=f"SuperAdmin users import: created={created}, updated={updated}, skipped={skipped}",
                )
            except Exception:
                pass

            return redirect("/users/import/")

        import_file = request.FILES.get("import_file")
        if not import_file:
            messages.error(request, "Choose a CSV file to import.")
            return redirect("/users/import/")
        extension = import_file.name.lower().rsplit(".", 1)[-1]
        if extension not in {"csv", "xlsx"}:
            messages.error(request, "Only CSV and XLSX are supported for Users import right now.")
            return redirect("/users/import/")

        schools = list(School.objects.all().only("id", "name"))
        schools_by_id = {s.id: s for s in schools}

        try:
            if extension == "csv":
                raw_rows = _read_csv_upload(import_file)
            else:
                raw_rows = _read_xlsx_upload(import_file)
        except Exception:
            messages.error(request, "We could not read that file. Please check headers and try again.")
            return redirect("/users/import/")

        preview_rows: list[dict] = []
        invalid_count = 0
        for idx, raw in enumerate(raw_rows[:5000], start=1):
            payload, row_errors = _validate_user_import_row(raw, schools_by_id=schools_by_id)
            if row_errors:
                invalid_count += 1
            preview_rows.append(
                {
                    "row_index": idx,
                    "raw": raw,
                    "cells": [raw.get(h, "") for h in USER_IMPORT_HEADERS],
                    "payload": payload,
                    "errors": row_errors,
                }
            )

        request.session[USER_IMPORT_SESSION_KEY] = {"rows": preview_rows, "errors": []}

        context = build_layout_context(request.user, current_section="users")
        context.update(
            {
                "headers": USER_IMPORT_HEADERS,
                "preview_rows": preview_rows[:50],
                "total_rows": len(preview_rows),
                "invalid_count": invalid_count,
                "schools": School.objects.filter(is_active=True).order_by("name"),
                **_role_context(),
            }
        )
        return render(request, "users/import_preview.html", context)

    context = build_layout_context(request.user, current_section="users")
    context.update({"headers": USER_IMPORT_HEADERS})
    return render(request, "users/import.html", context)


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_import_errors_csv(request):
    preview = request.session.get(USER_IMPORT_SESSION_KEY) or {}
    errors_out = preview.get("errors") or []
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users_import_errors.csv"'
    writer = csv.writer(response)
    writer.writerow(["row", "errors", *USER_IMPORT_HEADERS])
    for item in errors_out[:20000]:
        writer.writerow(
            [
                item.get("row") or "",
                _sanitize_csv_cell(item.get("errors") or ""),
                _sanitize_csv_cell(item.get("username") or ""),
                _sanitize_csv_cell(item.get("email") or ""),
                _sanitize_csv_cell(item.get("first_name") or ""),
                _sanitize_csv_cell(item.get("last_name") or ""),
                _sanitize_csv_cell(item.get("role") or ""),
                _sanitize_csv_cell(item.get("school_id") or ""),
                _sanitize_csv_cell(item.get("is_active") or ""),
            ]
        )
    return response


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_import_sample(request, file_type):
    if file_type != "csv":
        messages.error(request, "Unsupported sample file type.")
        return redirect("/users/import/")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users-import-sample.csv"'
    writer = csv.writer(response)
    writer.writerow(USER_IMPORT_HEADERS)
    writer.writerow(["teacher_1", "teacher1@example.com", "Amit", "Sharma", "TEACHER", "1", "yes"])
    writer.writerow(["accountant_1", "accounts@example.com", "Neha", "Verma", "ACCOUNTANT", "1", "yes"])
    return response


def _parse_id_list(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return sorted(set(ids))


def _role_values() -> set[str]:
    return {value for value, _ in User.ROLE_CHOICES}


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_bulk_action(request):
    if request.method != "POST":
        messages.error(request, "Invalid bulk action request.")
        return redirect("/users/")

    action = (request.POST.get("action") or "").strip().lower()
    raw_ids = (request.POST.get("user_ids") or request.POST.get("ids") or "").strip()
    ids = _parse_id_list(raw_ids)
    if not ids:
        messages.error(request, "Select at least one user.")
        return redirect("/users/")

    users_qs = User.objects.select_related("school").filter(id__in=ids).order_by("id")
    total = users_qs.count()
    if total == 0:
        messages.error(request, "No valid users selected.")
        return redirect("/users/")

    # Prevent foot-guns: never allow changing your own account via bulk.
    users_qs = users_qs.exclude(id=request.user.id)
    affected = users_qs.count()
    if affected == 0:
        messages.error(request, "Bulk action cannot be applied to your own account.")
        return redirect("/users/")

    role = (request.POST.get("role") or "").strip()
    school_id = (request.POST.get("school_id") or "").strip()

    summary = {"action": action, "requested": total, "affected": affected, "user_ids": ids[:200]}

    if action == "activate":
        changed = users_qs.update(is_active=True)
        summary["changed"] = changed
        messages.success(request, f"Activated {changed} user(s).")
    elif action == "deactivate":
        changed = users_qs.update(is_active=False)
        summary["changed"] = changed
        messages.success(request, f"Deactivated {changed} user(s).")
    elif action == "change_role":
        if role not in _role_values():
            messages.error(request, "Invalid role selected.")
            return redirect("/users/")
        changed = users_qs.update(role=role)
        summary.update({"role": role, "changed": changed})
        messages.success(request, f"Updated role for {changed} user(s) to {role}.")
    elif action == "assign_school":
        if not school_id.isdigit():
            messages.error(request, "Invalid school selected.")
            return redirect("/users/")
        school = School.objects.filter(id=int(school_id)).first()
        if not school:
            messages.error(request, "School not found.")
            return redirect("/users/")
        changed = users_qs.update(school=school)
        summary.update({"school_id": school.id, "school_name": school.name, "changed": changed})
        messages.success(request, f"Assigned {changed} user(s) to {school.name}.")
    else:
        messages.error(request, "Invalid bulk action.")
        return redirect("/users/")

    try:
        ActivityLog.objects.create(
            actor=request.user,
            school_id=getattr(request.user, "school_id", None),
            view_name="users.bulk_action",
            action="users.bulk_action",
            method="POST",
            path="/users/bulk-action/",
            status_code=200,
            ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
            message=f"SuperAdmin bulk users action: {summary}",
        )
    except Exception:
        pass

    return redirect("/users/")


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_export_csv(request):
    users = User.objects.select_related("school").all().order_by("username")

    role = (request.GET.get("role") or "").strip()
    school_id = (request.GET.get("school_id") or "").strip()
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if role:
        users = users.filter(role=role)
    if school_id:
        users = users.filter(school_id=school_id)
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    raw_ids = (request.GET.get("user_ids") or request.GET.get("ids") or "").strip()
    if raw_ids:
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if ids:
            users = users.filter(id__in=sorted(set(ids)))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users.csv"'

    writer = csv.writer(response)
    writer.writerow(["username", "email", "first_name", "last_name", "role", "school", "is_active"])
    for user in users:
        writer.writerow(
            [
                user.username,
                user.email or "",
                user.first_name or "",
                user.last_name or "",
                user.role,
                user.school.name if user.school else "",
                "yes" if user.is_active else "no",
            ]
        )

    return response


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_export_excel(request):
    users = User.objects.select_related("school").all().order_by("username")

    role = (request.GET.get("role") or "").strip()
    school_id = (request.GET.get("school_id") or "").strip()
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if role:
        users = users.filter(role=role)
    if school_id:
        users = users.filter(school_id=school_id)
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    raw_ids = (request.GET.get("user_ids") or request.GET.get("ids") or "").strip()
    if raw_ids:
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if ids:
            users = users.filter(id__in=sorted(set(ids)))

    # No extra deps: send an Excel-friendly HTML table as .xls
    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="users.xls"'

    def esc(value):
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    rows = [
        "<table>",
        "<thead><tr>"
        "<th>username</th><th>email</th><th>first_name</th><th>last_name</th><th>role</th><th>school</th><th>is_active</th>"
        "</tr></thead>",
        "<tbody>",
    ]
    for user in users:
        rows.append(
            "<tr>"
            f"<td>{esc(user.username)}</td>"
            f"<td>{esc(user.email)}</td>"
            f"<td>{esc(user.first_name)}</td>"
            f"<td>{esc(user.last_name)}</td>"
            f"<td>{esc(user.role)}</td>"
            f"<td>{esc(user.school.name if user.school else '')}</td>"
            f"<td>{'yes' if user.is_active else 'no'}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")

    response.write("".join(rows))
    return response


def _user_payload_from_request(request):
    return {
        "username": (request.POST.get("username") or "").strip(),
        "email": (request.POST.get("email") or "").strip(),
        "first_name": (request.POST.get("first_name") or "").strip(),
        "last_name": (request.POST.get("last_name") or "").strip(),
        "role": request.POST.get("role"),
        "school_id": request.POST.get("school_id") or None,
        "is_active": request.POST.get("is_active") == "on",
    }


def _validate_user_payload(payload):
    role = payload.get("role")
    school_id = payload.get("school_id")

    if role and role != "SUPER_ADMIN" and not school_id:
        return "School is required for non-Super Admin users."

    if role not in _role_values():
        return "Invalid role selected."

    if role == "SUPER_ADMIN" and school_id:
        return "Super Admin cannot be scoped to a school."

    return None


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_create(request):
    schools = School.objects.filter(is_active=True).order_by("name")
    if request.method == "POST":
        payload = _user_payload_from_request(request)
        password = request.POST.get("password") or ""

        if not payload["username"] or not payload["role"]:
            messages.error(request, "Username and role are required.")
        elif _validate_user_payload(payload):
            messages.error(request, _validate_user_payload(payload))
        elif User.objects.filter(username=payload["username"]).exists():
            messages.error(request, "That username already exists.")
        elif not password:
            messages.error(request, "Password is required.")
        else:
            user = User.objects.create(**payload)
            try:
                validate_password(password, user)
            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
                user.delete()
                context = build_layout_context(request.user, current_section="users")
                context.update({"schools": schools, **_role_context()})
                return render(request, "users/create.html", context)

            user.set_password(password)
            user.save(update_fields=["password"])
            messages.success(request, "User created successfully.")
            return redirect("/users/")

    context = build_layout_context(request.user, current_section="users")
    context.update({"schools": schools, **_role_context()})
    return render(request, "users/create.html", context)


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_update(request, id):
    user_obj = get_object_or_404(User, id=id)
    schools = School.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        payload = _user_payload_from_request(request)

        if not payload["username"] or not payload["role"]:
            messages.error(request, "Username and role are required.")
        elif _validate_user_payload(payload):
            messages.error(request, _validate_user_payload(payload))
        elif User.objects.filter(username=payload["username"]).exclude(id=user_obj.id).exists():
            messages.error(request, "That username already exists.")
        else:
            for field, value in payload.items():
                setattr(user_obj, field, value)
            user_obj.save()
            messages.success(request, "User updated successfully.")
            return redirect("/users/")

    context = build_layout_context(request.user, current_section="users")
    context.update({"user_obj": user_obj, "schools": schools, **_role_context()})
    return render(request, "users/edit.html", context)


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_reset_password(request, id):
    user_obj = get_object_or_404(User, id=id)

    if request.method != "POST":
        messages.error(request, "Invalid password reset request.")
        return redirect("/users/")

    password = (request.POST.get("password") or "").strip()
    if not password:
        messages.error(request, "Password is required.")
        return redirect("/users/")

    try:
        validate_password(password, user_obj)
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
        return redirect("/users/")

    user_obj.set_password(password)
    user_obj.save(update_fields=["password"])
    messages.success(request, f"Password reset for {user_obj.username}.")
    return redirect("/users/")


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_impersonate_start(request, id):
    if request.method != "POST":
        messages.error(request, "Invalid impersonation request.")
        return redirect("/users/")

    target = get_object_or_404(User, id=id)
    if target.id == request.user.id:
        messages.info(request, "You are already logged in as that user.")
        return redirect("/users/")

    if request.session.get(IMPERSONATE_SESSION_KEY):
        messages.error(request, "Stop current impersonation before starting a new one.")
        return redirect("/users/")

    original_user_id = request.user.id
    login(request, target, backend="django.contrib.auth.backends.ModelBackend")
    # `login()` rotates the session, so set the marker after login.
    request.session[IMPERSONATE_SESSION_KEY] = original_user_id
    try:
        ActivityLog.objects.create(
            actor=target,
            school_id=getattr(target, "school_id", None),
            view_name="users.impersonate_start",
            action="users.impersonate_start",
            method="POST",
            path=f"/users/{target.id}/impersonate/",
            status_code=200,
            ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
            message=f"Impersonation started by SUPER_ADMIN id={original_user_id} into user id={target.id} ({target.username})",
        )
    except Exception:
        pass

    messages.success(request, f"Impersonating {target.username}.")
    return redirect("/dashboard/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "STUDENT", "PARENT", "ACCOUNTANT", "RECEPTIONIST")
def user_impersonate_stop(request):
    if request.method != "POST":
        messages.error(request, "Invalid stop request.")
        return redirect("/dashboard/")

    original_user_id = request.session.get(IMPERSONATE_SESSION_KEY)
    if not original_user_id:
        messages.info(request, "No impersonation session active.")
        return redirect("/dashboard/")

    original = User.objects.filter(id=original_user_id).first()
    if not original:
        request.session.pop(IMPERSONATE_SESSION_KEY, None)
        messages.error(request, "Original user no longer exists.")
        return redirect("/login/")

    request.session.pop(IMPERSONATE_SESSION_KEY, None)
    login(request, original, backend="django.contrib.auth.backends.ModelBackend")
    try:
        ActivityLog.objects.create(
            actor=original,
            school_id=getattr(original, "school_id", None),
            view_name="users.impersonate_stop",
            action="users.impersonate_stop",
            method="POST",
            path="/users/impersonate/stop/",
            status_code=200,
            ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
            message=f"Impersonation stopped; returned to SUPER_ADMIN id={original.id} ({original.username})",
        )
    except Exception:
        pass

    messages.success(request, "Returned to Super Admin.")
    return redirect("/users/")


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_deactivate(request, id):
    user_obj = get_object_or_404(User, id=id)

    if request.method != "POST":
        messages.error(request, "Invalid deactivate request.")
        return redirect("/users/")

    if user_obj.id == request.user.id:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("/users/")

    user_obj.is_active = False
    user_obj.save(update_fields=["is_active"])
    messages.success(request, f"Deactivated {user_obj.username}.")
    return redirect("/users/")


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def invitation_list(request):
    invitations = UserInvitation.objects.select_related("user", "user__school", "created_by").all()
    context = build_layout_context(request.user, current_section="users")
    context["invitations"] = invitations
    return render(request, "users/invitations.html", context)


def _send_invitation_email(request, invitation, recipient_email):
    user = invitation.user
    activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
    subject = "Activate your School ERP account"

    context = {"user": user, "activation_url": activation_url}
    text_body = render_to_string("emails/invitation.txt", context)
    html_body = render_to_string("emails/invitation.html", context)

    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[recipient_email])
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    return activation_url


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_invite(request):
    schools = School.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        ip = (request.META.get("REMOTE_ADDR") or "")[:64]
        if throttle_hit(
            f"throttle:user_invite:uid:{request.user.id}:ip:{ip}",
            limit=int(getattr(settings, "THROTTLE_USER_INVITES_PER_15M", 30)),
            window_seconds=15 * 60,
        ):
            messages.error(request, "Too many invitations. Please wait a few minutes and try again.")
            return redirect("/users/invite/")

        payload = _user_payload_from_request(request)
        payload["is_active"] = False

        validation_error = _validate_user_payload(payload)
        if not payload["username"] or not payload["role"]:
            messages.error(request, "Username and role are required.")
        elif validation_error:
            messages.error(request, validation_error)
        elif User.objects.filter(username=payload["username"]).exists():
            messages.error(request, "That username already exists.")
        else:
            user = User.objects.create(**payload)
            user.set_unusable_password()
            user.save(update_fields=["password"])

            expires_at = timezone.now() + timedelta(days=7)
            invitation = UserInvitation.objects.create(user=user, created_by=request.user, expires_at=expires_at)

            if payload.get("email"):
                try:
                    activation_url = _send_invitation_email(request, invitation, payload["email"])
                    invitation.sent_to = payload["email"]
                    invitation.sent_at = timezone.now()
                    invitation.send_error = ""
                    invitation.save(update_fields=["sent_to", "sent_at", "send_error"])
                    messages.success(request, f"Invitation created and emailed to {payload['email']}.")
                except Exception as exc:
                    activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
                    invitation.sent_to = payload["email"]
                    invitation.sent_at = None
                    invitation.send_error = str(exc)
                    invitation.save(update_fields=["sent_to", "sent_at", "send_error"])
                    messages.warning(request, f"Invitation created but email could not be sent. Activation link: {activation_url}")
            else:
                activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
                messages.success(request, f"Invitation created. Activation link: {activation_url}")
            return redirect("/users/invitations/")

    context = build_layout_context(request.user, current_section="users")
    context.update({"schools": schools, **_role_context()})
    return render(request, "users/invite.html", context)


@role_required("SUPER_ADMIN")
@permission_required("users.manage")
def user_resend_invitation(request, id):
    invitation = get_object_or_404(UserInvitation.objects.select_related("user"), id=id)

    if request.method != "POST":
        messages.error(request, "Invalid resend request.")
        return redirect("/users/invitations/")

    ip = (request.META.get("REMOTE_ADDR") or "")[:64]
    if throttle_hit(
        f"throttle:user_invite_resend:uid:{request.user.id}:ip:{ip}",
        limit=int(getattr(settings, "THROTTLE_USER_INVITE_RESENDS_PER_15M", 60)),
        window_seconds=15 * 60,
    ):
        messages.error(request, "Too many resend attempts. Please wait a few minutes and try again.")
        return redirect("/users/invitations/")

    if invitation.is_accepted():
        messages.info(request, "This invitation was already accepted.")
        return redirect("/users/invitations/")

    recipient_email = (invitation.sent_to or invitation.user.email or "").strip()
    if not recipient_email:
        messages.error(request, "No email is available for this invitation/user.")
        return redirect("/users/invitations/")

    invitation.token = uuid.uuid4()
    invitation.expires_at = timezone.now() + timedelta(days=7)
    invitation.sent_at = None
    invitation.sent_to = recipient_email
    invitation.send_error = ""
    invitation.save(update_fields=["token", "expires_at", "sent_at", "sent_to", "send_error"])

    try:
        _send_invitation_email(request, invitation, recipient_email)
        invitation.sent_at = timezone.now()
        invitation.save(update_fields=["sent_at"])
        messages.success(request, f"Invitation resent to {recipient_email}.")
    except Exception as exc:
        invitation.send_error = str(exc)
        invitation.save(update_fields=["send_error"])
        activation_url = request.build_absolute_uri(f"/activate/{invitation.token}/")
        messages.warning(request, f"Resend failed. Activation link: {activation_url}")

    return redirect("/users/invitations/")
