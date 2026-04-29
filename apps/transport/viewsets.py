from rest_framework import viewsets

from apps.core.permissions import HasModulePermission

from .models import Driver, Route, Stop, TransportAllocation, Vehicle
from .serializers import (
    DriverSerializer,
    RouteSerializer,
    StopSerializer,
    TransportAllocationSerializer,
    VehicleSerializer,
)


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class StopViewSet(viewsets.ModelViewSet):
    queryset = Stop.objects.all()
    serializer_class = StopSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(route__school=self.request.user.school)


class TransportAllocationViewSet(viewsets.ModelViewSet):
    queryset = TransportAllocation.objects.all()
    serializer_class = TransportAllocationSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(route__school=self.request.user.school)
