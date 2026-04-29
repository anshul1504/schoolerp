from django.urls import path

from .views import (
    admission_create,
    admission_create_student,
    admission_delete,
    admission_detail,
    admission_document_add,
    admission_document_toggle_received,
    admission_edit,
    admission_list,
    admission_status,
)

urlpatterns = [
    path("", admission_list, name="admission-list"),
    path("create/", admission_create, name="admission-create"),
    path("<int:application_id>/", admission_detail, name="admission-detail"),
    path("<int:application_id>/edit/", admission_edit, name="admission-edit"),
    path("<int:application_id>/delete/", admission_delete, name="admission-delete"),
    path("<int:application_id>/status/", admission_status, name="admission-status"),
    path(
        "<int:application_id>/documents/add/", admission_document_add, name="admission-document-add"
    ),
    path(
        "<int:application_id>/documents/<int:document_id>/toggle/",
        admission_document_toggle_received,
        name="admission-document-toggle",
    ),
    path(
        "<int:application_id>/create-student/",
        admission_create_student,
        name="admission-create-student",
    ),
]
