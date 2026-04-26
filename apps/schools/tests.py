from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import EntityChangeLog
from .models import (
    Campus,
    ImplementationProject,
    ImplementationTask,
    PlanFeature,
    School,
    SchoolSubscription,
    SubscriptionInvoice,
    SubscriptionPayment,
    SubscriptionPlan,
)


class SchoolCreateUpdateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
        )

    def test_super_admin_can_create_school(self):
        self.client.force_login(self.super_admin)

        response = self.client.post(
            "/schools/create/",
            data={
                "name": "Beta School",
                "code": "BETA01",
                "email": "beta@example.com",
                "phone": "9999999999",
                "principal_name": "Principal Beta",
                "established_year": 2005,
                "student_capacity": 1000,
                "allowed_campuses": 1,
                "address": "Main road",
                "city": "Bhopal",
                "state": "Madhya Pradesh",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, "/schools/")
        self.assertTrue(School.objects.filter(code="BETA01").exists())

    def test_super_admin_can_update_school(self):
        self.client.force_login(self.super_admin)

        school = School.objects.create(
            name="Gamma School",
            code="GAMMA01",
            email="gamma@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )

        response = self.client.post(
            f"/schools/edit/{school.id}/",
            data={
                "name": "Gamma School Updated",
                "code": "GAMMA01",
                "email": "gamma@example.com",
                "phone": "9999999999",
                "principal_name": "Principal Updated",
                "established_year": 2002,
                "student_capacity": 1000,
                "allowed_campuses": 1,
                "address": "Main road",
                "city": "Bhopal",
                "state": "Madhya Pradesh",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, "/schools/")
        school.refresh_from_db()
        self.assertEqual(school.name, "Gamma School Updated")
        self.assertEqual(school.principal_name, "Principal Updated")
        self.assertEqual(school.established_year, 2002)
        self.assertTrue(EntityChangeLog.objects.filter(entity="schools.School", object_id=str(school.id), action="UPDATED").exists())


class SchoolDeleteTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Alpha School",
            code="ALPHA01",
            email="alpha@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        User = get_user_model()
        self.super_admin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
        )

    def test_school_delete_requires_post(self):
        self.client.force_login(self.super_admin)

        response = self.client.get(f"/schools/delete/{self.school.id}/")

        self.assertRedirects(response, "/schools/")
        self.assertTrue(School.objects.filter(id=self.school.id).exists())

    def test_super_admin_can_delete_school_with_post(self):
        self.client.force_login(self.super_admin)

        response = self.client.post(f"/schools/delete/{self.school.id}/")

        self.assertRedirects(response, "/schools/")
        self.assertFalse(School.objects.filter(id=self.school.id).exists())


class SchoolImportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(username="superadmin_import", password="pass123", role="SUPER_ADMIN")

    def test_school_import_preview_and_confirm_creates_school(self):
        self.client.force_login(self.super_admin)
        csv_text = (
            "name,code,email,phone,support_email,website,principal_name,board,medium,established_year,address,address_line2,city,state,pincode,student_capacity,allowed_campuses,is_active\n"
            "Beta School,BETA01,beta@example.com,9999999999,support@example.com,https://beta.example.com,Principal Beta,CBSE,English,2005,Main road,,Bhopal,Madhya Pradesh,462001,1200,1,yes\n"
        )
        preview = self.client.post("/schools/import/", data={"stage": "preview", "import_file": self._file(csv_text, "schools.csv")})
        self.assertEqual(preview.status_code, 200)
        confirm = self.client.post("/schools/import/", data={"stage": "confirm"})
        self.assertEqual(confirm.status_code, 302)
        self.assertTrue(School.objects.filter(code="BETA01").exists())
        school = School.objects.get(code="BETA01")
        self.assertTrue(Campus.objects.filter(school=school, is_main=True).exists())

    @staticmethod
    def _file(text: str, name: str):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")


class ImplementationTrackerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(username="superadmin_impl", password="pass123", role="SUPER_ADMIN")
        self.school = School.objects.create(
            name="Impl School",
            code="IMPL01",
            email="impl@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )

    def test_super_admin_can_open_and_create_task(self):
        self.client.force_login(self.super_admin)
        page = self.client.get(f"/schools/{self.school.id}/implementation/")
        self.assertEqual(page.status_code, 200)

        create = self.client.post(
            f"/schools/{self.school.id}/implementation/",
            data={"action": "create_task", "title": "Do training", "task_status": "TODO"},
        )
        self.assertEqual(create.status_code, 302)
        project = ImplementationProject.objects.get(school=self.school)
        self.assertTrue(ImplementationTask.objects.filter(project=project, title="Do training").exists())


class SubscriptionFeatureGatingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school = School.objects.create(
            name="Gate School",
            code="GATE01",
            email="gate@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        self.user = User.objects.create_user(username="teacher_gate", password="pass123", role="TEACHER", school=self.school)

        # Create a plan that explicitly excludes STAFF feature.
        PlanFeature.objects.update_or_create(code="STAFF", defaults={"name": "Staff", "description": "", "is_active": True})
        plan = SubscriptionPlan.objects.create(name="NoStaff", code="NOSTAFF", tier="SILVER", max_students=1000, max_campuses=1)
        plan.features.set([])
        SchoolSubscription.objects.update_or_create(
            school=self.school,
            defaults={"plan": plan, "status": "ACTIVE", "starts_on": self.school.created_at.date(), "ends_on": None},
        )

    def test_staff_module_redirects_when_feature_missing(self):
        self.client.force_login(self.user)
        resp = self.client.get("/staff/", follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/subscription/blocked/", resp["Location"])


class BillingEntityChangeLogTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Bill Log School",
            code="BLS01",
            email="bls@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", code="BLP", tier="SILVER", max_students=1000, max_campuses=1)

    def test_invoice_and_payment_create_update_logged(self):
        invoice = SubscriptionInvoice.objects.create(
            school=self.school,
            plan=self.plan,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            amount="100.00",
            status="ISSUED",
        )
        self.assertTrue(EntityChangeLog.objects.filter(entity="schools.SubscriptionInvoice", object_id=str(invoice.id), action="CREATED").exists())

        invoice.status = "PAID"
        invoice.save(update_fields=["status"])
        self.assertTrue(EntityChangeLog.objects.filter(entity="schools.SubscriptionInvoice", object_id=str(invoice.id), action="UPDATED").exists())

        payment = SubscriptionPayment.objects.create(invoice=invoice, amount="100.00", method="UPI", transaction_ref="tx")
        self.assertTrue(EntityChangeLog.objects.filter(entity="schools.SubscriptionPayment", object_id=str(payment.id), action="CREATED").exists())


class AdminSchoolsAccessTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Admin Scoped School",
            code="ADM01",
            email="adm@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        self.other_school = School.objects.create(
            name="Other Scoped School",
            code="ADM02",
            email="adm2@example.com",
            phone="8888888888",
            address="Other road",
            city="Indore",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2005,
            is_active=True,
        )
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin_school", password="pass123", role="ADMIN", school=self.school)

    def test_admin_can_open_school_list_and_profile(self):
        self.client.force_login(self.admin)

        list_response = self.client.get("/schools/")
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Admin Scoped School")
        self.assertNotContains(list_response, "Other Scoped School")

        profile_response = self.client.get("/schools/profile/")
        self.assertEqual(profile_response.status_code, 302)
        self.assertTrue(profile_response.url.endswith(f"/schools/{self.school.id}/"))

    def test_admin_cannot_access_other_school_detail(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/schools/{self.other_school.id}/")
        self.assertIn(response.status_code, {404, 302, 403})

    def test_admin_export_remains_scoped_to_own_school(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/schools/export/csv/?school_ids={self.school.id},{self.other_school.id}")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", errors="ignore")
        self.assertIn("Admin Scoped School", body)
        self.assertNotIn("Other Scoped School", body)


class SchoolOwnerWorkflowAccessTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Owner Main School",
            code="OWN01",
            email="owner-main@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        self.other_school = School.objects.create(
            name="Owner Other School",
            code="OWN02",
            email="owner-other@example.com",
            phone="8888888888",
            address="Other road",
            city="Indore",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2005,
            is_active=True,
        )
        User = get_user_model()
        self.owner = User.objects.create_user(username="school_owner_ops", password="pass123", role="SCHOOL_OWNER", school=self.school)
        self.same_school_user = User.objects.create_user(username="same_school_staff", password="pass123", role="TEACHER", school=self.school)
        self.other_school_user = User.objects.create_user(username="other_school_staff", password="pass123", role="TEACHER", school=self.other_school)

    def test_school_owner_can_update_own_school_profile(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            f"/schools/edit/{self.school.id}/",
            data={
                "name": "Owner Main School Updated",
                "code": "OWN01",
                "email": "owner-main@example.com",
                "phone": "9999999999",
                "principal_name": "Principal Updated",
                "established_year": 2002,
                "student_capacity": 1000,
                "allowed_campuses": 1,
                "address": "Main road",
                "city": "Bhopal",
                "state": "Madhya Pradesh",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.school.refresh_from_db()
        self.assertEqual(self.school.name, "Owner Main School Updated")

    def test_school_owner_cannot_update_other_school(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            f"/schools/edit/{self.other_school.id}/",
            data={
                "name": "Tampered Name",
                "code": "OWN02",
                "email": "owner-other@example.com",
                "phone": "8888888888",
                "principal_name": "Principal",
                "established_year": 2005,
                "student_capacity": 1000,
                "allowed_campuses": 1,
                "address": "Other road",
                "city": "Indore",
                "state": "Madhya Pradesh",
                "is_active": "on",
            },
        )
        self.assertIn(response.status_code, {404, 302, 403})

    def test_school_owner_can_access_implementation_for_own_school(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/schools/{self.school.id}/implementation/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Implementation Tracker")

    def test_implementation_owner_options_are_school_scoped(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/schools/{self.school.id}/implementation/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "same_school_staff")
        self.assertNotContains(response, "other_school_staff")
