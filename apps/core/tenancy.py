from __future__ import annotations

from typing import Iterable, Optional

from apps.schools.models import School


def school_scope_for_user(user):
    """Return the schools visible to this user (queryset)."""
    if getattr(user, "role", None) == "SUPER_ADMIN":
        return School.objects.filter(is_active=True).order_by("name")
    if getattr(user, "school_id", None):
        return School.objects.filter(id=user.school_id, is_active=True)
    return School.objects.none()


def allowed_school_ids_for_user(user) -> list[int]:
    return list(school_scope_for_user(user).values_list("id", flat=True))


def selected_school_for_request(request) -> Optional[School]:
    """Return the selected school for the request, respecting SUPER_ADMIN school picker."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None

    if getattr(user, "role", None) == "SUPER_ADMIN":
        school_id = request.POST.get("school") or request.GET.get("school")
        if school_id and str(school_id).isdigit():
            return School.objects.filter(id=int(school_id), is_active=True).first()
        return None

    return user.school if getattr(user, "school_id", None) else None


def scope_queryset_to_user_schools(qs, user, *, school_field: str = "school_id"):
    """Apply a school scope filter to a queryset using the given school_field."""
    return qs.filter(**{f"{school_field}__in": allowed_school_ids_for_user(user)})

