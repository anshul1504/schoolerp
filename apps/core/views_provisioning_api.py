from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.core.api_auth import require_token
from apps.schools.models import School


@api_view(["POST"])
def provision_user_upsert(request):
    token = require_token(request, scope="provision.users")
    if not token:
        return Response({"error": "unauthorized"}, status=401)

    payload = request.data or {}
    username = str(payload.get("username") or "").strip()
    email = str(payload.get("email") or "").strip()
    role = str(payload.get("role") or "").strip().upper()
    school_id_raw = str(payload.get("school_id") or "").strip()
    is_active = payload.get("is_active", True)

    if not username or not role:
        return Response({"error": "username and role are required"}, status=400)

    if school_id_raw and not school_id_raw.isdigit():
        return Response({"error": "school_id must be numeric"}, status=400)
    school_id = int(school_id_raw) if school_id_raw.isdigit() else None
    if school_id and not School.objects.filter(id=school_id, is_active=True).exists():
        return Response({"error": "school_id not found"}, status=400)

    User = get_user_model()
    defaults = {
        "email": email,
        "role": role,
        "school_id": school_id,
        "is_active": bool(is_active),
        "first_name": str(payload.get("first_name") or "").strip(),
        "last_name": str(payload.get("last_name") or "").strip(),
    }
    user = User.objects.filter(username=username).first()
    created = False
    if user:
        for k, v in defaults.items():
            setattr(user, k, v)
        user.save()
    else:
        user = User.objects.create(username=username, **defaults)
        user.set_unusable_password()
        user.save(update_fields=["password"])
        created = True

    return Response({"ok": True, "created": created, "user_id": user.id})


@api_view(["POST"])
def provision_user_deactivate(request):
    token = require_token(request, scope="provision.users")
    if not token:
        return Response({"error": "unauthorized"}, status=401)

    payload = request.data or {}
    username = str(payload.get("username") or "").strip()
    if not username:
        return Response({"error": "username is required"}, status=400)

    User = get_user_model()
    user = User.objects.filter(username=username).first()
    if not user:
        return Response({"ok": True, "changed": False})
    user.is_active = False
    user.save(update_fields=["is_active"])
    return Response({"ok": True, "changed": True, "user_id": user.id})
