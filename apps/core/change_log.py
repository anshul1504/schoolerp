from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime

from apps.core.models import EntityChangeLog
from apps.core.request_context import get_current_request


def _safe_str(value):
    try:
        return str(value)
    except Exception:
        return ""


def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        try:
            return value.isoformat()
        except Exception:
            return _safe_str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return _safe_str(value)


def record_change(*, entity: str, object_id, action: str, changes: dict) -> None:
    request = get_current_request()
    actor = getattr(request, "user", None) if request is not None else None
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None

    ip = ""
    ua = ""
    try:
        ip = (request.META.get("REMOTE_ADDR") or "")[:64] if request is not None else ""
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:5000] if request is not None else ""
    except Exception:
        ip, ua = "", ""

    EntityChangeLog.objects.create(
        actor=actor,
        entity=entity,
        object_id=_safe_str(object_id),
        action=action,
        changes=_json_safe(changes or {}),
        ip_address=ip,
        user_agent=ua,
    )
