from django import forms

from .models import EthicsReview, Grant, ResearchPaper, ResearchProject


class ResearchProjectForm(forms.ModelForm):
    class Meta:
        model = ResearchProject
        fields = ["title", "description", "pi", "status", "budget", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "pi": forms.Select(attrs={"class": "form-select"}),
            "budget": forms.NumberInput(attrs={"class": "form-control"}),
        }


class ResearchPaperForm(forms.ModelForm):
    class Meta:
        model = ResearchPaper
        fields = ["title", "journal", "publication_date", "doi", "link"]
        widgets = {
            "publication_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "journal": forms.TextInput(attrs={"class": "form-control"}),
            "doi": forms.TextInput(attrs={"class": "form-control"}),
            "link": forms.URLInput(attrs={"class": "form-control"}),
        }


class GrantForm(forms.ModelForm):
    class Meta:
        model = Grant
        fields = ["grant_id", "agency", "amount", "received_date"]
        widgets = {
            "received_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "grant_id": forms.TextInput(attrs={"class": "form-control"}),
            "agency": forms.TextInput(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
        }


class EthicsReviewForm(forms.ModelForm):
    class Meta:
        model = EthicsReview
        fields = ["status", "comments"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "comments": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }
