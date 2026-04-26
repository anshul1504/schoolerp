from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.core.change_log import record_change
from .models import Student


WATCH_FIELDS = [
    "school_id",
    "admission_no",
    "academic_year",
    "first_name",
    "middle_name",
    "last_name",
    "gender",
    "date_of_birth",
    "blood_group",
    "class_name",
    "section",
    "roll_number",
    "student_phone",
    "alternate_mobile",
    "email",
    "guardian_name",
    "guardian_phone",
    "guardian_email",
    "admission_date",
    "leaving_date",
    "is_active",
]


@receiver(pre_save, sender=Student)
def _student_pre_save(sender, instance: Student, **kwargs):
    if not instance.pk:
        instance._changelog_before = None
        return
    before = Student.objects.filter(pk=instance.pk).values(*WATCH_FIELDS).first()
    instance._changelog_before = before or None


@receiver(post_save, sender=Student)
def _student_post_save(sender, instance: Student, created: bool, **kwargs):
    if created:
        record_change(entity="students.Student", object_id=instance.pk, action="CREATED", changes={})
        return

    before = getattr(instance, "_changelog_before", None) or {}
    after = {field: getattr(instance, field) for field in WATCH_FIELDS}
    changes = {}
    for field in WATCH_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    if changes:
        record_change(entity="students.Student", object_id=instance.pk, action="UPDATED", changes=changes)


@receiver(post_delete, sender=Student)
def _student_post_delete(sender, instance: Student, **kwargs):
    record_change(entity="students.Student", object_id=instance.pk, action="DELETED", changes={})

