from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import UserInvitation, UserLoginOTP
from apps.core.models import ActivityLog, AuthSecurityEvent
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def platform_security(request):
    User = get_user_model()
    now = timezone.now()
    since = now - timedelta(days=1)

    users = User.objects.select_related("school").order_by("-date_joined")
    locked_users = users.filter(locked_until__isnull=False, locked_until__gt=now).order_by("-locked_until")
    risky_users = users.filter(Q(failed_login_attempts__gte=3) | Q(locked_until__isnull=False)).order_by("-failed_login_attempts", "-locked_until")

    otps = UserLoginOTP.objects.select_related("user").order_by("-created_at")
    active_otps = otps.filter(expires_at__gt=now, used_at__isnull=True).order_by("-expires_at")

    invites = UserInvitation.objects.select_related("user", "user__school").order_by("-created_at")
    pending_invites = invites.filter(accepted_at__isnull=True).order_by("-created_at")

    activity = ActivityLog.objects.select_related("actor", "school").order_by("-created_at")
    recent_auth_activity = activity.filter(path__in={"/login/", "/login/verify/"}).order_by("-created_at")

    events = AuthSecurityEvent.objects.all()
    recent_events = events.filter(created_at__gte=since).order_by("-created_at")
    recent_throttles = recent_events.filter(event="THROTTLED").count()
    recent_fails = recent_events.filter(event__in={"LOGIN_FAIL", "OTP_VERIFY_FAIL"}).count()
    recent_success = recent_events.filter(event__in={"LOGIN_SUCCESS", "OTP_VERIFY_SUCCESS"}).count()

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "kpis": {
                "locked_users": locked_users.count(),
                "risky_users": risky_users.count(),
                "pending_invites": pending_invites.count(),
                "active_otps": active_otps.count(),
                "auth_fails_24h": recent_fails,
                "auth_throttled_24h": recent_throttles,
                "auth_success_24h": recent_success,
            },
            "locked_users": locked_users[:50],
            "risky_users": risky_users[:50],
            "pending_invites": pending_invites[:50],
            "active_otps": active_otps[:50],
            "recent_auth_activity": recent_auth_activity[:30],
            "recent_auth_events": recent_events[:30],
            "now": now,
        }
    )
    return render(request, "platform/security.html", context)
