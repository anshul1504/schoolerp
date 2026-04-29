import csv

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import has_permission, role_required
from apps.core.tenancy import school_scope_for_user, selected_school_for_request
from apps.core.ui import build_layout_context

from .models import Notice


def _school_scope(user):
    return school_scope_for_user(user)


def _selected_school(request):
    return selected_school_for_request(request)


def _audience_scope_for_role(role):
    if role in {
        "SUPER_ADMIN",
        "SCHOOL_OWNER",
        "PRINCIPAL",
        "TEACHER",
        "ACCOUNTANT",
        "RECEPTIONIST",
    }:
        return {"ALL", "STAFF"}
    if role == "STUDENT":
        return {"ALL", "STUDENTS"}
    if role == "PARENT":
        return {"ALL", "PARENTS"}
    return {"ALL"}


@role_required(
    "SUPER_ADMIN",
    "SCHOOL_OWNER",
    "PRINCIPAL",
    "TEACHER",
    "STUDENT",
    "PARENT",
    "ACCOUNTANT",
    "RECEPTIONIST",
    "ADMISSION_COUNSELOR",
    "CAREER_COUNSELOR",
)
def communication_overview(request):
    if request.method == "POST" and not has_permission(request.user, "communication.manage"):
        messages.error(request, "You do not have permission to manage communication.")
        return redirect("/communication/")

    if not has_permission(request.user, "communication.view"):
        messages.error(request, "You do not have permission to view communication.")
        return redirect("dashboard")

    school = _selected_school(request)
    if request.user.role == "SUPER_ADMIN" and school is None:
        if request.method == "POST":
            messages.error(request, "Select a school before managing communication.")
            return redirect("/communication/")
    notices = Notice.objects.select_related("school", "created_by")
    if school:
        notices = notices.filter(school=school)
    elif request.user.school_id:
        notices = notices.filter(school_id=request.user.school_id)
    else:
        notices = notices.none()

    notices = notices.filter(
        is_published=True, audience__in=_audience_scope_for_role(request.user.role)
    )

    if request.method == "POST":
        if request.user.role not in {"SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST"}:
            messages.error(request, "You do not have permission to create notices.")
            return redirect("/communication/")
        if school is None:
            messages.error(request, "Select a valid school before publishing a notice.")
            return redirect("/communication/")
        Notice.objects.create(
            school=school,
            title=request.POST.get("title", "").strip(),
            body=request.POST.get("body", "").strip(),
            audience=request.POST.get("audience", "ALL"),
            priority=request.POST.get("priority", "NORMAL"),
            is_published=request.POST.get("is_published") == "on",
            created_by=request.user,
        )
        messages.success(request, "Notice published successfully.")
        return redirect(f"/communication/?school={school.id}")

    context = build_layout_context(request.user, current_section="communication")
    context["school_options"] = _school_scope(request.user)
    context["selected_school"] = school
    context["notices"] = notices[:12]
    context["notice_audience_choices"] = [choice[0] for choice in Notice.AUDIENCE_CHOICES]
    context["notice_priority_choices"] = [choice[0] for choice in Notice.PRIORITY_CHOICES]
    context["can_manage_notices"] = request.user.role in {
        "SUPER_ADMIN",
        "SCHOOL_OWNER",
        "PRINCIPAL",
        "RECEPTIONIST",
    }
    context["can_send_as_campaign"] = has_permission(request.user, "frontoffice.manage")
    context["communication_stats"] = {
        "published": notices.count(),
        "urgent": notices.filter(priority="URGENT").count(),
        "important": notices.filter(priority="IMPORTANT").count(),
        "audience": len(_audience_scope_for_role(request.user.role)),
    }
    return render(request, "communication/overview.html", context)


