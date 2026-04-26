from django import forms
from django.conf import settings

from .models import Campus, School, SchoolCommunicationSettings
from apps.core.upload_validation import DEFAULT_IMAGE_POLICY, UploadPolicy, validate_upload


class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = [
            "name",
            "code",
            "email",
            "phone",
            "support_email",
            "website",
            "address",
            "address_line2",
            "city",
            "state",
            "pincode",
            "principal_name",
            "board",
            "medium",
            "established_year",
            "student_capacity",
            "allowed_campuses",
            "logo",
            "is_active",
        ]

    def clean_established_year(self):
        year = self.cleaned_data.get("established_year")
        if year is None:
            return year
        if year < 1800 or year > 2200:
            raise forms.ValidationError("Established year looks invalid.")
        return year

    def clean_allowed_campuses(self):
        value = self.cleaned_data.get("allowed_campuses")
        if value is None:
            return value
        if value < 1:
            raise forms.ValidationError("Allowed campuses must be at least 1.")
        return value

    def clean_student_capacity(self):
        value = self.cleaned_data.get("student_capacity")
        if value is None:
            return value
        if value < 1:
            raise forms.ValidationError("Student capacity must be at least 1.")
        return value

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo:
            return logo
        policy = UploadPolicy(
            max_bytes=int(getattr(settings, "MAX_SCHOOL_LOGO_BYTES", DEFAULT_IMAGE_POLICY.max_bytes)),
            allowed_extensions=DEFAULT_IMAGE_POLICY.allowed_extensions,
            allowed_image_formats=DEFAULT_IMAGE_POLICY.allowed_image_formats,
        )
        errors = validate_upload(logo, policy=policy, kind="School logo")
        if errors:
            raise forms.ValidationError(errors[0])
        return logo


class SchoolCommunicationSettingsForm(forms.ModelForm):
    class Meta:
        model = SchoolCommunicationSettings
        exclude = ["school", "created_at", "updated_at"]


class SchoolTeamInviteForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(
        choices=[
            ("PRINCIPAL", "Principal"),
            ("TEACHER", "Teacher"),
            ("ACCOUNTANT", "Accountant"),
            ("RECEPTIONIST", "Receptionist"),
        ]
    )


class CampusForm(forms.ModelForm):
    class Meta:
        model = Campus
        fields = [
            "name",
            "code",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "pincode",
            "is_main",
            "is_active",
        ]
