from django.urls import path

from .views import exams_overview


urlpatterns = [
    path("", exams_overview, name="exams_overview"),
]
