from rest_framework import serializers

from .models import Driver, Route, Stop, TransportAllocation, Vehicle


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = "__all__"


class VehicleSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.full_name", read_only=True)

    class Meta:
        model = Vehicle
        fields = "__all__"


class RouteSerializer(serializers.ModelSerializer):
    vehicle_no = serializers.CharField(source="vehicle.vehicle_no", read_only=True)

    class Meta:
        model = Route
        fields = "__all__"


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = "__all__"


class TransportAllocationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    route_name = serializers.CharField(source="route.name", read_only=True)
    stop_name = serializers.CharField(source="stop.name", read_only=True)

    class Meta:
        model = TransportAllocation
        fields = "__all__"
