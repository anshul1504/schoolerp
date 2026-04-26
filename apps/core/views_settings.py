from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings

from apps.core.ui import build_layout_context
from apps.core.permissions import permission_required, role_required
from apps.core.models import PlatformSettings, RBACChangeEvent, RolePermissionsOverride
from apps.core.models import RoleSectionsOverride
from apps.core.models import TwoFactorPolicy
from apps.core.models import EntityChangeLog
from apps.accounts.models import User
from apps.accounts.roles import grouped_role_choices
from apps.core.ui import BASE_NAVIGATION
from apps.core.permissions import DEFAULT_PERMISSIONS
from apps.core.models import ActivityLog
from apps.core.upload_validation import DEFAULT_IMAGE_POLICY, UploadPolicy, validate_upload


def _normalize_hex_color(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith("#"):
        value = f"#{value}"
    if len(value) != 7:
        return ""
    allowed = set("0123456789abcdefABCDEF")
    if any(ch not in allowed for ch in value[1:]):
        return ""
    return value


def _role_selection_context():
    roles = [value for value, _ in User.ROLE_CHOICES]
    return {
        "roles": roles,
        "role_labels": dict(User.ROLE_CHOICES),
        "grouped_role_choices": grouped_role_choices(User.ROLE_CHOICES),
    }


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_index(request):
    context = build_layout_context(request.user, current_section="settings")
    return render(request, "settings/index.html", context)


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_branding(request):
    settings_obj = PlatformSettings.objects.first() or PlatformSettings.objects.create()

    if request.method == "POST":
        settings_obj.product_name = (request.POST.get("product_name") or "").strip() or "SchoolFlow"
        settings_obj.product_meta = (request.POST.get("product_meta") or "").strip() or "A product by The Webfix"
        settings_obj.support_email = (request.POST.get("support_email") or "").strip()
        logo = request.FILES.get("logo")
        if logo:
            policy = UploadPolicy(
                max_bytes=int(getattr(settings, "MAX_PLATFORM_LOGO_BYTES", DEFAULT_IMAGE_POLICY.max_bytes)),
                allowed_extensions=DEFAULT_IMAGE_POLICY.allowed_extensions,
                allowed_image_formats=DEFAULT_IMAGE_POLICY.allowed_image_formats,
            )
            errors = validate_upload(logo, policy=policy, kind="Logo")
            if errors:
                for e in errors[:2]:
                    messages.error(request, e)
                return redirect("/settings/branding/")
            settings_obj.logo = logo

        favicon = request.FILES.get("favicon")
        if favicon:
            policy = UploadPolicy(
                max_bytes=int(getattr(settings, "MAX_PLATFORM_FAVICON_BYTES", 512 * 1024)),
                allowed_extensions={".png", ".jpg", ".jpeg", ".ico"},
                allowed_image_formats={"PNG", "JPEG", "ICO"},
            )
            errors = validate_upload(favicon, policy=policy, kind="Favicon")
            if errors:
                for e in errors[:2]:
                    messages.error(request, e)
                return redirect("/settings/branding/")
            settings_obj.favicon = favicon

        theme_primary = _normalize_hex_color(request.POST.get("theme_primary") or "")
        theme_secondary = _normalize_hex_color(request.POST.get("theme_secondary") or "")
        if (request.POST.get("theme_primary") or "").strip() and not theme_primary:
            messages.error(request, "Theme primary must be a valid hex color like #1677ff.")
            return redirect("/settings/branding/")
        if (request.POST.get("theme_secondary") or "").strip() and not theme_secondary:
            messages.error(request, "Theme secondary must be a valid hex color like #44b8ff.")
            return redirect("/settings/branding/")

        settings_obj.theme_primary = theme_primary
        settings_obj.theme_secondary = theme_secondary
        settings_obj.save()
        messages.success(request, "Branding updated.")
        return redirect("/settings/branding/")

    context = build_layout_context(request.user, current_section="settings")
    context["branding"] = settings_obj
    return render(request, "settings/branding.html", context)


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_role_matrix(request):
    roles = [value for value, _ in User.ROLE_CHOICES]
    nav_keys = [item["key"] for item in BASE_NAVIGATION]
    nav_labels = {item["key"]: item["label"] for item in BASE_NAVIGATION}

    if request.method == "POST":
        role = (request.POST.get("role") or "").strip()
        selected = request.POST.getlist("sections")
        selected = [key for key in selected if key in nav_keys]

        if role not in roles:
            messages.error(request, "Invalid role.")
            return redirect("/settings/role-matrix/")
        if role == "SUPER_ADMIN" and not selected:
            messages.error(request, "SUPER_ADMIN must have at least one section.")
            return redirect("/settings/role-matrix/?role=SUPER_ADMIN")

        before_obj = RoleSectionsOverride.objects.filter(role=role).first()
        before = {"sections": list(getattr(before_obj, "sections", []) or [])} if before_obj else {}

        RoleSectionsOverride.objects.update_or_create(role=role, defaults={"sections": selected})

        try:
            RBACChangeEvent.objects.create(
                actor=request.user,
                kind="ROLE_SECTIONS_OVERRIDE",
                role=role,
                before=before,
                after={"sections": selected},
                ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
            )
        except Exception:
            pass
        try:
            ActivityLog.objects.create(
                actor=request.user,
                school_id=getattr(request.user, "school_id", None),
                view_name="settings.role_matrix",
                action="settings.role_matrix.update",
                method="POST",
                path="/settings/role-matrix/",
                status_code=200,
                ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
                message=f"RoleSectionsOverride updated for {role}: {len(selected)} sections",
            )
        except Exception:
            pass
        messages.success(request, f"Role matrix updated for {role}.")
        return redirect(f"/settings/role-matrix/?role={role}")

    current_role = (request.GET.get("role") or "SUPER_ADMIN").strip()
    override = RoleSectionsOverride.objects.filter(role=current_role).first()
    selected_sections = set(override.sections) if override else set()

    context = build_layout_context(request.user, current_section="settings")
    context.update(
        {
            **_role_selection_context(),
            "current_role": current_role,
            "current_role_label": dict(User.ROLE_CHOICES).get(current_role, current_role),
            "nav_items": [{"key": key, "label": nav_labels[key]} for key in nav_keys],
            "selected_sections": selected_sections,
        }
    )
    return render(request, "settings/role_matrix.html", context)


PERMISSION_CATALOG = [
    ("schools.view", "Schools: View"),
    ("schools.manage", "Schools: Create/Edit/Delete"),
    ("schools.comm_settings", "Schools: Communication Settings (SMTP/WhatsApp)"),
    ("users.manage", "Users & Roles: Manage"),
    ("billing.manage", "Billing: Manage plans/invoices"),
    ("billing.view", "Billing: View"),
    ("students.view", "Students: View"),
    ("students.manage", "Students: Create/Edit/Delete/Import"),
    ("admissions.view", "Admissions: View"),
    ("admissions.manage", "Admissions: Manage"),
    ("academics.view", "Academics: View"),
    ("academics.manage", "Academics: Manage"),
    ("attendance.view", "Attendance: View"),
    ("attendance.manage", "Attendance: Manage"),
    ("fees.view", "Fees: View"),
    ("fees.manage", "Fees: Manage"),
    ("exams.view", "Exams: View"),
    ("exams.manage", "Exams: Manage"),
    ("communication.view", "Communication: View"),
    ("communication.manage", "Communication: Manage"),
    ("frontoffice.view", "Front Office: View"),
    ("frontoffice.manage", "Front Office: Manage"),
    ("staff.view", "Staff: View"),
    ("staff.manage", "Staff: Manage"),
    ("transport.view", "Transport: View"),
    ("transport.manage", "Transport: Manage"),
    ("hostel.view", "Hostel: View"),
    ("hostel.manage", "Hostel: Manage"),
    ("library.view", "Library: View"),
    ("library.manage", "Library: Manage"),
    ("inventory.view", "Inventory: View"),
    ("inventory.manage", "Inventory: Manage"),
    ("api.manage", "API / Integrations: Manage"),
    ("reports.view", "Reports: View"),
    ("settings.manage", "Settings: Manage"),
    ("activity.view", "Activity Log: View"),
    ("platform.view", "Platform: View"),
]


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_permissions_matrix(request):
    roles = [value for value, _ in User.ROLE_CHOICES]

    if request.method == "POST":
        role = (request.POST.get("role") or "").strip()
        selected = request.POST.getlist("permissions")
        selected = [p for p, _ in PERMISSION_CATALOG if p in selected]

        if role not in roles:
            messages.error(request, "Invalid role.")
            return redirect("/settings/permissions/")
        if role == "SUPER_ADMIN" and "settings.manage" not in selected:
            messages.error(request, "Refusing to remove settings.manage from SUPER_ADMIN.")
            return redirect("/settings/permissions/?role=SUPER_ADMIN")

        before_obj = RolePermissionsOverride.objects.filter(role=role).first()
        before = {"permissions": list(getattr(before_obj, "permissions", []) or [])} if before_obj else {}

        RolePermissionsOverride.objects.update_or_create(role=role, defaults={"permissions": selected})

        try:
            RBACChangeEvent.objects.create(
                actor=request.user,
                kind="ROLE_PERMISSIONS_OVERRIDE",
                role=role,
                before=before,
                after={"permissions": selected},
                ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
            )
        except Exception:
            pass
        try:
            ActivityLog.objects.create(
                actor=request.user,
                school_id=getattr(request.user, "school_id", None),
                view_name="settings.permissions_matrix",
                action="settings.permissions_matrix.update",
                method="POST",
                path="/settings/permissions/",
                status_code=200,
                ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
                message=f"RolePermissionsOverride updated for {role}: {len(selected)} permissions",
            )
        except Exception:
            pass
        messages.success(request, f"Permissions updated for {role}.")
        return redirect(f"/settings/permissions/?role={role}")

    current_role = (request.GET.get("role") or "SCHOOL_OWNER").strip()
    override = RolePermissionsOverride.objects.filter(role=current_role).first()
    default_permissions = set(DEFAULT_PERMISSIONS.get(current_role, set()))
    if override:
        selected_permissions = set(override.permissions)
        using_defaults = False
    else:
        selected_permissions = set(default_permissions)
        using_defaults = True

    added_permissions = sorted(selected_permissions - default_permissions)
    removed_permissions = sorted(default_permissions - selected_permissions)
    matched_permissions = sorted(selected_permissions & default_permissions)
    permission_labels = {code: label for code, label in PERMISSION_CATALOG}
    added_permission_labels = [permission_labels.get(code, code) for code in added_permissions]
    removed_permission_labels = [permission_labels.get(code, code) for code in removed_permissions]

    context = build_layout_context(request.user, current_section="settings")
    context.update(
        {
            **_role_selection_context(),
            "current_role": current_role,
            "current_role_label": dict(User.ROLE_CHOICES).get(current_role, current_role),
            "catalog": PERMISSION_CATALOG,
            "selected_permissions": selected_permissions,
            "using_defaults": using_defaults,
            "default_permissions": default_permissions,
            "matched_permissions": matched_permissions,
            "added_permissions": added_permissions,
            "removed_permissions": removed_permissions,
            "added_permission_labels": added_permission_labels,
            "removed_permission_labels": removed_permission_labels,
            "permission_labels": permission_labels,
        }
    )
    return render(request, "settings/permissions_matrix.html", context)


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_email_test(request):
    if request.method == "POST":
        to_email = (request.POST.get("to_email") or "").strip()
        if not to_email:
            messages.error(request, "Recipient email is required.")
            return redirect("/settings/email-test/")

        subject = "School ERP SMTP Test"
        text_body = "This is a test email from School ERP."
        html_body = render_to_string("settings/email_test_email.html", {"to_email": to_email})

        try:
            msg = EmailMultiAlternatives(subject=subject, body=text_body, to=[to_email])
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)
            messages.success(request, f"Test email sent to {to_email}.")
        except Exception as exc:
            messages.error(request, f"Email send failed: {exc}")

        return redirect("/settings/email-test/")

    context = build_layout_context(request.user, current_section="settings")
    return render(request, "settings/email_test.html", context)


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_rbac_audit(request):
    role = (request.GET.get("role") or "").strip()
    kind = (request.GET.get("kind") or "").strip()

    events = RBACChangeEvent.objects.select_related("actor").all()
    if role:
        events = events.filter(role__iexact=role)
    if kind in {"ROLE_SECTIONS_OVERRIDE", "ROLE_PERMISSIONS_OVERRIDE"}:
        events = events.filter(kind=kind)

    context = build_layout_context(request.user, current_section="settings")
    context.update(
        {
            "events": events[:200],
            "filters": {"role": role, "kind": kind},
            "kind_choices": RBACChangeEvent.KIND_CHOICES,
        }
    )
    return render(request, "settings/rbac_audit.html", context)


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_two_factor_policy(request):
    policy = TwoFactorPolicy.objects.first() or TwoFactorPolicy.objects.create()
    roles = [value for value, _ in User.ROLE_CHOICES]

    if request.method == "POST":
        selected_roles = request.POST.getlist("roles")
        selected_roles = [r for r in selected_roles if r in roles and r != "SUPER_ADMIN"]

        raw_user_ids = (request.POST.get("user_ids") or "").strip()
        user_ids: list[int] = []
        if raw_user_ids:
            for part in raw_user_ids.split(","):
                part = part.strip()
                if part.isdigit():
                    user_ids.append(int(part))
        user_ids = sorted(set(user_ids))

        policy.require_for_roles = selected_roles
        policy.require_for_user_ids = user_ids
        policy.save(update_fields=["require_for_roles", "require_for_user_ids", "updated_at"])
        messages.success(request, "2FA policy updated.")
        return redirect("/settings/2fa/")

    context = build_layout_context(request.user, current_section="settings")
    context.update({"policy": policy, **_role_selection_context()})
    return render(request, "settings/two_factor_policy.html", context)


@role_required("SUPER_ADMIN")
@permission_required("settings.manage")
def settings_rbac_user_grants(request):
    """
    Shows "who granted what" at the user level (role / school assignment changes).

    Backed by EntityChangeLog on accounts.User.
    """

    q = (request.GET.get("q") or "").strip()
    logs = EntityChangeLog.objects.select_related("actor").filter(entity="accounts.User", action="UPDATED").order_by("-created_at")[:500]

    rows = []
    for log in logs:
        changes = log.changes or {}
        if "role" not in changes and "school_id" not in changes and "is_active" not in changes:
            continue
        if q:
            hay = f"{log.object_id} {changes}".lower()
            if q.lower() not in hay:
                continue
        rows.append(log)
        if len(rows) >= 200:
            break

    context = build_layout_context(request.user, current_section="settings")
    context.update({"logs": rows, "filters": {"q": q}})
    return render(request, "settings/rbac_user_grants.html", context)
