from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import EntityChangeLog
from apps.schools.models import School, SchoolSubscription, SubscriptionPlan
from apps.students.models import Student

from .models import FeePayment, FeeStructure, StudentFeeLedger


class FeesModuleTests(TestCase):
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
        self.accountant = User.objects.create_user(
            username="accountant",
            password="pass123",
            role="ACCOUNTANT",
            school=self.school,
        )
        self.owner = User.objects.create_user(
            username="owner",
            password="pass123",
            role="SCHOOL_OWNER",
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
        )

    def test_accountant_can_open_fees_overview(self):
        self.client.force_login(self.accountant)
        response = self.client.get("/fees/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fee Structures, Dues, And Collections")

    def test_accountant_can_create_structure_due_and_payment(self):
        self.client.force_login(self.accountant)
        structure_response = self.client.post(
            "/fees/",
            {
                "action": "create_structure",
                "name": "Tuition Fee",
                "class_name": "Class 5",
                "amount": "2500",
                "frequency": "MONTHLY",
                "due_day": "10",
            },
        )
        self.assertEqual(structure_response.status_code, 302)
        structure = FeeStructure.objects.get(name="Tuition Fee")

        due_response = self.client.post(
            "/fees/",
            {
                "action": "create_due",
                "student": self.student.id,
                "fee_structure": structure.id,
                "billing_month": "Apr-2026",
                "due_date": "2026-04-10",
                "amount_due": "2500",
            },
        )
        self.assertEqual(due_response.status_code, 302)
        ledger = StudentFeeLedger.objects.get(student=self.student, billing_month="Apr-2026")

        payment_response = self.client.post(
            "/fees/",
            {
                "action": "collect_payment",
                "ledger": ledger.id,
                "amount": "2500",
                "payment_date": "2026-04-11",
                "payment_mode": "ONLINE",
                "reference_no": "PAY123",
            },
        )
        self.assertEqual(payment_response.status_code, 302)
        ledger.refresh_from_db()
        self.assertEqual(ledger.status, "PAID")
        self.assertTrue(FeePayment.objects.filter(ledger=ledger, amount="2500").exists())

    def test_fees_export_does_not_leak_cross_school_rows(self):
        FeeStructure.objects.create(
            school=self.school,
            name="Tuition Fee",
            class_name="Class 5",
            amount="2500",
            frequency="MONTHLY",
            due_day=10,
        )
        FeeStructure.objects.create(
            school=self.other_school,
            name="Other Fee",
            class_name="Class 5",
            amount="999",
            frequency="MONTHLY",
            due_day=10,
        )

        ledger1 = StudentFeeLedger.objects.create(
            school=self.school,
            student=self.student,
            fee_structure=FeeStructure.objects.filter(school=self.school).first(),
            billing_month="Apr-2026",
            amount_due="2500",
            amount_paid="0",
            due_date="2026-04-10",
            status="DUE",
        )
        StudentFeeLedger.objects.create(
            school=self.other_school,
            student=self.other_student,
            fee_structure=FeeStructure.objects.filter(school=self.other_school).first(),
            billing_month="Apr-2026",
            amount_due="999",
            amount_paid="0",
            due_date="2026-04-10",
            status="DUE",
        )

        self.client.force_login(self.accountant)
        response = self.client.get(
            f"/fees/?school={self.other_school.id}&dataset=ledgers&export=csv"
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", errors="ignore")
        self.assertIn(str(ledger1.id), body)
        self.assertIn("Tuition Fee", body)
        self.assertNotIn("Other Fee", body)
        self.assertNotIn(self.other_student.admission_no, body)

    def test_school_owner_cannot_export_fees_even_with_direct_url(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/fees/?school={self.school.id}&dataset=ledgers&export=csv")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/fees/")

    def test_school_owner_cannot_tamper_school_scope_in_fees_page(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/fees/?school={self.other_school.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_school"].id, self.school.id)

    def test_create_structure_rejects_invalid_amount(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            "/fees/",
            {
                "action": "create_structure",
                "name": "Broken Fee",
                "class_name": "Class 5",
                "amount": "abc",
                "frequency": "MONTHLY",
                "due_day": "10",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            FeeStructure.objects.filter(name="Broken Fee", school=self.school).exists()
        )

    def test_create_due_rejects_non_numeric_amount_due(self):
        self.client.force_login(self.owner)
        structure = FeeStructure.objects.create(
            school=self.school,
            name="Tuition Fee",
            class_name="Class 5",
            amount="2500",
            frequency="MONTHLY",
            due_day=10,
        )
        response = self.client.post(
            "/fees/",
            {
                "action": "create_due",
                "student": self.student.id,
                "fee_structure": structure.id,
                "billing_month": "Apr-2026",
                "due_date": "2026-04-10",
                "amount_due": "bad-number",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            StudentFeeLedger.objects.filter(student=self.student, billing_month="Apr-2026").exists()
        )


class FeesEntityChangeLogTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Fees Log School",
            code="FLS01",
            email="fls@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        User = get_user_model()
        self.accountant = User.objects.create_user(
            username="accountant_log", password="pass123", role="ACCOUNTANT", school=self.school
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
        self.student = Student.objects.create(
            school=self.school,
            admission_no="F-001",
            academic_year="2026-27",
            first_name="A",
            gender="MALE",
            class_name="Class 1",
            section="A",
            guardian_name="G",
            guardian_phone="9999999999",
            admission_date="2026-04-20",
        )
        self.structure = FeeStructure.objects.create(
            school=self.school,
            name="Tuition",
            class_name="Class 1",
            amount="100.00",
            frequency="MONTHLY",
            due_day=10,
        )

    def test_ledger_and_payment_logged(self):
        ledger = StudentFeeLedger.objects.create(
            school=self.school,
            student=self.student,
            fee_structure=self.structure,
            billing_month="Apr-2026",
            amount_due="100.00",
            amount_paid="0",
            due_date="2026-04-10",
            status="DUE",
        )
        self.assertTrue(
            EntityChangeLog.objects.filter(
                entity="fees.StudentFeeLedger", object_id=str(ledger.id), action="CREATED"
            ).exists()
        )

        payment = FeePayment.objects.create(
            ledger=ledger,
            school=self.school,
            student=self.student,
            amount="50.00",
            payment_date=date(2026, 4, 5),
            payment_mode="CASH",
            collected_by=self.accountant,
        )
        self.assertTrue(
            EntityChangeLog.objects.filter(
                entity="fees.FeePayment", object_id=str(payment.id), action="CREATED"
            ).exists()
        )
