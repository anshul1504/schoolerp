from django import forms

from .models import ComplianceInspection, CompliancePolicy, SchoolCertification


class CompliancePolicyForm(forms.ModelForm):
    class Meta:
        model = CompliancePolicy
        fields = ["title", "category", "description", "effective_date", "review_date", "status"]
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "review_date": forms.DateInput(attrs={"type": "date"}),
        }


class ComplianceInspectionForm(forms.ModelForm):
    class Meta:
        model = ComplianceInspection
        fields = [
            "title",
            "inspection_date",
            "inspector_name",
            "related_policy",
            "findings",
            "status",
        ]
        widgets = {
            "inspection_date": forms.DateInput(attrs={"type": "date"}),
        }


class SchoolCertificationForm(forms.ModelForm):
    class Meta:
        model = SchoolCertification
        fields = [
            "name",
            "issuing_authority",
            "issue_date",
            "expiry_date",
            "certificate_number",
            "status",
        ]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }
