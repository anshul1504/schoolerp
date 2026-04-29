from django.urls import path

from .views import exams_overview, generate_report_card_pdf

urlpatterns = [
    path("", exams_overview, name="exams_overview"),
    path(
        "report-card/<int:exam_id>/<int:student_id>/",
        generate_report_card_pdf,
        name="generate_report_card_pdf",
    ),
]
