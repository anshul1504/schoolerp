from django.db import migrations

ADVANCED_FEATURES = [
    ("Research & Ethics", "RESEARCH", "Manage institutional research projects and ethics reviews"),
    (
        "Career Counseling",
        "CAREER_COUNSELING",
        "Student career guidance and university applications tracking",
    ),
    ("Transport Management", "TRANSPORT", "Fleet, route, and student transport tracking"),
    ("Hostel Management", "HOSTEL", "Dormitory, allocation, and mess operations"),
    ("Library Management", "LIBRARY", "Book inventory and circulation system"),
    ("Advanced Timetable", "TIMETABLE", "Automated scheduling and class timetables"),
]


def seed_advanced_features_and_gating(apps, schema_editor):
    Plan = apps.get_model("schools", "SubscriptionPlan")
    Feature = apps.get_model("schools", "PlanFeature")

    for name, code, desc in ADVANCED_FEATURES:
        Feature.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": desc, "is_active": True},
        )

    features = {f.code: f for f in Feature.objects.all()}

    def ensure_plan_has(code: str, extra_codes: list[str]):
        plan = Plan.objects.filter(code=code).first()
        if not plan:
            return
        ids = list(plan.features.values_list("id", flat=True))
        for c in extra_codes:
            if c in features and features[c].id not in ids:
                ids.append(features[c].id)
        plan.features.set(ids)

    # PLATINUM gets absolutely everything (Full ERP suite)
    ensure_plan_has(
        "PLATINUM",
        [
            "RESEARCH",
            "CAREER_COUNSELING",
            "TRANSPORT",
            "HOSTEL",
            "LIBRARY",
            "TIMETABLE",
            "STAFF",
            "FRONTOFFICE",
            "ADMISSIONS",
        ],
    )

    # GOLD gets standard operational modules, but not Research or Career Counseling
    ensure_plan_has(
        "GOLD",
        ["TRANSPORT", "HOSTEL", "LIBRARY", "TIMETABLE", "STAFF", "FRONTOFFICE", "ADMISSIONS"],
    )


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0019_school_cin_number_school_currency_school_gst_number_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_advanced_features_and_gating, migrations.RunPython.noop),
    ]
