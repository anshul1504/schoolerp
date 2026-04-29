from django.urls import path

from .views import (
    communication_overview,
    notice_create,
    notice_delete,
    notice_detail,
    notice_export_csv,
    notice_export_excel,
    notice_manage_list,
    notice_update,
)

urlpatterns = [
    path("", communication_overview, name="communication_overview"),
    path("manage/", notice_manage_list, name="notice_manage_list"),
    path("export/csv/", notice_export_csv, name="notice-export-csv"),
    path("export/excel/", notice_export_excel, name="notice-export-excel"),
    path("create/", notice_create, name="notice_create"),
    path("<int:notice_id>/edit/", notice_update, name="notice_update"),
    path("<int:notice_id>/delete/", notice_delete, name="notice_delete"),
    path("<int:notice_id>/", notice_detail, name="notice_detail"),
]
