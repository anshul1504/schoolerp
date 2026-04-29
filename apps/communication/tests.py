from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan

from .models import Notice


class CommunicationModuleTests(TestCase):
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
        self.student_user = User.objects.create_user(
            username="studentuser",
            password="pass123",
            role="STUDENT",
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

    def test_principal_can_publish_notice(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            "/communication/",
            {
                "title": "Holiday Notice",
                "audience": "ALL",
                "priority": "IMPORTANT",
                "body": "School will remain closed tomorrow.",
                "is_published": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Notice.objects.filter(title="Holiday Notice", school=self.school).exists())

    def test_student_can_view_matching_notice_feed(self):
        notice = Notice.objects.create(
            school=self.school,
            title="Exam Schedule",
            body="Exam starts next Monday.",
            audience="STUDENTS",
            priority="NORMAL",
            is_published=True,
            created_by=self.principal,
        )
        self.client.force_login(self.student_user)
        response = self.client.get("/communication/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, notice.title)

    def test_student_can_open_notice_detail(self):
        notice = Notice.objects.create(
            school=self.school,
            title="Exam Schedule",
            body="Exam starts next Monday.",
            audience="STUDENTS",
            priority="NORMAL",
            is_published=True,
            created_by=self.principal,
        )
        self.client.force_login(self.student_user)
        response = self.client.get(f"/communication/{notice.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exam starts next Monday.")

    def test_notice_export_selected_does_not_leak_cross_school(self):
        n1 = Notice.objects.create(
            school=self.school,
            title="In School",
            body="Body",
            audience="ALL",
            priority="NORMAL",
            is_published=True,
            created_by=self.principal,
        )
        n2 = Notice.objects.create(
            school=self.other_school,
            title="Other School Notice",
            body="Body",
            audience="ALL",
            priority="NORMAL",
            is_published=True,
            created_by=self.principal,
        )
        self.client.force_login(self.principal)
        response = self.client.get(f"/communication/export/csv/?notice_ids={n1.id},{n2.id}")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", errors="ignore")
        self.assertIn("In School", body)
        self.assertNotIn("Other School Notice", body)
