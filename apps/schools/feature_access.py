from django.core.cache import cache

from apps.schools.models import SchoolSubscription


MODULE_FEATURE_MAP = {
    "students": "STUDENTS",
    "academics": "ACADEMICS",
    "staff": "STAFF",
    "attendance": "ATTENDANCE",
    "fees": "FEES",
    "exams": "EXAMS",
    "communication": "COMMUNICATION",
    "frontoffice": "FRONTOFFICE",
    "admissions": "ADMISSIONS",
    "reports": "REPORTS",
}

PATH_MODULE_PREFIXES = {
    "/students/": "students",
    "/academics/": "academics",
    "/staff/": "staff",
    "/attendance/": "attendance",
    "/fees/": "fees",
    "/exams/": "exams",
    "/communication/": "communication",
    "/frontoffice/": "frontoffice",
    "/admissions/": "admissions",
    "/reports/": "reports",
}


def enabled_feature_codes_for_school(school_id):
    cache_key = f"school_features:{school_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    subscription = (
        SchoolSubscription.objects.select_related("plan")
        .prefetch_related("plan__features")
        .filter(school_id=school_id)
        .first()
    )
    if not subscription:
        cache.set(cache_key, set(), timeout=60)
        return set()

    codes = set(subscription.plan.features.values_list("code", flat=True))
    cache.set(cache_key, codes, timeout=60)
    return codes


def required_feature_for_path(path):
    for prefix, module_key in PATH_MODULE_PREFIXES.items():
        if path.startswith(prefix):
            return MODULE_FEATURE_MAP.get(module_key)
    return None
