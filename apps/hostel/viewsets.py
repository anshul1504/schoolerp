from rest_framework import viewsets

from apps.core.permissions import HasModulePermission

from .models import Bed, Hostel, HostelAllocation, MessPlan, Room
from .serializers import (
    BedSerializer,
    HostelAllocationSerializer,
    HostelSerializer,
    MessPlanSerializer,
    RoomSerializer,
)


class HostelViewSet(viewsets.ModelViewSet):
    queryset = Hostel.objects.all()
    serializer_class = HostelSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(hostel__school=self.request.user.school)


class BedViewSet(viewsets.ModelViewSet):
    queryset = Bed.objects.all()
    serializer_class = BedSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(room__hostel__school=self.request.user.school)


class MessPlanViewSet(viewsets.ModelViewSet):
    queryset = MessPlan.objects.all()
    serializer_class = MessPlanSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class HostelAllocationViewSet(viewsets.ModelViewSet):
    queryset = HostelAllocation.objects.all()
    serializer_class = HostelAllocationSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(hostel__school=self.request.user.school)
