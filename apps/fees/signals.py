from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.core.change_log import record_change
from .models import FeePayment, StudentFeeLedger


LEDGER_FIELDS = [
    "school_id",
    "student_id",
    "fee_structure_id",
    "billing_month",
    "amount_due",
    "amount_paid",
    "due_date",
    "status",
]


@receiver(pre_save, sender=StudentFeeLedger)
def _ledger_pre_save(sender, instance: StudentFeeLedger, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = StudentFeeLedger.objects.filter(pk=instance.pk).values(*LEDGER_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=StudentFeeLedger)
def _ledger_post_save(sender, instance: StudentFeeLedger, created: bool, **kwargs):
    if created:
        record_change(entity="fees.StudentFeeLedger", object_id=instance.pk, action="CREATED", changes={})
        return
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in LEDGER_FIELDS}
    changes = {}
    for field in LEDGER_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(entity="fees.StudentFeeLedger", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=StudentFeeLedger)
def _ledger_post_delete(sender, instance: StudentFeeLedger, **kwargs):
    record_change(entity="fees.StudentFeeLedger", object_id=instance.pk, action="DELETED", changes={})


PAYMENT_FIELDS = [
    "ledger_id",
    "school_id",
    "student_id",
    "amount",
    "payment_date",
    "payment_mode",
    "reference_no",
    "collected_by_id",
]


@receiver(pre_save, sender=FeePayment)
def _payment_pre_save(sender, instance: FeePayment, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = FeePayment.objects.filter(pk=instance.pk).values(*PAYMENT_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=FeePayment)
def _payment_post_save(sender, instance: FeePayment, created: bool, **kwargs):
    if created:
        record_change(entity="fees.FeePayment", object_id=instance.pk, action="CREATED", changes={})
        return
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in PAYMENT_FIELDS}
    changes = {}
    for field in PAYMENT_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(entity="fees.FeePayment", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=FeePayment)
def _payment_post_delete(sender, instance: FeePayment, **kwargs):
    record_change(entity="fees.FeePayment", object_id=instance.pk, action="DELETED", changes={})

