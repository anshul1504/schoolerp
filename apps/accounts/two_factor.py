from django.conf import settings

from apps.core.models import TwoFactorPolicy


def requires_email_otp(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "role", None) == "SUPER_ADMIN":
        return True

    if getattr(settings, "EMAIL_OTP_2FA_ENABLED", False):
        return True

    policy = TwoFactorPolicy.objects.first()
    if not policy:
        return False

    role = getattr(user, "role", "") or ""
    if role and role in (policy.require_for_roles or []):
        return True

    try:
        uid = int(getattr(user, "id", 0) or 0)
    except Exception:
        uid = 0
    if uid and uid in (policy.require_for_user_ids or []):
        return True

    return False
