from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.academics.models import AcademicClass, AcademicSubject
from datetime import date

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan
from apps.students.models import Student

from .models import Exam, ExamMark


class ExamsModuleTests(TestCase):
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
        User = get_user_model()
        self.principal = User.objects.create_user(
            username="principal",
            password="pass123",
            role="PRINCIPAL",
            school=self.school,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        self.academic_class = AcademicClass.objects.create(
            school=self.school,
            name="Class 5",
            section="A",
        )
        self.subject = AcademicSubject.objects.create(
            school=self.school,
            academic_class=self.academic_class,
            name="Mathematics",
        )
        self.student = Student.objects.create(
            school=self.school,
            admission_no="ADM/2026-27/04/0001",
            academic_year="2026-27",
            first_name="Aman",
            gender="MALE",
            class_name="Class 5",
            section="A",
            guardian_name="Parent Name",
            guardian_phone="+91 9876543210",
            admission_date="2026-04-20",
        )

    def test_principal_can_open_exams_overview(self):
        self.client.force_login(self.principal)
        response = self.client.get("/exams/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exams, Subjects, And Marks Entry")

    def test_principal_can_create_exam_and_save_marks(self):
        self.client.force_login(self.principal)
        create_response = self.client.post(
            "/exams/",
            {
                "action": "create_exam",
                "academic_class": self.academic_class.id,
                "name": "Unit Test 1",
                "exam_date": "2026-04-25",
                "total_marks": "100",
                "passing_marks": "33",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        exam = Exam.objects.get(name="Unit Test 1")

        marks_response = self.client.post(
            "/exams/",
            {
                "action": "save_marks",
                "exam": exam.id,
                f"marks_{self.student.id}_{self.subject.id}": "78",
                f"remark_{self.student.id}_{self.subject.id}": "Good work",
            },
        )
        self.assertEqual(marks_response.status_code, 302)
        self.assertTrue(ExamMark.objects.filter(exam=exam, student=self.student, subject=self.subject, marks_obtained="78").exists())

    def test_exam_marks_export_rejects_cross_school_exam_id(self):
        other_school = School.objects.create(
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
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=other_school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        other_user = get_user_model().objects.create_user(
            username="principal2",
            password="pass123",
            role="PRINCIPAL",
            school=other_school,
        )
        other_class = AcademicClass.objects.create(school=other_school, name="Class 5", section="B")
        other_exam = Exam.objects.create(
            school=other_school,
            name="Other Exam",
            academic_class=other_class,
            exam_date="2026-04-25",
            total_marks="100",
            passing_marks="33",
            created_by=other_user,
        )

        self.client.force_login(self.principal)
        response = self.client.get(f"/exams/?exam={other_exam.id}&dataset=marks&export=csv")
        self.assertIn(response.status_code, {302, 400})

    def test_superadmin_cannot_create_exam_without_selected_school(self):
        User = get_user_model()
        superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.client.force_login(superadmin)
        response = self.client.post(
            "/exams/",
            {
                "action": "create_exam",
                "academic_class": self.academic_class.id,
                "name": "Should Not Create",
                "exam_date": "2026-04-25",
                "total_marks": "100",
                "passing_marks": "33",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Exam.objects.filter(name="Should Not Create").exists())

    def test_exam_marks_export_selected_students_filters_output(self):
        self.client.force_login(self.principal)
        exam = Exam.objects.create(
            school=self.school,
            name="Export Exam",
            academic_class=self.academic_class,
            exam_date="2026-04-25",
            total_marks="100",
            passing_marks="33",
            created_by=self.principal,
        )
        other_student = Student.objects.create(
            school=self.school,
            admission_no="ADM/2026-27/04/0002",
            academic_year="2026-27",
            first_name="Bina",
            gender="FEMALE",
            class_name="Class 5",
            section="A",
            guardian_name="Parent Name",
            guardian_phone="+91 9876543222",
            admission_date="2026-04-20",
        )
        ExamMark.objects.create(exam=exam, student=self.student, subject=self.subject, marks_obtained="78", remark="")
        ExamMark.objects.create(exam=exam, student=other_student, subject=self.subject, marks_obtained="55", remark="")

        response = self.client.get(f"/exams/?school={self.school.id}&exam={exam.id}&dataset=marks&export=csv&student_ids={self.student.id}")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", errors="ignore")
        self.assertIn(self.student.admission_no, body)
        self.assertNotIn(other_student.admission_no, body)
