from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan
from apps.communication.models import Notice
from apps.core.models import EntityChangeLog

from .models import (
    AdmissionWorkflowEvent,
    Student,
    StudentCommunicationLog,
    StudentComplianceReminder,
    StudentDisciplineIncident,
    StudentClassChangeHistory,
    StudentHealthRecord,
    StudentHistoryEvent,
    StudentProfileEditHistory,
    TransferCertificate,
    TransferCertificateRequest,
)
from .views import _next_class_name, _student_completion_status


class StudentAccessTests(TestCase):
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
            category="General",
            religion="Hindu",
            nationality="Indian",
            relation_with_student="Father",
            current_state="Madhya Pradesh",
            current_city="Bhopal",
            current_pincode="462001",
            permanent_state="Madhya Pradesh",
            permanent_city="Bhopal",
            permanent_pincode="462001",
            emergency_contact="+91 9876543210",
            date_of_birth="2015-01-10",
        )
        self.other_student = Student.objects.create(
            school=self.other_school,
            admission_no="ADM/2026-27/04/0002",
            academic_year="2026-27",
            first_name="Bina",
            gender="FEMALE",
            class_name="Class 5",
            section="A",
            guardian_name="Parent Name",
            guardian_phone="+91 9876543222",
            admission_date="2026-04-20",
            category="General",
            religion="Hindu",
            nationality="Indian",
            relation_with_student="Father",
            current_state="Madhya Pradesh",
            current_city="Indore",
            current_pincode="452001",
            permanent_state="Madhya Pradesh",
            permanent_city="Indore",
            permanent_pincode="452001",
            emergency_contact="+91 9876543222",
            date_of_birth="2015-01-10",
        )

    def test_teacher_list_page_does_not_show_manage_actions(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/students/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View")
        self.assertNotContains(response, "Edit")
        self.assertNotContains(response, "Delete")

    def test_student_list_links_name_and_detail_cells_to_student_view(self):
        self.client.force_login(self.principal)
        response = self.client.get("/students/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="/students/{self.student.slug}/"', count=10)

    def test_student_create_redirects_to_new_student_profile(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            "/students/create/",
            {
                "academic_year": "2026-27",
                "admission_no": "ADM/2026-27/04/0099",
                "first_name": "Riya",
                "last_name": "Verma",
                "gender": "FEMALE",
                "class_name": "Class 4",
                "section": "B",
                "guardian_name": "Sanjay Verma",
                "guardian_phone": "9876543222",
                "relation_with_student": "Father",
                "admission_date": "2026-04-20",
                "date_of_birth": "2016-03-11",
                "category": "General",
                "religion": "Hindu",
                "nationality": "Indian",
                "emergency_contact": "9876543222",
                "current_address_line1": "Street 1",
                "current_city": "Bhopal",
                "current_state": "Madhya Pradesh",
                "current_pincode": "462001",
                "permanent_address_line1": "Street 1",
                "permanent_city": "Bhopal",
                "permanent_state": "Madhya Pradesh",
                "permanent_pincode": "462001",
                "admission_status": "Active",
            },
        )

        created_student = Student.objects.get(admission_no="ADM/2026-27/04/0099")
        self.assertEqual(created_student.student_password, "")
        self.assertEqual(created_student.parent_password, "")
        self.assertTrue(
            StudentHistoryEvent.objects.filter(student=created_student, action="CREATED").exists()
        )
        self.assertRedirects(response, f"/students/{created_student.slug}/")
        self.assertTrue(EntityChangeLog.objects.filter(entity="students.Student", object_id=str(created_student.id), action="CREATED").exists())

    def test_student_detail_shows_audit_timeline_entries(self):
        StudentHistoryEvent.objects.create(
            student=self.student,
            school=self.school,
            actor=self.principal,
            action="UPDATED",
            message="Profile updated.",
        )
        self.client.force_login(self.principal)
        response = self.client.get(f"/students/{self.student.id}/", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Timeline")
        self.assertContains(response, "Profile updated.")

    def test_student_detail_shows_workflow_hub_actions(self):
        self.client.force_login(self.principal)
        response = self.client.get(f"/students/{self.student.id}/", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student Workflow")
        self.assertContains(response, "Operations Control")
        self.assertContains(response, "ERP Snapshot")
        self.assertContains(response, "Passwords are not displayed in ERP screens.")
        self.assertContains(response, f"/students/{self.student.id}/documents/")
        self.assertContains(response, f"/students/id-cards/designer/?student_ids={self.student.id}")

    def test_student_detail_shows_latest_student_notice_in_erp_snapshot(self):
        Notice.objects.create(
            school=self.school,
            title="Exam Schedule",
            body="Exam starts next Monday.",
            audience="STUDENTS",
            priority="NORMAL",
            is_published=True,
            created_by=self.principal,
        )
        self.client.force_login(self.principal)
        response = self.client.get(f"/students/{self.student.id}/", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Latest:")
        self.assertContains(response, "Exam Schedule")

    def test_student_completion_status_marks_incomplete_student(self):
        status = _student_completion_status(self.student)

        self.assertEqual(status["label"], "In Progress")
        self.assertIn("documents", status["missing"])

    def test_student_list_can_filter_complete_workflow_students(self):
        complete_student = Student.objects.create(
            school=self.school,
            admission_no="ADM/2026-27/04/0098",
            academic_year="2026-27",
            first_name="Complete",
            gender="MALE",
            class_name="Class 5",
            section="A",
            guardian_name="Guardian",
            guardian_phone="+91 9999999999",
            relation_with_student="Father",
            admission_date="2026-04-20",
            category="General",
            religion="Hindu",
            nationality="Indian",
            current_state="Madhya Pradesh",
            current_city="Bhopal",
            current_pincode="462001",
            permanent_state="Madhya Pradesh",
            permanent_city="Bhopal",
            permanent_pincode="462001",
            emergency_contact="+91 9999999999",
            date_of_birth="2015-01-10",
            photo="students/photos/sample.png",
            birth_certificate="students/documents/birth.pdf",
        )

        self.client.force_login(self.principal)
        response = self.client.get("/students/?workflow=complete")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete")
        self.assertContains(response, complete_student.admission_no)
        self.assertNotContains(response, self.student.admission_no)

    def test_principal_can_delete_student(self):
        self.client.force_login(self.principal)
        response = self.client.post(f"/students/{self.student.slug}/delete/")

        self.assertRedirects(response, "/students/")
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())
        self.assertTrue(EntityChangeLog.objects.filter(entity="students.Student", object_id=str(self.student.id), action="DELETED").exists())

    def test_teacher_cannot_delete_student(self):
        self.client.force_login(self.teacher)
        response = self.client.post(f"/students/{self.student.id}/delete/")

        self.assertRedirects(response, "/dashboard/")
        self.assertTrue(Student.objects.filter(id=self.student.id).exists())

    def test_teacher_can_download_student_pdf(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/students/{self.student.id}/pdf/", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_principal_dashboard_shows_operational_highlights(self):
        self.client.force_login(self.principal)
        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational Highlights")
        self.assertContains(response, "Attendance Entries")

    def test_next_class_helper_suggests_promotion_class(self):
        self.assertEqual(_next_class_name("Nursery"), "LKG")
        self.assertEqual(_next_class_name("Class 5"), "Class 6")
        self.assertEqual(_next_class_name("Class 12"), "Class 12")

    def test_principal_can_download_tc_pdf_after_generation(self):
        TransferCertificate.objects.create(
            student=self.student,
            certificate_no="TC/202627/0001",
            issue_date="2026-04-20",
            reason="Family relocation",
            destination_school="New School",
            is_issued=True,
        )
        self.client.force_login(self.principal)
        response = self.client.get(f"/students/{self.student.id}/tc/pdf/", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_promotion_creates_history_event(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            f"/students/{self.student.id}/promotion/",
            {
                "to_class": "Class 6",
                "to_section": "A",
                "promoted_on": "2026-04-21",
                "note": "Annual promotion",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.class_name, "Class 6")
        self.assertTrue(StudentHistoryEvent.objects.filter(student=self.student, action="PROMOTED").exists())

    def test_tc_issue_creates_history_event(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            f"/students/{self.student.id}/tc/",
            {
                "certificate_no": "TC/202627/0099",
                "issue_date": "2026-04-21",
                "reason": "Relocation",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.assertTrue(StudentHistoryEvent.objects.filter(student=self.student, action="TC_ISSUED").exists())

    def test_student_workflow_page_can_create_event(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            f"/students/{self.student.slug}/workflow/",
            {"stage": "DOCUMENT_VERIFICATION", "status": "IN_PROGRESS", "note": "Docs under review"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AdmissionWorkflowEvent.objects.filter(
                student=self.student,
                stage="DOCUMENT_VERIFICATION",
                status="IN_PROGRESS",
            ).exists()
        )

    def test_student_history_page_renders_new_phase1_sections(self):
        StudentProfileEditHistory.objects.create(
            student=self.student,
            school=self.school,
            actor=self.principal,
            changed_fields=["guardian_phone"],
            summary="Updated guardian phone",
        )
        StudentClassChangeHistory.objects.create(
            student=self.student,
            school=self.school,
            actor=self.principal,
            from_class="Class 5",
            from_section="A",
            to_class="Class 6",
            to_section="A",
            source="PROMOTION",
        )
        self.client.force_login(self.principal)
        response = self.client.get(f"/students/{self.student.slug}/history/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile Edit History")
        self.assertContains(response, "Class Change History")

    def test_tc_request_create_and_approve_flow(self):
        self.client.force_login(self.principal)
        create_response = self.client.post(
            f"/students/{self.student.slug}/tc/",
            {"action": "request", "reason": "Relocation", "destination_school": "City Public"},
        )
        self.assertEqual(create_response.status_code, 302)
        tc_request = TransferCertificateRequest.objects.filter(student=self.student).first()
        self.assertIsNotNone(tc_request)
        self.assertEqual(tc_request.status, "PENDING")

        approve_response = self.client.post(
            f"/students/{self.student.slug}/tc/requests/",
            {"request_id": str(tc_request.id), "decision": "APPROVED", "review_note": "Approved by principal"},
        )
        self.assertEqual(approve_response.status_code, 302)
        tc_request.refresh_from_db()
        self.assertEqual(tc_request.status, "APPROVED")

    def test_student_discipline_page_can_add_incident(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            f"/students/{self.student.slug}/discipline/",
            {"title": "Class misconduct", "severity": "MEDIUM", "status": "OPEN", "incident_date": "2026-04-21"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StudentDisciplineIncident.objects.filter(student=self.student, title="Class misconduct").exists())

    def test_student_health_page_can_add_record(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            f"/students/{self.student.slug}/health/",
            {"title": "Annual checkup", "record_type": "CHECKUP", "record_date": "2026-04-21"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StudentHealthRecord.objects.filter(student=self.student, title="Annual checkup").exists())

    def test_student_compliance_page_can_add_reminder(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            f"/students/{self.student.slug}/compliance/",
            {"reminder_type": "Aadhar renewal", "status": "PENDING", "due_date": "2026-06-01"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StudentComplianceReminder.objects.filter(student=self.student, reminder_type="Aadhar renewal").exists())

    def test_student_communication_logs_page_can_add_log(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            f"/students/{self.student.slug}/communication-logs/",
            {"channel": "CALL", "subject": "Parent call", "message": "Discussed attendance."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StudentCommunicationLog.objects.filter(student=self.student, channel="CALL").exists())

    def test_student_list_paginates_results(self):
        for index in range(2, 15):
            Student.objects.create(
                school=self.school,
                admission_no=f"ADM/2026-27/04/{index:04d}",
                academic_year="2026-27",
                first_name=f"Student{index}",
                gender="MALE",
                class_name="Class 5",
                section="A",
                guardian_name="Parent Name",
                guardian_phone=f"+91 9000000{index:03d}",
                admission_date="2026-04-20",
                category="General",
                religion="Hindu",
                nationality="Indian",
                relation_with_student="Father",
                current_state="Madhya Pradesh",
                current_city="Bhopal",
                current_pincode="462001",
                permanent_state="Madhya Pradesh",
                permanent_city="Bhopal",
                permanent_pincode="462001",
                emergency_contact=f"+91 9000000{index:03d}",
                date_of_birth="2015-01-10",
            )

        self.client.force_login(self.principal)
        response = self.client.get("/students/?page_size=10&page=2")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")

    def test_principal_can_download_selected_student_id_cards_pdf(self):
        self.client.force_login(self.principal)
        response = self.client.post(
            "/students/id-cards/pdf/",
            {
                "student_ids": [str(self.student.id)],
                "card_size": "CR80",
                "front_primary": "#0f172a",
                "front_secondary": "#2563eb",
                "accent_color": "#f97316",
                "text_color": "#0f172a",
                "back_background": "#111827",
                "back_text_color": "#f8fafc",
                "card_title": "Student Identity Card",
                "footer_text": "If found, return to school office.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_principal_can_open_id_card_designer(self):
        self.client.force_login(self.principal)
        response = self.client.get(f"/students/id-cards/designer/?student_ids={self.student.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student Photo And Print List")
        self.assertContains(response, "Download Print Sheet PDF")

    def test_principal_can_download_import_sample_csv(self):
        self.client.force_login(self.principal)
        response = self.client.get("/students/import/sample/csv/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_principal_can_download_import_sample_excel(self):
        self.client.force_login(self.principal)
        response = self.client.get("/students/import/sample/excel/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")

    def test_students_export_selected_does_not_leak_cross_school_rows(self):
        self.client.force_login(self.principal)
        response = self.client.get(f"/students/?export=csv&student_ids={self.other_student.id},{self.student.id}")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", errors="ignore")
        self.assertIn(self.student.admission_no, body)
        self.assertNotIn(self.other_student.admission_no, body)
