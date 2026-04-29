from django.urls import path

from . import views

app_name = "digital_marketing"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("reports/advanced.csv", views.advanced_report_csv, name="advanced_report_csv"),
    path("reports/roi/", views.roi_analytics, name="roi_analytics"),
    path("reports/schedules/", views.report_schedule_list, name="report_schedule_list"),
    path("reports/schedules/create/", views.report_schedule_form, name="report_schedule_create"),
    path(
        "reports/schedules/<int:pk>/edit/", views.report_schedule_form, name="report_schedule_edit"
    ),
    path(
        "reports/schedules/<int:pk>/run/",
        views.report_schedule_run_now,
        name="report_schedule_run_now",
    ),
    path("settings/integrations/", views.integration_settings, name="integration_settings"),
    path("campaigns/", views.campaign_list, name="campaign_list"),
    path("campaigns/create/", views.campaign_form, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/edit/", views.campaign_form, name="campaign_edit"),
    path("campaigns/<int:pk>/delete/", views.campaign_delete, name="campaign_delete"),
    path("campaigns/export/csv/", views.campaign_export_csv, name="campaign_export_csv"),
    path("campaigns/export/excel/", views.campaign_export_excel, name="campaign_export_excel"),
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/create/", views.lead_form, name="lead_create"),
    path("leads/<int:pk>/edit/", views.lead_form, name="lead_edit"),
    path("leads/<int:pk>/delete/", views.lead_delete, name="lead_delete"),
    path("leads/export/csv/", views.lead_export_csv, name="lead_export_csv"),
    path("import/", views.import_data, name="import_data"),
    path("social/", views.social_hub, name="social_hub"),
    path("social/accounts/create/", views.social_account_form, name="social_account_create"),
    path("social/accounts/<int:pk>/edit/", views.social_account_form, name="social_account_edit"),
    path(
        "social/accounts/<int:pk>/test/",
        views.social_account_test_connection,
        name="social_account_test_connection",
    ),
    path("social/oauth/start/<str:platform>/", views.social_oauth_start, name="social_oauth_start"),
    path(
        "social/oauth/simulated-consent/",
        views.social_oauth_simulated_consent,
        name="social_oauth_simulated_consent",
    ),
    path("social/oauth/callback/", views.social_oauth_callback, name="social_oauth_callback"),
    path("social/posts/", views.social_post_list, name="social_post_list"),
    path("social/calendar/", views.social_calendar, name="social_calendar"),
    path("social/posts/create/", views.social_post_form, name="social_post_create"),
    path("social/posts/<int:pk>/edit/", views.social_post_form, name="social_post_edit"),
    path("social/posts/<int:pk>/delete/", views.social_post_delete, name="social_post_delete"),
    path(
        "social/posts/<int:pk>/submit-review/",
        views.social_post_submit_review,
        name="social_post_submit_review",
    ),
    path("social/posts/<int:pk>/approve/", views.social_post_approve, name="social_post_approve"),
    path("social/posts/<int:pk>/reject/", views.social_post_reject, name="social_post_reject"),
    path("social/posts/<int:pk>/publish/", views.social_post_publish, name="social_post_publish"),
    path("social/posts/<int:pk>/retry/", views.social_post_retry, name="social_post_retry"),
    path("website-integrations/", views.website_integration_list, name="website_integration_list"),
    path(
        "website-integrations/create/",
        views.website_integration_form,
        name="website_integration_create",
    ),
    path(
        "website-integrations/<int:pk>/edit/",
        views.website_integration_form,
        name="website_integration_edit",
    ),
    path(
        "website-integrations/<int:pk>/delete/",
        views.website_integration_delete,
        name="website_integration_delete",
    ),
    path(
        "website-integrations/<int:integration_id>/ingest/",
        views.website_integration_ingest,
        name="website_integration_ingest",
    ),
    path("seo/", views.seo_list, name="seo_list"),
    path("seo/create/", views.seo_form, name="seo_create"),
    path("seo/<int:pk>/", views.seo_detail, name="seo_detail"),
    path("seo/<int:pk>/edit/", views.seo_form, name="seo_edit"),
    path("seo/<int:pk>/delete/", views.seo_delete, name="seo_delete"),
    path("seo/export/csv/", views.seo_export_csv, name="seo_export_csv"),
]
