from django.contrib import admin

from .models import EthicsReview, Grant, ResearchPaper, ResearchProject


@admin.register(ResearchProject)
class ResearchProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "school", "pi", "status", "budget", "created_at")
    list_filter = ("status", "school")
    search_fields = ("title", "description", "pi__full_name")


@admin.register(Grant)
class GrantAdmin(admin.ModelAdmin):
    list_display = ("agency", "grant_id", "project", "amount", "status", "received_date")
    list_filter = ("status",)


@admin.register(ResearchPaper)
class ResearchPaperAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "journal", "publication_date")
    search_fields = ("title", "journal")


@admin.register(EthicsReview)
class EthicsReviewAdmin(admin.ModelAdmin):
    list_display = ("project", "status", "reviewer", "reviewed_at")
    list_filter = ("status",)
