from django.urls import path

from . import views

app_name = "research"

urlpatterns = [
    path("", views.research_overview, name="overview"),
    path("projects/", views.project_list, name="project_list"),
    path("projects/create/", views.project_create, name="project_create"),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("projects/<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("projects/<int:pk>/grants/add/", views.grant_add, name="grant_add"),
    path("projects/<int:pk>/papers/add/", views.paper_add, name="paper_add"),
    path("projects/<int:pk>/ethics/update/", views.ethics_update, name="ethics_update"),
    path("grants/", views.grant_list, name="grant_list"),
    path("papers/", views.paper_list, name="paper_list"),
    path("ethics/", views.ethics_queue, name="ethics_queue"),
    # Export URLs
    path("export/projects/csv/", views.export_projects_csv, name="export_projects_csv"),
    path("export/projects/pdf/", views.export_projects_pdf, name="export_projects_pdf"),
    path(
        "projects/<int:pk>/export/pdf/",
        views.export_project_detail_pdf,
        name="export_project_detail_pdf",
    ),
    path("export/grants/csv/", views.export_grants_csv, name="export_grants_csv"),
    path("export/papers/csv/", views.export_papers_csv, name="export_papers_csv"),
]
