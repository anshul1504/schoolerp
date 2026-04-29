import re

from django import forms
from django.conf import settings

from apps.core.upload_validation import DEFAULT_IMAGE_POLICY, UploadPolicy, validate_upload

from .models import Campus, School, SchoolCommunicationSettings


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
            "registration_number",
            "gst_number",
            "cin_number",
            "upi_id",
            "currency",
            "timezone",
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

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            # Simple numeric check with minimum length for international compatibility
            digits_only = re.sub(r"\D", "", phone)
            if len(digits_only) < 7:
                raise forms.ValidationError("Phone number seems too short.")
        return phone

    def clean_gst_number(self):
        gst = self.cleaned_data.get("gst_number")
        if gst:
            gst = gst.upper()
            # Indian GSTIN format check: 2 digits, 10 chars PAN, 1 digit, 1 char, 1 char/digit
            if len(gst) > 0 and not re.match(
                r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d[Z]{1}[A-Z\d]{1}$", gst
            ):
                if (
                    len(gst) == 15
                ):  # if it is 15 chars but doesn't match format exactly, just warn or allow. But let's be strict for Indian format if length is exactly 15 and starts with 2 digits.
                    raise forms.ValidationError("Invalid GST number format.")
        return gst

    def clean_pincode(self):
        pincode = self.cleaned_data.get("pincode")
        if pincode:
            if not re.match(r"^[\d\s-]{4,12}$", pincode):
                raise forms.ValidationError("Invalid pincode format.")
        return pincode

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo:
            return logo
        policy = UploadPolicy(
            max_bytes=int(
                getattr(settings, "MAX_SCHOOL_LOGO_BYTES", DEFAULT_IMAGE_POLICY.max_bytes)
            ),
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
