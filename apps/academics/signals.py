from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.core.change_log import record_change
from .models import AcademicYear, ClassMaster, SectionMaster, SubjectMaster


def _watch(sender, instance, fields, entity):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = sender.objects.filter(pk=instance.pk).values(*fields).first()
    instance._changelog_before = before or None


def _diff(instance, fields):
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in fields}
    changes = {}
    for field in fields:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    return changes


@receiver(pre_save, sender=AcademicYear)
def _ay_pre(sender, instance: AcademicYear, **kwargs):
    _watch(AcademicYear, instance, ["school_id", "name", "start_date", "end_date", "is_current"], "academics.AcademicYear")


@receiver(post_save, sender=AcademicYear)
def _ay_post(sender, instance: AcademicYear, created: bool, **kwargs):
    if created:
        record_change(entity="academics.AcademicYear", object_id=instance.pk, action="CREATED", changes={})
        return
    changes = _diff(instance, ["school_id", "name", "start_date", "end_date", "is_current"])
    if changes:
        record_change(entity="academics.AcademicYear", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=AcademicYear)
def _ay_del(sender, instance: AcademicYear, **kwargs):
    record_change(entity="academics.AcademicYear", object_id=instance.pk, action="DELETED", changes={})


@receiver(pre_save, sender=ClassMaster)
def _cm_pre(sender, instance: ClassMaster, **kwargs):
    _watch(ClassMaster, instance, ["school_id", "name", "is_active"], "academics.ClassMaster")


@receiver(post_save, sender=ClassMaster)
def _cm_post(sender, instance: ClassMaster, created: bool, **kwargs):
    if created:
        record_change(entity="academics.ClassMaster", object_id=instance.pk, action="CREATED", changes={})
        return
    changes = _diff(instance, ["school_id", "name", "is_active"])
    if changes:
        record_change(entity="academics.ClassMaster", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=ClassMaster)
def _cm_del(sender, instance: ClassMaster, **kwargs):
    record_change(entity="academics.ClassMaster", object_id=instance.pk, action="DELETED", changes={})


@receiver(pre_save, sender=SectionMaster)
def _sm_pre(sender, instance: SectionMaster, **kwargs):
    _watch(SectionMaster, instance, ["school_id", "name", "is_active"], "academics.SectionMaster")


@receiver(post_save, sender=SectionMaster)
def _sm_post(sender, instance: SectionMaster, created: bool, **kwargs):
    if created:
        record_change(entity="academics.SectionMaster", object_id=instance.pk, action="CREATED", changes={})
        return
    changes = _diff(instance, ["school_id", "name", "is_active"])
    if changes:
        record_change(entity="academics.SectionMaster", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=SectionMaster)
def _sm_del(sender, instance: SectionMaster, **kwargs):
    record_change(entity="academics.SectionMaster", object_id=instance.pk, action="DELETED", changes={})


@receiver(pre_save, sender=SubjectMaster)
def _sub_pre(sender, instance: SubjectMaster, **kwargs):
    _watch(SubjectMaster, instance, ["school_id", "name", "is_active"], "academics.SubjectMaster")


@receiver(post_save, sender=SubjectMaster)
def _sub_post(sender, instance: SubjectMaster, created: bool, **kwargs):
    if created:
        record_change(entity="academics.SubjectMaster", object_id=instance.pk, action="CREATED", changes={})
        return
    changes = _diff(instance, ["school_id", "name", "is_active"])
    if changes:
        record_change(entity="academics.SubjectMaster", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=SubjectMaster)
def _sub_del(sender, instance: SubjectMaster, **kwargs):
    record_change(entity="academics.SubjectMaster", object_id=instance.pk, action="DELETED", changes={})

