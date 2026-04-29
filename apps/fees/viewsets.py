from rest_framework import permissions, viewsets

from .models import FeeDiscount, FeeFine, FeePayment, FeeStructure, StudentFeeLedger
from .serializers import (
    FeeDiscountSerializer,
    FeeFineSerializer,
    FeePaymentSerializer,
    FeeStructureSerializer,
    StudentFeeLedgerSerializer,
)


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class StudentFeeLedgerViewSet(viewsets.ModelViewSet):
    queryset = StudentFeeLedger.objects.all()
    serializer_class = StudentFeeLedgerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class FeePaymentViewSet(viewsets.ModelViewSet):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class FeeDiscountViewSet(viewsets.ModelViewSet):
    queryset = FeeDiscount.objects.all()
    serializer_class = FeeDiscountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class FeeFineViewSet(viewsets.ModelViewSet):
    queryset = FeeFine.objects.all()
    serializer_class = FeeFineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)
