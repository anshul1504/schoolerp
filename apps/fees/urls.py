from django.urls import path

from .views import fees_overview


urlpatterns = [
    path("", fees_overview, name="fees_overview"),
]
