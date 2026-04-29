from django import forms

from apps.career_counseling.models import (
    Application,
    CareerEvent,
    CareerProfile,
    CounselingSession,
    EventRegistration,
    University,
)
from apps.students.models import Student


class CounselingSessionForm(forms.ModelForm):
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 5}),
        help_text="Select one or more students for the session (Hold Ctrl/Cmd to select multiple).",
    )

    class Meta:
        model = CounselingSession
        fields = [
            "session_type",
            "mode",
            "meeting_link",
            "scheduled_at",
            "duration_minutes",
            "summary",
            "follow_up_required",
            "is_completed",
        ]
        widgets = {
            "scheduled_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "session_type": forms.Select(attrs={"class": "form-select"}),
            "mode": forms.Select(attrs={"class": "form-select"}),
            "meeting_link": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "e.g. https://zoom.us/j/12345"}
            ),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "summary": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "follow_up_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_completed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop("school", None)
        super().__init__(*args, **kwargs)
        if school:
            self.fields["students"].queryset = Student.objects.filter(school=school)


class CareerProfileForm(forms.ModelForm):
    class Meta:
        model = CareerProfile
        fields = [
            "target_exams",
            "interests",
            "preferred_universities",
            "preferred_courses",
            "notes",
        ]
        widgets = {
            "target_exams": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. JEE, NEET, SAT"}
            ),
            "interests": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "General career interests...",
                }
            ),
            "preferred_universities": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "preferred_courses": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Confidential counselor notes...",
                }
            ),
        }


class UniversityForm(forms.ModelForm):
    class Meta:
        model = University
        fields = ["name", "location", "website", "is_abroad"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
            "is_abroad": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["university", "course", "status", "applied_on", "deadline", "notes"]
        widgets = {
            "university": forms.Select(attrs={"class": "form-select"}),
            "course": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "applied_on": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "deadline": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop("school", None)
        super().__init__(*args, **kwargs)
        if school:
            self.fields["university"].queryset = University.objects.filter(school=school)


class CareerEventForm(forms.ModelForm):
    class Meta:
        model = CareerEvent
        fields = ["title", "event_type", "date", "location", "description", "organizer"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "event_type": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "organizer": forms.TextInput(attrs={"class": "form-control"}),
        }


class EventRegistrationForm(forms.ModelForm):
    class Meta:
        model = EventRegistration
        fields = ["student", "attended"]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "attended": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop("school", None)
        super().__init__(*args, **kwargs)
        if school:
            self.fields["student"].queryset = Student.objects.filter(school=school)
