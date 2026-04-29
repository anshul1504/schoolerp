from rest_framework import serializers

from .models import Bed, Hostel, HostelAllocation, MessPlan, Room


class HostelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hostel
        fields = "__all__"


class RoomSerializer(serializers.ModelSerializer):
    hostel_name = serializers.CharField(source="hostel.name", read_only=True)

    class Meta:
        model = Room
        fields = "__all__"


class BedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bed
        fields = "__all__"


class MessPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessPlan
        fields = "__all__"


class HostelAllocationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    hostel_name = serializers.CharField(source="hostel.name", read_only=True)
    room_number = serializers.CharField(source="room.room_number", read_only=True)

    class Meta:
        model = HostelAllocation
        fields = "__all__"
