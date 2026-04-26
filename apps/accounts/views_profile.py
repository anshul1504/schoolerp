from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.conf import settings

from apps.core.ui import build_layout_context
from apps.core.upload_validation import DEFAULT_IMAGE_POLICY, UploadPolicy, validate_upload


@login_required
def profile_view(request):
    context = build_layout_context(request.user, current_section="settings")
    return render(request, "accounts/profile.html", context)


@login_required
def profile_edit(request):
    if request.method != "POST":
        return redirect("/profile/")

    user = request.user
    user.first_name = (request.POST.get("first_name") or "").strip()
    user.last_name = (request.POST.get("last_name") or "").strip()
    user.email = (request.POST.get("email") or "").strip()

    avatar = request.FILES.get("avatar")
    if avatar:
        policy = UploadPolicy(
            max_bytes=int(getattr(settings, "MAX_USER_AVATAR_BYTES", DEFAULT_IMAGE_POLICY.max_bytes)),
            allowed_extensions=DEFAULT_IMAGE_POLICY.allowed_extensions,
            allowed_image_formats=DEFAULT_IMAGE_POLICY.allowed_image_formats,
        )
        errors = validate_upload(avatar, policy=policy, kind="Avatar")
        if errors:
            for e in errors[:2]:
                messages.error(request, e)
            return redirect("/profile/")
        user.avatar = avatar

    password = (request.POST.get("password") or "").strip()
    if password:
        try:
            validate_password(password, user)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            return redirect("/profile/")
        user.set_password(password)

    user.save()
    messages.success(request, "Profile updated.")
    return redirect("/profile/")
