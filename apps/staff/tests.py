from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan

from .models import StaffMember


class StaffExportTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            code="TS01",
            email="school@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        self.other_school = School.objects.create(
            name="Other School",
            code="OS01",
            email="other@example.com",
            phone="8888888888",
            address="Other road",
            city="Indore",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2005,
            is_active=True,
        )
        User = get_user_model()
        self.principal = User.objects.create_user(
            username="principal",
            password="pass123",
            role="PRINCIPAL",
            school=self.school,
        )
        plan = (
            SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first()
            or SubscriptionPlan.objects.first()
        )
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={
                    "plan": plan,
                    "status": "ACTIVE",
                    "starts_on": date(2026, 4, 1),
                    "ends_on": None,
                },
            )
            SchoolSubscription.objects.update_or_create(
                school=self.other_school,
                defaults={
                    "plan": plan,
                    "status": "ACTIVE",
                    "starts_on": date(2026, 4, 1),
                    "ends_on": None,
                },
            )

        self.staff = StaffMember.objects.create(
            school=self.school,
            full_name="Aditi Sharma",
            staff_role="TEACHER",
            employee_id="EMP-01",
            email="aditi@example.com",
            is_active=True,
        )
        self.other_staff = StaffMember.objects.create(
            school=self.other_school,
            full_name="Other Person",
            staff_role="STAFF",
            employee_id="EMP-02",
            email="other@example.com",
            is_active=True,
        )

    def test_staff_export_selected_does_not_leak_cross_school(self):
        self.client.force_login(self.principal)
        response = self.client.get(
            f"/staff/export/csv/?school={self.other_school.id}&staff_ids={self.staff.id},{self.other_staff.id}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", errors="ignore")
        self.assertIn("Aditi Sharma", body)
        self.assertNotIn("Other Person", body)
