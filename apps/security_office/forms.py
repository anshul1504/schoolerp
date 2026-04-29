from django import forms

from .models import GatePass, GuardRoster, PatrolCheckpointLog, SecurityIncident, VisitorEntry


class _StyledModelForm(forms.ModelForm):
    def _style_fields(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = (
                    "form-select" if isinstance(field.widget, forms.Select) else "form-control"
                )


class SecurityIncidentForm(_StyledModelForm):
    class Meta:
        model = SecurityIncident
        fields = [
            "title",
            "incident_type",
            "severity",
            "status",
            "location",
            "description",
            "reported_at",
            "resolved_at",
        ]
        widgets = {
            "reported_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "resolved_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class VisitorEntryForm(_StyledModelForm):
    class Meta:
        model = VisitorEntry
        fields = [
            "name",
            "phone",
            "purpose",
            "person_to_meet",
            "check_in_at",
            "check_out_at",
            "is_verified",
        ]
        widgets = {
            "check_in_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "check_out_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class GuardRosterForm(_StyledModelForm):
    class Meta:
        model = GuardRoster
        fields = ["guard_name", "shift", "area", "duty_date", "is_active"]
        widgets = {"duty_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class GatePassForm(_StyledModelForm):
    class Meta:
        model = GatePass
        fields = [
            "pass_type",
            "person_name",
            "reason",
            "issued_at",
            "valid_till",
            "status",
            "issued_by",
        ]
        widgets = {
            "issued_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "valid_till": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PatrolCheckpointLogForm(_StyledModelForm):
    class Meta:
        model = PatrolCheckpointLog
        fields = ["checkpoint_name", "guard_name", "logged_at", "status_note", "is_alert"]
        widgets = {"logged_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
