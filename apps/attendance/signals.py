from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.core.change_log import record_change
from .models import AttendanceSession, StudentAttendance


SESSION_FIELDS = [
    "school_id",
    "academic_class_id",
    "attendance_date",
    "marked_by_id",
    "note",
]


@receiver(pre_save, sender=AttendanceSession)
def _session_pre_save(sender, instance: AttendanceSession, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = AttendanceSession.objects.filter(pk=instance.pk).values(*SESSION_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=AttendanceSession)
def _session_post_save(sender, instance: AttendanceSession, created: bool, **kwargs):
    if created:
        record_change(entity="attendance.AttendanceSession", object_id=instance.pk, action="CREATED", changes={})
        return
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in SESSION_FIELDS}
    changes = {}
    for field in SESSION_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(entity="attendance.AttendanceSession", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=AttendanceSession)
def _session_post_delete(sender, instance: AttendanceSession, **kwargs):
    record_change(entity="attendance.AttendanceSession", object_id=instance.pk, action="DELETED", changes={})


ENTRY_FIELDS = [
    "session_id",
    "student_id",
    "status",
    "remark",
]


@receiver(pre_save, sender=StudentAttendance)
def _entry_pre_save(sender, instance: StudentAttendance, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = StudentAttendance.objects.filter(pk=instance.pk).values(*ENTRY_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=StudentAttendance)
def _entry_post_save(sender, instance: StudentAttendance, created: bool, **kwargs):
    if created:
        record_change(entity="attendance.StudentAttendance", object_id=instance.pk, action="CREATED", changes={})
        return
    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in ENTRY_FIELDS}
    changes = {}
    for field in ENTRY_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(entity="attendance.StudentAttendance", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=StudentAttendance)
def _entry_post_delete(sender, instance: StudentAttendance, **kwargs):
    record_change(entity="attendance.StudentAttendance", object_id=instance.pk, action="DELETED", changes={})

