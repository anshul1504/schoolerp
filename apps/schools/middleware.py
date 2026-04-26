from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

from apps.schools.models import SchoolSubscription
from apps.schools.feature_access import enabled_feature_codes_for_school, required_feature_for_path
from apps.schools.models import SchoolDomain


class SubscriptionEnforcementMiddleware:
    EXEMPT_PATH_PREFIXES = (
        "/admin/",
        "/login/",
        "/logout/",
        "/activate/",
        "/password-reset/",
        "/reset/",
        "/login/verify/",
        "/billing/",
        "/users/",
        "/schools/",
        "/settings/",
        "/platform/",
        "/activity/",
        "/profile/",
        "/subscription/blocked/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Domain → school mapping (for branding and optional tenant resolution before login).
        try:
            host = (request.get_host() or "").split(":", 1)[0].strip().lower()
        except Exception:
            host = ""
        request.tenant_school = None
        if host and host not in {"localhost", "127.0.0.1"}:
            domain = SchoolDomain.objects.select_related("school").filter(domain=host, is_active=True).first()
            if domain and domain.school and domain.school.is_active:
                request.tenant_school = domain.school

        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False) and user.role != "SUPER_ADMIN":
            path = request.path or "/"
            if not any(path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES):
                if not user.school_id:
                    logout(request)
                    messages.error(request, "Your account is not linked to any school. Contact administrator.")
                    return redirect("login")

                subscription = (
                    SchoolSubscription.objects.select_related("school", "plan")
                    .filter(school_id=user.school_id)
                    .first()
                )
                if not subscription or not subscription.is_valid_access(today=timezone.now().date()):
                    messages.error(request, "Subscription is inactive or expired.")
                    return redirect("/subscription/blocked/")

                plan = getattr(subscription, "plan", None)
                if plan and getattr(plan, "max_campuses", None):
                    if subscription.school.allowed_campuses and subscription.school.allowed_campuses > plan.max_campuses:
                        messages.error(request, "Your plan campus limit is exceeded. Please upgrade your subscription plan.")
                        return redirect("/subscription/blocked/?reason=campus_limit")

                required = required_feature_for_path(path)
                if required:
                    enabled = enabled_feature_codes_for_school(user.school_id)
                    if required not in enabled:
                        messages.error(request, "This module is not enabled for your subscription plan.")
                        return redirect("/subscription/blocked/")

        return self.get_response(request)
