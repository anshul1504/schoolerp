from django.urls import path

from .views import attendance_overview


urlpatterns = [
    path("", attendance_overview, name="attendance_overview"),
]
