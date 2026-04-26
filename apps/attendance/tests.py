from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.academics.models import AcademicClass, AcademicSubject
from datetime import date

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan
from apps.students.models import Student
from apps.core.models import EntityChangeLog

from .models import AttendanceSession, StudentAttendance


class AttendanceModuleTests(TestCase):
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
        self.teacher = User.objects.create_user(
            username="teacher",
            password="pass123",
            role="TEACHER",
            school=self.school,
            first_name="Aditi",
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
            class_teacher=self.teacher,
        )
        AcademicSubject.objects.create(
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

    def test_principal_can_open_attendance_overview(self):
        self.client.force_login(self.principal)
        response = self.client.get("/attendance/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daily Class Attendance")

    def test_teacher_can_mark_attendance_for_class(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            "/attendance/",
            {
                "action": "mark_attendance",
                "academic_class": self.academic_class.id,
                "attendance_date": "2026-04-21",
                "student_ids": [self.student.id],
                f"status_{self.student.id}": "LATE",
                f"remark_{self.student.id}": "Bus delay",
                "note": "Traffic on route",
            },
        )

        self.assertEqual(response.status_code, 302)
        session = AttendanceSession.objects.get(academic_class=self.academic_class, attendance_date="2026-04-21")
        entry = StudentAttendance.objects.get(session=session, student=self.student)
        self.assertEqual(entry.status, "LATE")
        self.assertEqual(entry.remark, "Bus delay")

    def test_teacher_can_view_attendance_sheet_for_selected_class(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/attendance/?academic_class={self.academic_class.id}&date=2026-04-21")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.admission_no)
        self.assertContains(response, "Save Attendance")

    def test_attendance_export_does_not_leak_cross_school_sessions(self):
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
            username="teacher2",
            password="pass123",
            role="TEACHER",
            school=other_school,
        )
        other_class = AcademicClass.objects.create(school=other_school, name="Class 5", section="B", class_teacher=other_user)
        AttendanceSession.objects.create(school=other_school, academic_class=other_class, attendance_date="2026-04-21", marked_by=other_user, note="Other note")

        AttendanceSession.objects.create(school=self.school, academic_class=self.academic_class, attendance_date="2026-04-21", marked_by=self.teacher, note="My note")

        self.client.force_login(self.teacher)
        response = self.client.get(f"/attendance/?school={other_school.id}&dataset=sessions&export=csv")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", errors="ignore")
        self.assertIn("My note", body)
        self.assertNotIn("Other note", body)

    def test_superadmin_cannot_mark_attendance_without_selected_school(self):
        User = get_user_model()
        superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.client.force_login(superadmin)
        response = self.client.post(
            "/attendance/",
            {
                "action": "mark_attendance",
                "academic_class": self.academic_class.id,
                "attendance_date": "2026-04-21",
                "student_ids": [self.student.id],
                f"status_{self.student.id}": "PRESENT",
                "note": "Should not save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AttendanceSession.objects.filter(note="Should not save").exists())


class AttendanceEntityChangeLogTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Att Log School",
            code="ALS01",
            email="als@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        User = get_user_model()
        self.teacher = User.objects.create_user(username="teacher_attlog", password="pass123", role="TEACHER", school=self.school)
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        self.academic_class = AcademicClass.objects.create(school=self.school, name="Class 1", section="A", class_teacher=self.teacher)
        self.student = Student.objects.create(
            school=self.school,
            admission_no="A-001",
            academic_year="2026-27",
            first_name="A",
            gender="MALE",
            class_name="Class 1",
            section="A",
            guardian_name="G",
            guardian_phone="9999999999",
            admission_date="2026-04-20",
        )

    def test_session_and_entry_logged(self):
        session = AttendanceSession.objects.create(
            school=self.school,
            academic_class=self.academic_class,
            attendance_date=date(2026, 4, 20),
            marked_by=self.teacher,
        )
        self.assertTrue(EntityChangeLog.objects.filter(entity="attendance.AttendanceSession", object_id=str(session.id), action="CREATED").exists())

        entry = StudentAttendance.objects.create(session=session, student=self.student, status="PRESENT", remark="")
        self.assertTrue(EntityChangeLog.objects.filter(entity="attendance.StudentAttendance", object_id=str(entry.id), action="CREATED").exists())
