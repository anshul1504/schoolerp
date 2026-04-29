from django.urls import path

from . import views

app_name = "security_office"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("incidents/", views.incident_list, name="incident_list"),
    path("incidents/create/", views.incident_form, name="incident_create"),
    path("incidents/<int:pk>/edit/", views.incident_form, name="incident_edit"),
    path("incidents/<int:pk>/delete/", views.incident_delete, name="incident_delete"),
    path("visitors/", views.visitor_list, name="visitor_list"),
    path("visitors/create/", views.visitor_form, name="visitor_create"),
    path("visitors/<int:pk>/edit/", views.visitor_form, name="visitor_edit"),
    path("visitors/<int:pk>/delete/", views.visitor_delete, name="visitor_delete"),
    path("roster/", views.roster_list, name="roster_list"),
    path("roster/create/", views.roster_form, name="roster_create"),
    path("roster/<int:pk>/edit/", views.roster_form, name="roster_edit"),
    path("roster/<int:pk>/delete/", views.roster_delete, name="roster_delete"),
    path("gate-passes/", views.gate_pass_list, name="gate_pass_list"),
    path("gate-passes/create/", views.gate_pass_form, name="gate_pass_create"),
    path("gate-passes/<int:pk>/edit/", views.gate_pass_form, name="gate_pass_edit"),
    path("gate-passes/<int:pk>/delete/", views.gate_pass_delete, name="gate_pass_delete"),
    path("patrol-logs/", views.patrol_log_list, name="patrol_log_list"),
    path("patrol-logs/create/", views.patrol_log_form, name="patrol_log_create"),
    path("patrol-logs/<int:pk>/edit/", views.patrol_log_form, name="patrol_log_edit"),
    path("patrol-logs/<int:pk>/delete/", views.patrol_log_delete, name="patrol_log_delete"),
]
