from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
    path("schools/", include("apps.schools.urls")),
    path("admissions/", include("apps.admissions.urls")),
    path("students/", include("apps.students.urls")),
    path("academics/", include("apps.academics.urls")),
    path("staff/", include("apps.staff.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("fees/", include("apps.fees.urls")),
    path("exams/", include("apps.exams.urls")),
    path("communication/", include("apps.communication.urls")),
    path("frontoffice/", include("apps.frontoffice.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
