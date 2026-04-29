from django import forms

from .models import (
    DigitalMarketingIntegrationSetting,
    DigitalMarketingReportSchedule,
    MarketingCampaign,
    MarketingLead,
    SEOTracker,
    SocialAccountConnection,
    SocialPost,
    WebsiteFormIntegration,
)


class MarketingCampaignForm(forms.ModelForm):
    class Meta:
        model = MarketingCampaign
        fields = [
            "name",
            "channel",
            "objective",
            "start_date",
            "end_date",
            "budget",
            "spent",
            "status",
            "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css


class MarketingLeadForm(forms.ModelForm):
    class Meta:
        model = MarketingLead
        fields = [
            "campaign",
            "student_name",
            "guardian_name",
            "phone",
            "email",
            "class_interest",
            "source",
            "stage",
            "expected_revenue",
            "next_followup_on",
        ]
        widgets = {
            "next_followup_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css


class SocialAccountConnectionForm(forms.ModelForm):
    class Meta:
        model = SocialAccountConnection
        fields = ["platform", "handle", "profile_url", "access_token", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css


class SocialPostForm(forms.ModelForm):
    class Meta:
        model = SocialPost
        fields = [
            "campaign",
            "account",
            "title",
            "caption",
            "scheduled_at",
            "published_at",
            "status",
            "reach",
            "clicks",
            "leads_generated",
        ]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css


class WebsiteFormIntegrationForm(forms.ModelForm):
    class Meta:
        model = WebsiteFormIntegration
        fields = [
            "name",
            "website_url",
            "endpoint_url",
            "auth_key",
            "source_label",
            "field_mapping",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css
        self.fields[
            "field_mapping"
        ].help_text = (
            'JSON mapping like {"student_name":"full_name","phone":"mobile","email":"email_id"}'
        )


class SEOTrackerForm(forms.ModelForm):
    class Meta:
        model = SEOTracker
        fields = [
            "page_url",
            "keyword",
            "ranking_position",
            "impressions",
            "clicks",
            "ctr_percent",
            "audit_notes",
            "tracked_on",
        ]
        widgets = {
            "tracked_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css


class DigitalMarketingReportScheduleForm(forms.ModelForm):
    class Meta:
        model = DigitalMarketingReportSchedule
        fields = ["name", "frequency", "delivery_email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css


class DigitalMarketingIntegrationSettingForm(forms.ModelForm):
    class Meta:
        model = DigitalMarketingIntegrationSetting
        fields = [
            "meta_app_id",
            "meta_app_secret",
            "google_client_id",
            "google_client_secret",
            "linkedin_client_id",
            "linkedin_client_secret",
            "x_api_key",
            "x_api_secret",
            "webhook_secret",
            "webhook_ip_allowlist",
            "attribution_model",
            "enable_auto_publish",
            "enable_report_email",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            field.widget.attrs["class"] = css
