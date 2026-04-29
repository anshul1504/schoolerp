from django.urls import path

from . import views

app_name = "career_counseling"

urlpatterns = [
    path("", views.counseling_overview, name="overview"),
    path("students/", views.student_list, name="student_list"),
    path("students/<int:pk>/", views.student_detail, name="student_detail"),
    path("applications/", views.application_list, name="application_list"),
    path("applications/add/", views.application_add, name="application_add"),
    path("applications/<int:pk>/edit/", views.application_edit, name="application_edit"),
    path("applications/<int:pk>/delete/", views.application_delete, name="application_delete"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/add/", views.session_add, name="session_add"),
    path("sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path("universities/", views.university_list, name="university_list"),
    path("universities/add/", views.university_add, name="university_add"),
    path("universities/<int:pk>/edit/", views.university_edit, name="university_edit"),
    path("universities/<int:pk>/delete/", views.university_delete, name="university_delete"),
    path("events/", views.event_list, name="event_list"),
    path("events/add/", views.event_add, name="event_add"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/edit/", views.event_edit, name="event_edit"),
]
