from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.core.change_log import record_change

from .models import School, SubscriptionInvoice, SubscriptionPayment

WATCH_FIELDS = [
    "name",
    "code",
    "email",
    "phone",
    "support_email",
    "website",
    "address",
    "address_line2",
    "city",
    "state",
    "pincode",
    "principal_name",
    "board",
    "medium",
    "established_year",
    "student_capacity",
    "allowed_campuses",
    "is_active",
]


@receiver(pre_save, sender=School)
def _school_pre_save(sender, instance: School, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = School.objects.filter(pk=instance.pk).values(*WATCH_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=School)
def _school_post_save(sender, instance: School, created: bool, **kwargs):
    if created:
        record_change(entity="schools.School", object_id=instance.pk, action="CREATED", changes={})
        return

    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in WATCH_FIELDS}
    changes = {}
    for field in WATCH_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(
            entity="schools.School", object_id=instance.pk, action="UPDATED", changes=changes
        )


@receiver(post_delete, sender=School)
def _school_post_delete(sender, instance: School, **kwargs):
    record_change(entity="schools.School", object_id=instance.pk, action="DELETED", changes={})


INVOICE_WATCH_FIELDS = [
    "school_id",
    "plan_id",
    "period_start",
    "period_end",
    "amount",
    "tax_percent",
    "tax_amount",
    "total_amount",
    "due_date",
    "status",
    "issued_at",
]


@receiver(pre_save, sender=SubscriptionInvoice)
def _invoice_pre_save(sender, instance: SubscriptionInvoice, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = (
        SubscriptionInvoice.objects.filter(pk=instance.pk).values(*INVOICE_WATCH_FIELDS).first()
    )
    instance._changelog_before = before or None


@receiver(post_save, sender=SubscriptionInvoice)
def _invoice_post_save(sender, instance: SubscriptionInvoice, created: bool, **kwargs):
    if created:
        record_change(
            entity="schools.SubscriptionInvoice",
            object_id=instance.pk,
            action="CREATED",
            changes={},
        )
        return
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in INVOICE_WATCH_FIELDS}
    changes = {}
    for field in INVOICE_WATCH_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(
            entity="schools.SubscriptionInvoice",
            object_id=instance.pk,
            action="UPDATED",
            changes=changes,
        )


@receiver(post_delete, sender=SubscriptionInvoice)
def _invoice_post_delete(sender, instance: SubscriptionInvoice, **kwargs):
    record_change(
        entity="schools.SubscriptionInvoice", object_id=instance.pk, action="DELETED", changes={}
    )


PAYMENT_WATCH_FIELDS = [
    "invoice_id",
    "amount",
    "method",
    "transaction_ref",
    "paid_at",
]


@receiver(pre_save, sender=SubscriptionPayment)
def _payment_pre_save(sender, instance: SubscriptionPayment, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = (
        SubscriptionPayment.objects.filter(pk=instance.pk).values(*PAYMENT_WATCH_FIELDS).first()
    )
    instance._changelog_before = before or None


@receiver(post_save, sender=SubscriptionPayment)
def _payment_post_save(sender, instance: SubscriptionPayment, created: bool, **kwargs):
    if created:
        record_change(
            entity="schools.SubscriptionPayment",
            object_id=instance.pk,
            action="CREATED",
            changes={},
        )
        return
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in PAYMENT_WATCH_FIELDS}
    changes = {}
    for field in PAYMENT_WATCH_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(
            entity="schools.SubscriptionPayment",
            object_id=instance.pk,
            action="UPDATED",
            changes=changes,
        )


@receiver(post_delete, sender=SubscriptionPayment)
def _payment_post_delete(sender, instance: SubscriptionPayment, **kwargs):
    record_change(
        entity="schools.SubscriptionPayment", object_id=instance.pk, action="DELETED", changes={}
    )
