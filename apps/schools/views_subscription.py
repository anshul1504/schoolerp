from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.models import PlatformSettings
from apps.core.ui import build_layout_context
from apps.schools.feature_access import enabled_feature_codes_for_school
from apps.schools.models import SchoolSubscription


@login_required
def subscription_blocked(request):
    context = build_layout_context(request.user, current_section="dashboard")
    context["blocked_reason"] = (request.GET.get("reason") or "").strip()
    branding = PlatformSettings.objects.first()
    context["support_email"] = getattr(branding, "support_email", "") if branding else ""

    subscription = None
    enabled_features = set()
    if request.user.role != "SUPER_ADMIN" and getattr(request.user, "school_id", None):
        subscription = (
            SchoolSubscription.objects.select_related("school", "plan")
            .prefetch_related("plan__features")
            .filter(school_id=request.user.school_id)
            .first()
        )
        enabled_features = enabled_feature_codes_for_school(request.user.school_id)

    context["subscription"] = subscription
    context["enabled_features"] = sorted(enabled_features)
    return render(request, "billing/subscription_blocked.html", context)
