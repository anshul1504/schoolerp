from django import forms

from .models import StaffMember


class StaffMemberForm(forms.ModelForm):
    class Meta:
        model = StaffMember
        fields = [
            "full_name",
            "staff_role",
            "employee_id",
            "designation",
            "phone",
            "email",
            "joined_on",
            "is_active",
        ]
