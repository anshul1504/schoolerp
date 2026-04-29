import secrets

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import IntegrationToken
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def token_list(request):
    tokens = IntegrationToken.objects.all()
    context = build_layout_context(request.user, current_section="platform")
    context["tokens"] = tokens[:200]
    return render(request, "platform/tokens_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def token_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        scopes_raw = (request.POST.get("scopes") or "").strip()
        is_active = request.POST.get("is_active") == "on"
        scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
        if not name:
            messages.error(request, "Name is required.")
        else:
            token = secrets.token_hex(32)
            IntegrationToken.objects.create(
                name=name, token=token, scopes=scopes, is_active=is_active
            )
            messages.success(request, "Token created. Copy it now (it won’t be shown again).")
            request.session["last_created_token_value"] = token
            return redirect("/platform/tokens/")

    context = build_layout_context(request.user, current_section="platform")
    return render(request, "platform/tokens_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def token_toggle(request, id):
    obj = get_object_or_404(IntegrationToken, id=id)
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("/platform/tokens/")
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, "Token updated.")
    return redirect("/platform/tokens/")
