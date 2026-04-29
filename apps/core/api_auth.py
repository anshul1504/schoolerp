from django.utils import timezone

from apps.core.models import IntegrationToken


def token_from_request(request) -> str:
    raw = request.headers.get("X-API-KEY") or request.headers.get("Authorization") or ""
    raw = raw.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    return raw


def require_token(request, *, scope: str) -> IntegrationToken | None:
    token = token_from_request(request)
    if not token:
        return None
    obj = IntegrationToken.objects.filter(token=token, is_active=True).first()
    if not obj:
        return None
    scopes = set(obj.scopes or [])
    if "*" not in scopes and scope not in scopes:
        return None
    IntegrationToken.objects.filter(id=obj.id).update(last_used_at=timezone.now())
    return obj
