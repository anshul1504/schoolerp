from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import timetable_overview
from .viewsets import PeriodMasterViewSet, TimetableSlotViewSet

router = DefaultRouter()
router.register("periods", PeriodMasterViewSet, basename="timetable-period")
router.register("slots", TimetableSlotViewSet, basename="timetable-slot")

urlpatterns = [
    path("", timetable_overview, name="timetable_overview"),
    path("api/", include(router.urls)),
]
