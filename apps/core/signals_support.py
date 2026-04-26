from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.core.change_log import record_change
from apps.core.models import SupportTicket


WATCH_FIELDS = [
    "school_id",
    "created_by_id",
    "assigned_to_id",
    "title",
    "description",
    "status",
    "priority",
    "requester_email",
    "requester_phone",
    "resolved_at",
    "closed_at",
]


@receiver(pre_save, sender=SupportTicket)
def _ticket_pre_save(sender, instance: SupportTicket, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = SupportTicket.objects.filter(pk=instance.pk).values(*WATCH_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=SupportTicket)
def _ticket_post_save(sender, instance: SupportTicket, created: bool, **kwargs):
    if created:
        record_change(entity="core.SupportTicket", object_id=instance.pk, action="CREATED", changes={})
        return
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in WATCH_FIELDS}
    changes = {}
    for field in WATCH_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(entity="core.SupportTicket", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=SupportTicket)
def _ticket_post_delete(sender, instance: SupportTicket, **kwargs):
    record_change(entity="core.SupportTicket", object_id=instance.pk, action="DELETED", changes={})

