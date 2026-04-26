from django.urls import path

from .views import (
    staff_list,
    staff_create,
    staff_edit,
    staff_delete,
    staff_import,
    staff_import_errors_csv,
    staff_import_sample,
    staff_export_csv,
    staff_export_excel,
)


urlpatterns = [
    path("", staff_list, name="staff-list"),
    path("create/", staff_create, name="staff-create"),
    path("import/", staff_import, name="staff-import"),
    path("import/sample/<str:file_type>/", staff_import_sample, name="staff-import-sample"),
    path("import/errors/", staff_import_errors_csv, name="staff-import-errors"),
    path("export/csv/", staff_export_csv, name="staff-export-csv"),
    path("export/excel/", staff_export_excel, name="staff-export-excel"),
    path("<int:id>/edit/", staff_edit, name="staff-edit"),
    path("<int:id>/delete/", staff_delete, name="staff-delete"),
]
