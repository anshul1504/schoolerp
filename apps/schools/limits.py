from apps.schools.models import SchoolSubscription


def active_student_limit_for_school(school_id):
    subscription = (
        SchoolSubscription.objects.select_related("plan")
        .filter(school_id=school_id)
        .first()
    )
    if not subscription or not subscription.plan:
        return None
    limit = getattr(subscription.plan, "max_students", None)
    if not limit or int(limit) <= 0:
        return None
    return int(limit)


def campus_limit_for_school(school_id):
    subscription = (
        SchoolSubscription.objects.select_related("plan")
        .filter(school_id=school_id)
        .first()
    )
    if not subscription or not subscription.plan:
        return None
    limit = getattr(subscription.plan, "max_campuses", None)
    if not limit or int(limit) <= 0:
        return None
    return int(limit)
