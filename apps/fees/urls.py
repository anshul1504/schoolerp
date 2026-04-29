from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import fees_overview, generate_receipt_pdf
from .viewsets import (
    FeeDiscountViewSet,
    FeeFineViewSet,
    FeePaymentViewSet,
    FeeStructureViewSet,
    StudentFeeLedgerViewSet,
)

router = DefaultRouter()
router.register("structures", FeeStructureViewSet, basename="fee-structure")
router.register("ledgers", StudentFeeLedgerViewSet, basename="fee-ledger")
router.register("payments", FeePaymentViewSet, basename="fee-payment")
router.register("discounts", FeeDiscountViewSet, basename="fee-discount")
router.register("fines", FeeFineViewSet, basename="fee-fine")

urlpatterns = [
    path("", fees_overview, name="fees_overview"),
    path("receipt/<int:payment_id>/", generate_receipt_pdf, name="generate_receipt_pdf"),
    path("api/", include(router.urls)),
]
