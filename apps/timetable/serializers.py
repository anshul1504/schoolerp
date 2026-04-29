from rest_framework import serializers

from .models import PeriodMaster, TimetableSlot


class PeriodMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodMaster
        fields = "__all__"


class TimetableSlotSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    section = serializers.CharField(source="academic_class.section", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)

    class Meta:
        model = TimetableSlot
        fields = "__all__"
