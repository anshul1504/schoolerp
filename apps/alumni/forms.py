from django import forms

from .models import Alumni, AlumniEvent, SuccessStory


class AlumniForm(forms.ModelForm):
    class Meta:
        model = Alumni
        fields = [
            "student",
            "full_name",
            "graduation_year",
            "batch",
            "current_occupation",
            "current_organization",
            "location",
            "email",
            "phone",
            "linkedin_profile",
            "is_verified",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "graduation_year": forms.NumberInput(attrs={"class": "form-control"}),
            "batch": forms.TextInput(attrs={"class": "form-control"}),
            "current_occupation": forms.TextInput(attrs={"class": "form-control"}),
            "current_organization": forms.TextInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "linkedin_profile": forms.URLInput(attrs={"class": "form-control"}),
            "is_verified": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AlumniEventForm(forms.ModelForm):
    class Meta:
        model = AlumniEvent
        fields = ["title", "description", "date", "location", "poster"]
        widgets = {
            "date": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "poster": forms.FileInput(attrs={"class": "form-control"}),
        }


class SuccessStoryForm(forms.ModelForm):
    class Meta:
        model = SuccessStory
        fields = ["alumni", "title", "content", "image", "is_featured"]
        widgets = {
            "alumni": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "image": forms.FileInput(attrs={"class": "form-control"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
