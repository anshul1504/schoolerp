from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.core.change_log import record_change

from .models import User

WATCH_FIELDS = [
    "username",
    "email",
    "first_name",
    "last_name",
    "role",
    "school_id",
    "is_active",
]


@receiver(pre_save, sender=User)
def _user_pre_save(sender, instance: User, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = User.objects.filter(pk=instance.pk).values(*WATCH_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=User)
def _user_post_save(sender, instance: User, created: bool, **kwargs):
    if created:
        record_change(entity="accounts.User", object_id=instance.pk, action="CREATED", changes={})
        return

    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in WATCH_FIELDS}
    changes = {}
    for field in WATCH_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(
            entity="accounts.User", object_id=instance.pk, action="UPDATED", changes=changes
        )
