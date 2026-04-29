from django.contrib import admin

from .models import (
    Application,
    CareerEvent,
    CareerProfile,
    CounselingSession,
    EventRegistration,
    University,
)


@admin.register(CareerProfile)
class CareerProfileAdmin(admin.ModelAdmin):
    list_display = ("student", "target_exams", "updated_at")
    search_fields = ("student__full_name", "target_exams")


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "is_abroad")
    list_filter = ("is_abroad", "school")
    search_fields = ("name", "location")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "university", "course", "status", "deadline")
    list_filter = ("status",)
    search_fields = ("student__full_name", "university__name", "course")


@admin.register(CounselingSession)
class CounselingSessionAdmin(admin.ModelAdmin):
    list_display = ("student", "counselor", "session_type", "scheduled_at", "is_completed")
    list_filter = ("session_type", "is_completed")
    search_fields = ("student__full_name", "counselor__full_name")


@admin.register(CareerEvent)
class CareerEventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "date", "location")
    list_filter = ("event_type",)
    search_fields = ("title", "location")


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "student", "attended", "registered_at")
    list_filter = ("attended",)
