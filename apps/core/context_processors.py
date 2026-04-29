from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.core.models import PlatformAnnouncement, PlatformSettings


def platform_settings(request):
    settings_obj = PlatformSettings.objects.first()
    if not settings_obj:
        settings_obj = PlatformSettings.objects.create()

    now = timezone.now()
    active_announcement = (
        PlatformAnnouncement.objects.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .order_by("-created_at")
        .first()
    )

    tenant_school = getattr(request, "tenant_school", None)
    return {
        "platform_settings": settings_obj,
        "platform_announcement": active_announcement,
        "tenant_school": tenant_school,
        "GOOGLE_OIDC_ENABLED": bool(getattr(settings, "GOOGLE_OIDC_ENABLED", False)),
    }
