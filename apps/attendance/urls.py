from django.urls import path

from .views import attendance_overview, monthly_report

urlpatterns = [
    path("", attendance_overview, name="attendance_overview"),
    path("monthly-report/", monthly_report, name="monthly_report"),
]
