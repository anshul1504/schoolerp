from django.urls import path

from . import views

app_name = "alumni"

urlpatterns = [
    path("", views.alumni_dashboard, name="dashboard"),
    path("list/", views.alumni_list, name="alumni_list"),
    path("list/add/", views.alumni_create, name="alumni_create"),
    path("list/detail/<int:pk>/", views.alumni_detail, name="alumni_detail"),
    path("list/edit/<int:pk>/", views.alumni_edit, name="alumni_edit"),
    path("list/delete/<int:pk>/", views.alumni_delete, name="alumni_delete"),
    path("list/verify/<int:pk>/", views.toggle_verification, name="toggle_verification"),
    path("list/contribution/<int:pk>/", views.add_contribution, name="add_contribution"),
    path(
        "list/contribution/delete/<int:pk>/", views.delete_contribution, name="delete_contribution"
    ),
    path("events/", views.event_list, name="event_list"),
    path("events/detail/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/create/", views.event_create, name="event_create"),
    path("events/edit/<int:pk>/", views.event_edit, name="event_edit"),
    path("events/delete/<int:pk>/", views.event_delete, name="event_delete"),
    path("stories/", views.success_stories, name="success_stories"),
    path("stories/detail/<int:pk>/", views.story_detail, name="story_detail"),
    path("stories/publish/", views.story_create, name="story_create"),
    path("stories/edit/<int:pk>/", views.story_edit, name="story_edit"),
    path("stories/delete/<int:pk>/", views.story_delete, name="story_delete"),
    path("list/export/", views.export_alumni_csv, name="export_alumni_csv"),
]
