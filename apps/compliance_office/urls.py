from django.urls import path

from . import views

app_name = "compliance_office"

urlpatterns = [
    path("", views.overview, name="overview"),
    # Policies
    path("policies/", views.policy_list, name="policy_list"),
    path("policies/create/", views.policy_create, name="policy_create"),
    path("policies/<int:pk>/", views.policy_detail, name="policy_detail"),
    path("policies/<int:pk>/edit/", views.policy_edit, name="policy_edit"),
    path("policies/<int:pk>/delete/", views.policy_delete, name="policy_delete"),
    # Inspections / Audits
    path("inspections/", views.inspection_list, name="inspection_list"),
    path("inspections/create/", views.inspection_create, name="inspection_create"),
    path("inspections/<int:pk>/edit/", views.inspection_edit, name="inspection_edit"),
    path("inspections/<int:pk>/delete/", views.inspection_delete, name="inspection_delete"),
    # Certifications
    path("certifications/", views.certification_list, name="certification_list"),
    path("certifications/create/", views.certification_create, name="certification_create"),
    path("certifications/<int:pk>/", views.certification_detail, name="certification_detail"),
    path("certifications/<int:pk>/edit/", views.certification_edit, name="certification_edit"),
    path(
        "certifications/<int:pk>/delete/", views.certification_delete, name="certification_delete"
    ),
    # Student Compliance
    path("students/", views.student_compliance_list, name="student_list"),
]
