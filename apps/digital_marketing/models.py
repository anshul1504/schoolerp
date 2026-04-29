from django.conf import settings
from django.db import models

from apps.schools.models import School


class MarketingCampaign(models.Model):
    STATUS_CHOICES = (("DRAFT", "Draft"), ("ACTIVE", "Active"), ("PAUSED", "Paused"), ("COMPLETED", "Completed"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="marketing_campaigns")
    name = models.CharField(max_length=200)
    channel = models.CharField(max_length=50, default="Meta Ads")
    objective = models.CharField(max_length=120, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class MarketingLead(models.Model):
    STAGE_CHOICES = (("NEW", "New"), ("CONTACTED", "Contacted"), ("QUALIFIED", "Qualified"), ("CONVERTED", "Converted"), ("LOST", "Lost"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="marketing_leads")
    campaign = models.ForeignKey(MarketingCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    student_name = models.CharField(max_length=150)
    guardian_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    class_interest = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=80, default="Website")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="NEW")
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    next_followup_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_name} ({self.phone})"


class SocialAccountConnection(models.Model):
    PLATFORM_CHOICES = (("INSTAGRAM", "Instagram"), ("FACEBOOK", "Facebook"), ("YOUTUBE", "YouTube"), ("LINKEDIN", "LinkedIn"), ("X", "X/Twitter"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="social_accounts")
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    handle = models.CharField(max_length=120)
    profile_url = models.URLField(blank=True)
    access_token = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SocialPost(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("IN_REVIEW", "In Review"),
        ("APPROVED", "Approved"),
        ("SCHEDULED", "Scheduled"),
        ("PUBLISHED", "Published"),
        ("FAILED", "Failed"),
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="social_posts")
    campaign = models.ForeignKey(MarketingCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="social_posts")
    account = models.ForeignKey(SocialAccountConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    title = models.CharField(max_length=180)
    caption = models.TextField(blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_social_posts")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    reach = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    leads_generated = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class WebsiteFormIntegration(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="website_integrations")
    name = models.CharField(max_length=140)
    website_url = models.URLField()
    endpoint_url = models.URLField(blank=True)
    auth_key = models.CharField(max_length=255, blank=True)
    source_label = models.CharField(max_length=80, default="Website Form")
    field_mapping = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SEOTracker(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="seo_trackers")
    page_url = models.URLField()
    keyword = models.CharField(max_length=160)
    ranking_position = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    ctr_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    audit_notes = models.TextField(blank=True)
    tracked_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)


class SocialConnectionTestLog(models.Model):
    RESULT_CHOICES = (("SUCCESS", "Success"), ("FAILED", "Failed"))
    account = models.ForeignKey(SocialAccountConnection, on_delete=models.CASCADE, related_name="test_logs")
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    message = models.CharField(max_length=255, blank=True)
    tested_at = models.DateTimeField(auto_now_add=True)


class SocialPublishRun(models.Model):
    RESULT_CHOICES = (("SUCCESS", "Success"), ("FAILED", "Failed"), ("RETRY", "Retry"))
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name="publish_runs")
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    message = models.CharField(max_length=255, blank=True)
    attempt_no = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class DigitalMarketingReportSchedule(models.Model):
    FREQUENCY_CHOICES = (("DAILY", "Daily"), ("WEEKLY", "Weekly"), ("MONTHLY", "Monthly"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="dm_report_schedules")
    name = models.CharField(max_length=120)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="WEEKLY")
    delivery_email = models.EmailField()
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DigitalMarketingReportRun(models.Model):
    schedule = models.ForeignKey(DigitalMarketingReportSchedule, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=20, default="SUCCESS")
    message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DigitalMarketingJob(models.Model):
    STATUS_CHOICES = (("QUEUED", "Queued"), ("RUNNING", "Running"), ("SUCCESS", "Success"), ("FAILED", "Failed"), ("DEAD_LETTER", "Dead Letter"))
    TYPE_CHOICES = (("PUBLISH_POST", "Publish Post"), ("INGEST_LEAD", "Ingest Lead"), ("SEND_REPORT", "Send Report"))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="dm_jobs")
    job_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="QUEUED")
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_error = models.CharField(max_length=255, blank=True)
    run_at = models.DateTimeField(default=models.functions.Now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DigitalMarketingIntegrationSetting(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="dm_integration_setting")
    meta_app_id = models.CharField(max_length=255, blank=True)
    meta_app_secret = models.CharField(max_length=255, blank=True)
    google_client_id = models.CharField(max_length=255, blank=True)
    google_client_secret = models.CharField(max_length=255, blank=True)
    linkedin_client_id = models.CharField(max_length=255, blank=True)
    linkedin_client_secret = models.CharField(max_length=255, blank=True)
    x_api_key = models.CharField(max_length=255, blank=True)
    x_api_secret = models.CharField(max_length=255, blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    webhook_ip_allowlist = models.TextField(blank=True)
    attribution_model = models.CharField(max_length=30, default="LAST_TOUCH")
    enable_auto_publish = models.BooleanField(default=False)
    enable_report_email = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