@role_required(
    "SUPER_ADMIN",
    "SCHOOL_OWNER",
    "PRINCIPAL",
    "TEACHER",
    "STUDENT",
    "PARENT",
    "ACCOUNTANT",
    "RECEPTIONIST",
    "ADMISSION_COUNSELOR",
    "CAREER_COUNSELOR",
)
def notice_detail(request, notice_id):
    if not has_permission(request.user, "communication.view"):
        messages.error(request, "You do not have permission to view communication.")
        return redirect("dashboard")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    notice = get_object_or_404(
        Notice.objects.select_related("school", "created_by"),
        id=notice_id,
        school_id__in=school_ids,
        is_published=True,
        audience__in=_audience_scope_for_role(request.user.role),
    )
    context = build_layout_context(request.user, current_section="communication")
    context["notice"] = notice
    context["can_send_as_campaign"] = has_permission(request.user, "frontoffice.manage")
    return render(request, "communication/detail.html", context)


def _require_manage_access(request):
    if not has_permission(request.user, "communication.manage"):
        messages.error(request, "You do not have permission to manage notices.")
        return False
    if request.user.role not in {"SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST"}:
        messages.error(request, "You do not have permission to manage notices.")
        return False
    return True


def _sanitize_csv_cell(value) -> str:
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _esc(value) -> str:
    return (
        _sanitize_csv_cell(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _parse_ids(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
    return sorted(set(ids))


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST")
def notice_export_csv(request):
    if not _require_manage_access(request):
        return redirect("/communication/")

    school = _selected_school(request)
    if request.user.role == "SUPER_ADMIN" and school is None:
        messages.error(request, "Select a school first.")
        return redirect("/communication/manage/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    qs = Notice.objects.select_related("school", "created_by").filter(school_id__in=school_ids)
    if school:
        qs = qs.filter(school=school)
    elif request.user.school_id:
        qs = qs.filter(school_id=request.user.school_id)
    else:
        qs = qs.none()

    raw_ids = request.GET.get("notice_ids") or request.GET.get("ids") or ""
    ids = _parse_ids(raw_ids)
    if ids:
        qs = qs.filter(id__in=ids)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="notices_export.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "id",
            "school",
            "title",
            "audience",
            "priority",
            "is_published",
            "created_by",
            "created_at",
        ]
    )
    for n in qs.order_by("-created_at", "-id")[:20000]:
        creator = n.created_by.get_full_name() if n.created_by else ""
        if not creator and n.created_by:
            creator = n.created_by.username
        writer.writerow(
            [
                n.id,
                _sanitize_csv_cell(n.school.name if n.school else ""),
                _sanitize_csv_cell(n.title),
                _sanitize_csv_cell(n.audience),
                _sanitize_csv_cell(n.priority),
                _sanitize_csv_cell("yes" if n.is_published else "no"),
                _sanitize_csv_cell(creator),
                _sanitize_csv_cell(n.created_at),
            ]
        )
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST")
def notice_export_excel(request):
    if not _require_manage_access(request):
        return redirect("/communication/")

    school = _selected_school(request)
    if request.user.role == "SUPER_ADMIN" and school is None:
        messages.error(request, "Select a school first.")
        return redirect("/communication/manage/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    qs = Notice.objects.select_related("school", "created_by").filter(school_id__in=school_ids)
    if school:
        qs = qs.filter(school=school)
    elif request.user.school_id:
        qs = qs.filter(school_id=request.user.school_id)
    else:
        qs = qs.none()

    raw_ids = request.GET.get("notice_ids") or request.GET.get("ids") or ""
    ids = _parse_ids(raw_ids)
    if ids:
        qs = qs.filter(id__in=ids)

    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="notices_export.xls"'
    rows = []
    for n in qs.order_by("-created_at", "-id")[:20000]:
        creator = n.created_by.get_full_name() if n.created_by else ""
        if not creator and n.created_by:
            creator = n.created_by.username
        rows.append(
            "<tr>"
            f"<td>{_esc(n.id)}</td>"
            f"<td>{_esc(n.school.name if n.school else '')}</td>"
            f"<td>{_esc(n.title)}</td>"
            f"<td>{_esc(n.audience)}</td>"
            f"<td>{_esc(n.priority)}</td>"
            f"<td>{_esc('yes' if n.is_published else 'no')}</td>"
            f"<td>{_esc(creator)}</td>"
            f"<td>{_esc(n.created_at)}</td>"
            "</tr>"
        )
    response.write(
        "<table><thead><tr>"
        "<th>id</th><th>school</th><th>title</th><th>audience</th><th>priority</th><th>is_published</th><th>created_by</th><th>created_at</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST")
def notice_manage_list(request):
    if not _require_manage_access(request):
        return redirect("/communication/")

    school = _selected_school(request)
    if request.user.role == "SUPER_ADMIN" and school is None:
        messages.error(request, "Select a school first.")
        return redirect("/communication/")
    qs = Notice.objects.select_related("school", "created_by")
    if school:
        qs = qs.filter(school=school)
    elif request.user.school_id:
        qs = qs.filter(school_id=request.user.school_id)
    else:
        qs = qs.none()

    context = build_layout_context(request.user, current_section="communication")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "notices": qs[:200],
        }
    )
    return render(request, "communication/manage_list.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST")
def notice_create(request):
    if not _require_manage_access(request):
        return redirect("/communication/")

    if request.method == "POST":
        school = _selected_school(request)
        if school is None:
            messages.error(request, "Select a valid school first.")
            return redirect("/communication/create/")

        Notice.objects.create(
            school=school,
            title=request.POST.get("title", "").strip(),
            body=request.POST.get("body", "").strip(),
            audience=request.POST.get("audience", "ALL"),
            priority=request.POST.get("priority", "NORMAL"),
            is_published=request.POST.get("is_published") == "on",
            created_by=request.user,
        )
        messages.success(request, "Notice saved.")
        return redirect(f"/communication/manage/?school={school.id}")

    context = build_layout_context(request.user, current_section="communication")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": _selected_school(request),
            "notice_audience_choices": [choice[0] for choice in Notice.AUDIENCE_CHOICES],
            "notice_priority_choices": [choice[0] for choice in Notice.PRIORITY_CHOICES],
        }
    )
    return render(request, "communication/notice_form.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST")
