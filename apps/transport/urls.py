from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import transport_overview
from .viewsets import (
    DriverViewSet,
    RouteViewSet,
    StopViewSet,
    TransportAllocationViewSet,
    VehicleViewSet,
)

router = DefaultRouter()
router.register("drivers", DriverViewSet, basename="transport-driver")
router.register("vehicles", VehicleViewSet, basename="transport-vehicle")
router.register("routes", RouteViewSet, basename="transport-route")
router.register("stops", StopViewSet, basename="transport-stop")
router.register("allocations", TransportAllocationViewSet, basename="transport-allocation")

urlpatterns = [
    path("", transport_overview, name="transport_overview"),
    path("api/", include(router.urls)),
]
