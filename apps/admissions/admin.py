from django.contrib import admin

from .models import AdmissionApplication, AdmissionDocument, AdmissionEvent


class AdmissionDocumentInline(admin.TabularInline):
    model = AdmissionDocument
    extra = 0


class AdmissionEventInline(admin.TabularInline):
    model = AdmissionEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "school", "application_no", "student_name", "status", "created_at")
    list_filter = ("status", "school")
    search_fields = ("application_no", "student_name", "phone", "email")
    inlines = [AdmissionDocumentInline, AdmissionEventInline]


@admin.register(AdmissionDocument)
class AdmissionDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "title", "is_received", "received_at")
    list_filter = ("is_received",)
    search_fields = ("title", "application__application_no", "application__student_name")


@admin.register(AdmissionEvent)
class AdmissionEventAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "action", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("application__application_no", "message")
