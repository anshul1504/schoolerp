from rest_framework import permissions, viewsets

from .models import PeriodMaster, TimetableSlot
from .serializers import PeriodMasterSerializer, TimetableSlotSerializer


class PeriodMasterViewSet(viewsets.ModelViewSet):
    queryset = PeriodMaster.objects.all()
    serializer_class = PeriodMasterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class TimetableSlotViewSet(viewsets.ModelViewSet):
    queryset = TimetableSlot.objects.all()
    serializer_class = TimetableSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)
