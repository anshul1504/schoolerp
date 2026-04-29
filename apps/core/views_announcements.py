from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import PlatformAnnouncement
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context


def _parse_dt(value: str):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return timezone.datetime.fromisoformat(raw)
    except Exception:
        return None


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def announcement_list(request):
    qs = PlatformAnnouncement.objects.all()
    context = build_layout_context(request.user, current_section="platform")
    context["announcements"] = qs[:200]
    return render(request, "platform/announcements_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def announcement_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        message = (request.POST.get("message") or "").strip()
        severity = (request.POST.get("severity") or "INFO").strip().upper()
        is_active = request.POST.get("is_active") == "on"
        starts_at = _parse_dt(request.POST.get("starts_at") or "")
        ends_at = _parse_dt(request.POST.get("ends_at") or "")

        if not title or not message:
            messages.error(request, "Title and message are required.")
        elif severity not in dict(PlatformAnnouncement.SEVERITY_CHOICES):
            messages.error(request, "Invalid severity.")
        else:
            PlatformAnnouncement.objects.create(
                title=title,
                message=message,
                severity=severity,
                is_active=is_active,
                starts_at=starts_at,
                ends_at=ends_at,
            )
            messages.success(request, "Announcement created.")
            return redirect("/platform/announcements/")

    context = build_layout_context(request.user, current_section="platform")
    context.update({"mode": "create", "severity_choices": PlatformAnnouncement.SEVERITY_CHOICES})
    return render(request, "platform/announcements_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def announcement_update(request, id):
    obj = get_object_or_404(PlatformAnnouncement, id=id)
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        message = (request.POST.get("message") or "").strip()
        severity = (request.POST.get("severity") or obj.severity).strip().upper()
        is_active = request.POST.get("is_active") == "on"
        starts_at = _parse_dt(request.POST.get("starts_at") or "")
        ends_at = _parse_dt(request.POST.get("ends_at") or "")

        if not title or not message:
            messages.error(request, "Title and message are required.")
        elif severity not in dict(PlatformAnnouncement.SEVERITY_CHOICES):
            messages.error(request, "Invalid severity.")
        else:
            obj.title = title
            obj.message = message
            obj.severity = severity
            obj.is_active = is_active
            obj.starts_at = starts_at
            obj.ends_at = ends_at
            obj.save()
            messages.success(request, "Announcement updated.")
            return redirect("/platform/announcements/")

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "mode": "edit",
            "announcement": obj,
            "severity_choices": PlatformAnnouncement.SEVERITY_CHOICES,
        }
    )
    return render(request, "platform/announcements_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def announcement_delete(request, id):
    obj = get_object_or_404(PlatformAnnouncement, id=id)
    if request.method != "POST":
        messages.error(request, "Invalid delete request.")
        return redirect("/platform/announcements/")
    obj.delete()
    messages.success(request, "Announcement deleted.")
    return redirect("/platform/announcements/")
