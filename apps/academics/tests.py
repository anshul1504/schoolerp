from django.contrib.auth import get_user_model
from django.test import TestCase

from datetime import date

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan
from apps.core.models import EntityChangeLog

from .models import AcademicClass, AcademicSubject, AcademicYear, TeacherAllocation


class AcademicsModuleTests(TestCase):
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
        self.teacher = User.objects.create_user(
            username="teacher",
            password="pass123",
            role="TEACHER",
            school=self.school,
            first_name="Aditi",
            last_name="Sharma",
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
            SchoolSubscription.objects.update_or_create(
                school=self.other_school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )

    def test_principal_can_open_academics_overview(self):
        self.client.force_login(self.principal)
        response = self.client.get("/academics/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Classes, Subjects, And Teacher Allocation")

    def test_principal_can_create_class_subject_and_teacher_allocation(self):
        self.client.force_login(self.principal)
        class_response = self.client.post(
            "/academics/",
            {
                "action": "create_class",
                "name": "Class 6",
                "section": "A",
                "class_teacher": self.teacher.id,
                "room_name": "Room 12",
                "capacity": 35,
            },
        )
        self.assertEqual(class_response.status_code, 302)

        academic_class = AcademicClass.objects.get(name="Class 6", section="A")
        subject_response = self.client.post(
            "/academics/",
            {
                "action": "create_subject",
                "academic_class": academic_class.id,
                "name": "Mathematics",
                "code": "MATH-6A",
            },
        )
        self.assertEqual(subject_response.status_code, 302)

        subject = AcademicSubject.objects.get(name="Mathematics")
        allocation_response = self.client.post(
            "/academics/",
            {
                "action": "create_allocation",
                "teacher": self.teacher.id,
                "academic_class": academic_class.id,
                "subject": subject.id,
                "is_class_lead": "on",
            },
        )
        self.assertEqual(allocation_response.status_code, 302)
        self.assertTrue(TeacherAllocation.objects.filter(teacher=self.teacher, academic_class=academic_class, subject=subject).exists())

    def test_teacher_can_view_but_not_manage_academics(self):
        AcademicClass.objects.create(school=self.school, name="Class 7", section="B")
        self.client.force_login(self.teacher)
        response = self.client.get("/academics/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Class 7 - B")
        self.assertNotContains(response, "Create Class")

    def test_academics_export_selected_does_not_leak_cross_school(self):
        c1 = AcademicClass.objects.create(school=self.school, name="Class 5", section="A")
        c2 = AcademicClass.objects.create(school=self.other_school, name="Class 5", section="B")
        s1 = AcademicSubject.objects.create(school=self.school, academic_class=c1, name="Mathematics", code="MATH")
        s2 = AcademicSubject.objects.create(school=self.other_school, academic_class=c2, name="Other", code="OTH")

        self.client.force_login(self.principal)
        class_export = self.client.get(f"/academics/export/csv/?school={self.other_school.id}&dataset=classes&class_ids={c1.id},{c2.id}")
        self.assertEqual(class_export.status_code, 200)
        body = class_export.content.decode("utf-8", errors="ignore")
        self.assertIn("Class 5", body)
        self.assertIn("A", body)
        self.assertNotIn("B", body)

        subject_export = self.client.get(f"/academics/export/csv/?school={self.other_school.id}&dataset=subjects&subject_ids={s1.id},{s2.id}")
        self.assertEqual(subject_export.status_code, 200)
        body = subject_export.content.decode("utf-8", errors="ignore")
        self.assertIn("Mathematics", body)
        self.assertNotIn("Other", body)


class AcademicsEntityChangeLogTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Acad Log School",
            code="ACLS01",
            email="acls@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )

    def test_academic_year_create_logged(self):
        year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_current=True,
        )
        self.assertTrue(EntityChangeLog.objects.filter(entity="academics.AcademicYear", object_id=str(year.id), action="CREATED").exists())
