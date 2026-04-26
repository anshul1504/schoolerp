from django.urls import path

from .views import (
    academics_overview,
    academics_export_csv,
    academics_export_excel,
    academic_year_list,
    academic_year_create,
    academic_year_edit,
    academic_year_delete,
    academic_class_edit,
    academic_class_delete,
    academic_subject_edit,
    academic_subject_delete,
    teacher_allocation_delete,
    master_list,
    master_create,
    master_edit,
    master_delete,
)


urlpatterns = [
    path("", academics_overview, name="academics_overview"),
    path("export/csv/", academics_export_csv, name="academics-export-csv"),
    path("export/excel/", academics_export_excel, name="academics-export-excel"),
    path("years/", academic_year_list, name="academic_year_list"),
    path("years/create/", academic_year_create, name="academic_year_create"),
    path("years/<int:year_id>/edit/", academic_year_edit, name="academic_year_edit"),
    path("years/<int:year_id>/delete/", academic_year_delete, name="academic_year_delete"),
    path("classes/<int:class_id>/edit/", academic_class_edit, name="academic_class_edit"),
    path("classes/<int:class_id>/delete/", academic_class_delete, name="academic_class_delete"),
    path("subjects/<int:subject_id>/edit/", academic_subject_edit, name="academic_subject_edit"),
    path("subjects/<int:subject_id>/delete/", academic_subject_delete, name="academic_subject_delete"),
    path("allocations/<int:allocation_id>/delete/", teacher_allocation_delete, name="teacher_allocation_delete"),
    path("masters/<str:master_type>/", master_list, name="academic_master_list"),
    path("masters/<str:master_type>/create/", master_create, name="academic_master_create"),
    path("masters/<str:master_type>/<int:item_id>/edit/", master_edit, name="academic_master_edit"),
    path("masters/<str:master_type>/<int:item_id>/delete/", master_delete, name="academic_master_delete"),
]
