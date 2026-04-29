from rest_framework import serializers

from .models import FeeDiscount, FeeFine, FeePayment, FeeStructure, StudentFeeLedger


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = "__all__"


class StudentFeeLedgerSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    structure_name = serializers.CharField(source="fee_structure.name", read_only=True)

    class Meta:
        model = StudentFeeLedger
        fields = "__all__"


class FeePaymentSerializer(serializers.ModelSerializer):
    collected_by_name = serializers.CharField(source="collected_by.get_full_name", read_only=True)

    class Meta:
        model = FeePayment
        fields = "__all__"


class FeeDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeDiscount
        fields = "__all__"


class FeeFineSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeFine
        fields = "__all__"
