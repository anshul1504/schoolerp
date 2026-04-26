from django.db import migrations


DEFAULT_FEATURES = [
    ("Staff", "STAFF", "Staff directory and HR workflows"),
    ("Front Office", "FRONTOFFICE", "Reception, enquiries, visitor ops, campaigns"),
    ("Admissions", "ADMISSIONS", "Admissions documents and admission workflows"),
]


def seed_more_features_and_attach_to_plans(apps, schema_editor):
    Plan = apps.get_model("schools", "SubscriptionPlan")
    Feature = apps.get_model("schools", "PlanFeature")

    for name, code, desc in DEFAULT_FEATURES:
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

    # Keep backwards-compatible access: existing default plans get the new features too.
    for plan_code in ["SILVER", "GOLD", "PLATINUM"]:
        ensure_plan_has(plan_code, ["STAFF", "FRONTOFFICE", "ADMISSIONS"])


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0016_implementation_tracker"),
    ]

    operations = [
        migrations.RunPython(seed_more_features_and_attach_to_plans, migrations.RunPython.noop),
    ]

