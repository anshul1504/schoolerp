from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import hostel_overview
from .viewsets import (
    BedViewSet,
    HostelAllocationViewSet,
    HostelViewSet,
    MessPlanViewSet,
    RoomViewSet,
)

router = DefaultRouter()
router.register("hostels", HostelViewSet, basename="hostel")
router.register("rooms", RoomViewSet, basename="hostel-room")
router.register("beds", BedViewSet, basename="hostel-bed")
router.register("mess-plans", MessPlanViewSet, basename="hostel-mess")
router.register("allocations", HostelAllocationViewSet, basename="hostel-allocation")

urlpatterns = [
    path("", hostel_overview, name="hostel_overview"),
    path("api/", include(router.urls)),
]