def notice_update(request, notice_id):
    if not _require_manage_access(request):
        return redirect("/communication/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    notice = get_object_or_404(Notice, id=notice_id, school_id__in=school_ids)

    if request.method == "POST":
        notice.title = request.POST.get("title", notice.title).strip()
        notice.body = request.POST.get("body", notice.body).strip()
        notice.audience = request.POST.get("audience", notice.audience)
        notice.priority = request.POST.get("priority", notice.priority)
        notice.is_published = request.POST.get("is_published") == "on"
        notice.save()
        messages.success(request, "Notice updated.")
        return redirect(f"/communication/manage/?school={notice.school_id}")

    context = build_layout_context(request.user, current_section="communication")
    context.update(
        {
            "mode": "edit",
            "notice": notice,
            "school_options": _school_scope(request.user),
            "selected_school": notice.school,
            "notice_audience_choices": [choice[0] for choice in Notice.AUDIENCE_CHOICES],
            "notice_priority_choices": [choice[0] for choice in Notice.PRIORITY_CHOICES],
        }
    )
    return render(request, "communication/notice_form.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RECEPTIONIST")
def notice_delete(request, notice_id):
    if not _require_manage_access(request):
        return redirect("/communication/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    notice = get_object_or_404(Notice, id=notice_id, school_id__in=school_ids)
    if request.method == "POST":
        school_id = notice.school_id
        notice.delete()
        messages.success(request, "Notice deleted.")
        return redirect(f"/communication/manage/?school={school_id}")
    messages.error(request, "Invalid delete request.")
    return redirect(f"/communication/manage/?school={notice.school_id}")
