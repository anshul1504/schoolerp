from datetime import date
from decimal import Decimal
import json
import hashlib
import hmac
import time
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan
from apps.core.models import ScheduledReport
from apps.core.models import ActivityLog
from apps.core.models import EntityChangeLog
from apps.core.models import AuditLogExport
from apps.core.models import PlatformAnnouncement
from apps.core.models import SupportTicket
from apps.core.models import AuthSecurityEvent
from apps.core.models import ReportTemplate
from apps.students.models import Student
from apps.schools.models import SubscriptionInvoice, SubscriptionPayment
from apps.schools.models import SchoolDomain
from apps.schools.models import SubscriptionCoupon
from apps.core.models import IntegrationToken
from apps.core.models import RBACChangeEvent, RolePermissionsOverride, RoleSectionsOverride
from apps.core.models import TwoFactorPolicy
from apps.core.models import SupportTicket
from apps.core.models import (
    TransportRoute,
    TransportAssignment,
    HostelRoom,
    HostelAllocation,
    LibraryBook,
    LibraryIssue,
    InventoryItem,
    InventoryMovement,
    InventoryVendor,
    InventoryPurchaseOrder,
    ServiceRefundEvent,
)
from apps.fees.models import FeeStructure, StudentFeeLedger
from apps.core.upload_validation import DEFAULT_IMAGE_POLICY, UploadPolicy, validate_upload
from apps.core.upload_validation import DEFAULT_DOCUMENT_POLICY


class ReportsOverviewTests(TestCase):
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

    def test_principal_can_open_reports_overview(self):
        self.client.force_login(self.principal)
        response = self.client.get("/reports/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational Reports Overview")
        self.assertContains(response, "Leadership Summary")

    def test_user_without_school_gets_scoped_zero_metrics(self):
        User = get_user_model()
        principal = User.objects.create_user(
            username="principal_no_school",
            password="pass123",
            role="PRINCIPAL",
            school=None,
        )
        self.client.force_login(principal)
        response = self.client.get("/reports/")
        # Depending on instance policy, a user without a school may be redirected,
        # but must never see cross-school (unscoped) aggregates.
        if response.status_code == 200:
            metrics = response.context.get("report_metrics") or []
            schools_metric = next((m for m in metrics if m.get("label") == "Schools"), None)
            self.assertIsNotNone(schools_metric)
            self.assertEqual(schools_metric.get("value"), 0)
        else:
            self.assertIn(response.status_code, {302, 403})


class UsersExportsAccessTests(TestCase):
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

    def test_non_superadmin_cannot_access_users_export(self):
        self.client.force_login(self.principal)
        response = self.client.get("/users/export/csv/")
        self.assertIn(response.status_code, {302, 403})


class UsersBulkActionsTests(TestCase):
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
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.user = User.objects.create_user(
            username="user1",
            password="pass123",
            role="TEACHER",
            school=self.school,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )

    def test_bulk_action_never_applies_to_self(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(
            "/users/bulk-action/",
            {"action": "deactivate", "user_ids": f"{self.superadmin.id},{self.user.id}"},
        )
        self.assertEqual(response.status_code, 302)
        self.superadmin.refresh_from_db()
        self.user.refresh_from_db()
        self.assertTrue(self.superadmin.is_active)
        self.assertFalse(self.user.is_active)


class PlatformSecurityAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.student = User.objects.create_user(
            username="student",
            password="pass123",
            role="STUDENT",
            school=None,
        )

    def test_superadmin_can_open_platform_security(self):
        self.client.force_login(self.superadmin)
        response = self.client.get("/platform/security/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform Security")

    def test_non_superadmin_cannot_open_platform_security(self):
        self.client.force_login(self.student)
        response = self.client.get("/platform/security/")
        self.assertIn(response.status_code, {302, 403})


class ScheduledReportsRunNowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.report = ScheduledReport.objects.create(
            name="Test Activity Export",
            report_type="ACTIVITY",
            frequency="WEEKLY",
            recipients="ops@example.com",
            is_active=True,
        )

    def test_superadmin_can_trigger_run_now(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(f"/reports/scheduled/{self.report.id}/run/")
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertIsNotNone(self.report.last_run_at)
        self.assertIsNotNone(self.report.next_run_at)


class ImpersonationFlowTests(TestCase):
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
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.teacher = User.objects.create_user(
            username="teacher1",
            password="pass123",
            role="TEACHER",
            school=self.school,
        )

    def test_superadmin_can_impersonate_and_stop(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(f"/users/{self.teacher.id}/impersonate/")
        self.assertEqual(response.status_code, 302)
        response2 = self.client.get("/dashboard/", follow=True)
        self.assertEqual(response2.wsgi_request.user.username, "teacher1")
        response3 = self.client.post("/users/impersonate/stop/")
        self.assertEqual(response3.status_code, 302)
        response4 = self.client.get("/users/")
        self.assertEqual(response4.wsgi_request.user.username, "superadmin")
        self.assertTrue(ActivityLog.objects.filter(action__icontains="impersonate_").exists())


class PlatformAnnouncementsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )

    def test_superadmin_can_create_announcement(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(
            "/platform/announcements/create/",
            {"title": "Maintenance", "message": "Tonight 10 PM", "severity": "WARNING", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlatformAnnouncement.objects.filter(title="Maintenance").exists())


class SupportInboxTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )

    def test_superadmin_can_create_support_ticket(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(
            "/platform/support/create/",
            {"title": "Login issue", "description": "School cannot login", "status": "OPEN", "priority": "HIGH"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SupportTicket.objects.filter(title="Login issue").exists())


class AuthThrottlingSmokeTests(TestCase):
    def test_login_throttle_sets_event(self):
        # This is a smoke test: we just ensure event logging model is wired.
        AuthSecurityEvent.objects.create(event="THROTTLED", username="x", ip_address="1.1.1.1", success=False, details="test")
        self.assertEqual(AuthSecurityEvent.objects.filter(event="THROTTLED").count(), 1)


class ReportBuilderSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.template = ReportTemplate.objects.create(name="Users Export", dataset="USERS", filters={}, columns=[], is_active=True)

    def test_superadmin_can_export_report_template_csv(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(f"/reports/builder/{self.template.id}/export/csv/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.get("Content-Type", ""))


class TenancySafetyTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(
            name="Alpha School",
            code="A01",
            email="a@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal A",
            established_year=2001,
            is_active=True,
        )
        self.school_b = School.objects.create(
            name="Beta School",
            code="B01",
            email="b@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal B",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school_a,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
            SchoolSubscription.objects.update_or_create(
                school=self.school_b,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )

        User = get_user_model()
        self.principal_a = User.objects.create_user(username="principal_a", password="pass123", role="PRINCIPAL", school=self.school_a)

        self.student_b = Student.objects.create(
            school=self.school_b,
            admission_no="B-001",
            first_name="Test",
            last_name="Student",
            gender="MALE",
            class_name="1",
            section="A",
            guardian_name="Guardian",
            guardian_phone="9999999999",
            is_active=True,
            slug="test-student-b001",
            admission_date=date(2026, 4, 1),
        )

    def test_user_cannot_access_other_school_student_by_id(self):
        self.client.force_login(self.principal_a)
        response = self.client.get(f"/students/{self.student_b.id}/")
        self.assertIn(response.status_code, {404, 302, 403})

    def test_user_cannot_access_other_school_student_by_slug(self):
        self.client.force_login(self.principal_a)
        response = self.client.get(f"/students/{self.student_b.slug}/")
        self.assertIn(response.status_code, {404, 302, 403})


class BillingWebhookSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(username="superadmin", password="pass123", role="SUPER_ADMIN", school=None)
        self.school = School.objects.create(
            name="Webhook School",
            code="WS01",
            email="ws@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if not plan:
            plan = SubscriptionPlan.objects.create(name="Plan", code="X", tier="SILVER")
        self.invoice = SubscriptionInvoice.objects.create(
            school=self.school,
            plan=plan,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            amount="100.00",
            status="ISSUED",
        )

    def test_webhook_creates_payment_and_marks_paid(self):
        payload = {
            "provider": "GENERIC",
            "event_id": "evt_1",
            "event_type": "payment.captured",
            "invoice_id": self.invoice.id,
            "amount": "100.00",
            "method": "UPI",
            "transaction_ref": "tx1",
            "status": "PAID",
        }
        response = self.client.post("/billing/webhooks/generic/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PAID")
        self.assertTrue(SubscriptionPayment.objects.filter(invoice=self.invoice).exists())


class AuditLogExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(username="superadmin_export", password="pass123", role="SUPER_ADMIN", school=None)
        ActivityLog.objects.create(
            actor=self.superadmin,
            school=None,
            view_name="test",
            action="test.export",
            method="POST",
            path="/x/",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="pytest",
            message="hello",
        )

    @override_settings(MEDIA_ROOT="test_media")
    def test_create_and_verify_export(self):
        self.client.force_login(self.superadmin)
        response = self.client.post("/activity/exports/create/", {"method": "POST"})
        self.assertEqual(response.status_code, 302)
        export = AuditLogExport.objects.order_by("-id").first()
        self.assertIsNotNone(export)

        download = self.client.get(f"/activity/exports/{export.id}/download/?verify=1")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers.get("X-Audit-Export-SHA256"), export.sha256)

    @override_settings(MEDIA_ROOT="test_media")
    def test_verify_command_passes_for_chain(self):
        from django.core.management import call_command

        self.client.force_login(self.superadmin)
        self.client.post("/activity/exports/create/", {"method": "POST"})
        self.client.post("/activity/exports/create/", {"method": "POST"})
        call_command("verify_audit_exports", limit=10, verbosity=0)


class SettingsOverridesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(username="superadmin_settings", password="pass123", role="SUPER_ADMIN", school=None)

    def test_superadmin_can_save_role_sections_override(self):
        self.client.force_login(self.superadmin)
        resp = self.client.post("/settings/role-matrix/", data={"role": "TEACHER", "sections": ["dashboard", "students", "schools", "settings"]})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(RoleSectionsOverride.objects.filter(role="TEACHER").exists())
        self.assertTrue(RBACChangeEvent.objects.filter(kind="ROLE_SECTIONS_OVERRIDE", role="TEACHER").exists())

    def test_superadmin_cannot_remove_settings_manage_from_superadmin(self):
        self.client.force_login(self.superadmin)
        resp = self.client.post("/settings/permissions/", data={"role": "SUPER_ADMIN", "permissions": ["schools.view"]})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(RolePermissionsOverride.objects.filter(role="SUPER_ADMIN").exists())
        self.assertFalse(RBACChangeEvent.objects.filter(kind="ROLE_PERMISSIONS_OVERRIDE", role="SUPER_ADMIN").exists())

    def test_rbac_grants_page_loads(self):
        self.client.force_login(self.superadmin)
        resp = self.client.get("/settings/rbac-grants/")
        self.assertEqual(resp.status_code, 200)


class RateLimitingSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(username="superadmin_rate", password="pass123", role="SUPER_ADMIN", school=None)

    @override_settings(THROTTLE_USER_INVITES_PER_15M=1)
    def test_user_invite_throttles(self):
        self.client.force_login(self.superadmin)
        school = School.objects.create(
            name="Rate School",
            code="RATE01",
            email="rate@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        payload = {
            "username": "invitee_1",
            "email": "invitee1@example.com",
            "first_name": "A",
            "last_name": "B",
            "role": "TEACHER",
            "school_id": str(school.id),
        }
        first = self.client.post("/users/invite/", data=payload, follow=False)
        self.assertEqual(first.status_code, 302)
        second = self.client.post("/users/invite/", data={**payload, "username": "invitee_2", "email": "invitee2@example.com"}, follow=False)
        self.assertEqual(second.status_code, 302)


class UploadValidationTests(TestCase):
    def test_validate_upload_rejects_oversized_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("x.png", b"0" * (10), content_type="image/png")
        policy = UploadPolicy(
            max_bytes=1,
            allowed_extensions=DEFAULT_IMAGE_POLICY.allowed_extensions,
            allowed_image_formats=DEFAULT_IMAGE_POLICY.allowed_image_formats,
        )
        errors = validate_upload(fake, policy=policy, kind="Test")
        self.assertTrue(errors)

    def test_validate_upload_accepts_valid_png(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (1, 1), color=(255, 0, 0)).save(buf, format="PNG")
        payload = buf.getvalue()
        up = SimpleUploadedFile("ok.png", payload, content_type="image/png")
        errors = validate_upload(up, policy=DEFAULT_IMAGE_POLICY, kind="Image")
        self.assertEqual(errors, [])

    def test_validate_upload_rejects_invalid_pdf(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        up = SimpleUploadedFile("bad.pdf", b"NOTPDF", content_type="application/pdf")
        errors = validate_upload(up, policy=DEFAULT_DOCUMENT_POLICY, kind="PDF")
        self.assertTrue(errors)

    def test_validate_upload_accepts_pdf_header(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        up = SimpleUploadedFile("ok.pdf", b"%PDF-1.7\\n...", content_type="application/pdf")
        errors = validate_upload(up, policy=DEFAULT_DOCUMENT_POLICY, kind="PDF")
        self.assertEqual(errors, [])

    @override_settings(ANTIVIRUS_SCAN_MODE="required")
    def test_validate_upload_fails_when_antivirus_required_but_missing(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        up = SimpleUploadedFile("ok.pdf", b"%PDF-1.7\\n...", content_type="application/pdf")
        with patch("apps.core.upload_validation.shutil.which", return_value=None):
            errors = validate_upload(up, policy=DEFAULT_DOCUMENT_POLICY, kind="PDF")
        self.assertTrue(any("antivirus scanner not available" in e.lower() for e in errors))

    @override_settings(ANTIVIRUS_SCAN_MODE="best_effort")
    def test_validate_upload_skips_when_antivirus_best_effort_and_missing(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        up = SimpleUploadedFile("ok.pdf", b"%PDF-1.7\\n...", content_type="application/pdf")
        with patch("apps.core.upload_validation.shutil.which", return_value=None):
            errors = validate_upload(up, policy=DEFAULT_DOCUMENT_POLICY, kind="PDF")
        self.assertEqual(errors, [])


class SupportTicketEntityChangeLogTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(username="superadmin_supportlog", password="pass123", role="SUPER_ADMIN", school=None)

    def test_support_ticket_update_creates_change_log(self):
        self.client.force_login(self.superadmin)
        ticket = SupportTicket.objects.create(title="Help", description="x", status="OPEN", priority="NORMAL")
        ticket.status = "IN_PROGRESS"
        ticket.save(update_fields=["status"])
        self.assertTrue(EntityChangeLog.objects.filter(entity="core.SupportTicket", object_id=str(ticket.id), action="UPDATED").exists())


class CustomDomainBrandingTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Domain School",
            code="DS01",
            email="ds@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        SchoolDomain.objects.create(school=self.school, domain="erp.domainschool.test", is_active=True, is_primary=True)

    @override_settings(ALLOWED_HOSTS=["erp.domainschool.test", "testserver", "localhost", "127.0.0.1"])
    def test_login_page_title_uses_tenant_school(self):
        response = self.client.get("/login/", HTTP_HOST="erp.domainschool.test")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login | Domain School")


class CouponInvoiceSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(username="superadmin", password="pass123", role="SUPER_ADMIN", school=None)
        self.school = School.objects.create(
            name="Coupon School",
            code="CS01",
            email="cs@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if not plan:
            plan = SubscriptionPlan.objects.create(name="Plan", code="PC", tier="SILVER")
        self.plan = plan
        SubscriptionCoupon.objects.create(code="LAUNCH50", discount_type="PERCENT", value="50", is_active=True)

    def test_invoice_create_applies_coupon_discount(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(
            "/billing/invoices/create/",
            {
                "school_id": self.school.id,
                "plan_id": self.plan.id,
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
                "due_date": "2026-04-10",
                "amount": "100.00",
                "status": "ISSUED",
                "coupon_code": "LAUNCH50",
            },
        )
        self.assertEqual(response.status_code, 302)
        inv = SubscriptionInvoice.objects.filter(school=self.school).order_by("-id").first()
        self.assertIsNotNone(inv)
        self.assertEqual(str(inv.amount), "50.00")


class InvoiceTaxSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(username="superadmin", password="pass123", role="SUPER_ADMIN", school=None)
        self.school = School.objects.create(
            name="Tax School",
            code="TX01",
            email="tx@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if not plan:
            plan = SubscriptionPlan.objects.create(name="Plan", code="TP", tier="SILVER")
        self.plan = plan

    def test_invoice_create_sets_tax_and_total(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(
            "/billing/invoices/create/",
            {
                "school_id": self.school.id,
                "plan_id": self.plan.id,
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
                "amount": "100.00",
                "tax_percent": "18",
                "status": "ISSUED",
            },
        )
        self.assertEqual(response.status_code, 302)
        inv = SubscriptionInvoice.objects.filter(school=self.school).order_by("-id").first()
        self.assertIsNotNone(inv)
        self.assertEqual(str(inv.tax_amount), "18.00")
        self.assertEqual(str(inv.total_amount), "118.00")


class BillingWebhookSecurityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Webhook School",
            code="WB01",
            email="wb@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if not plan:
            plan = SubscriptionPlan.objects.create(name="Plan", code="WBP", tier="SILVER")
        self.invoice = SubscriptionInvoice.objects.create(
            school=self.school,
            plan=plan,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            amount="100.00",
            total_amount="100.00",
            status="ISSUED",
        )

    def _signed_headers(self, payload: dict, secret: str):
        timestamp = str(int(time.time()))
        body = json.dumps(payload)
        signed_payload = f"{timestamp}.{body}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        return body, {
            "HTTP_X_WEBHOOK_TIMESTAMP": timestamp,
            "HTTP_X_WEBHOOK_SIGNATURE": f"sha256={signature}",
        }

    @override_settings(BILLING_WEBHOOK_REQUIRE_SIGNATURE=True, BILLING_WEBHOOK_SECRET="test-secret")
    def test_rejects_missing_signature_headers(self):
        payload = {"provider": "GENERIC", "event_id": "ev_missing_headers", "invoice_id": self.invoice.id}
        response = self.client.post("/billing/webhooks/generic/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 401)

    @override_settings(BILLING_WEBHOOK_REQUIRE_SIGNATURE=True, BILLING_WEBHOOK_SECRET="test-secret")
    def test_accepts_valid_signature_and_processes_payment(self):
        payload = {
            "provider": "GENERIC",
            "event_id": "ev_valid_sig",
            "event_type": "payment.captured",
            "invoice_id": self.invoice.id,
            "amount": "100.00",
            "method": "UPI",
            "transaction_ref": "txn_ok",
            "status": "PAID",
        }
        body, headers = self._signed_headers(payload, "test-secret")
        response = self.client.post("/billing/webhooks/generic/", data=body, content_type="application/json", **headers)
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PAID")

    @override_settings(BILLING_WEBHOOK_REQUIRE_SIGNATURE=True, BILLING_WEBHOOK_SECRET="test-secret")
    def test_replay_signature_is_blocked(self):
        payload = {
            "provider": "GENERIC",
            "event_id": "ev_replay",
            "invoice_id": self.invoice.id,
            "amount": "100.00",
            "method": "UPI",
        }
        body, headers = self._signed_headers(payload, "test-secret")
        first = self.client.post("/billing/webhooks/generic/", data=body, content_type="application/json", **headers)
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/billing/webhooks/generic/", data=body, content_type="application/json", **headers)
        self.assertEqual(second.status_code, 409)


class BillingAutomationCommandTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Automation School",
            code="AUTO01",
            email="auto@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if not plan:
            plan = SubscriptionPlan.objects.create(name="Plan", code="AUTOP", tier="SILVER")
        self.sub = SchoolSubscription.objects.create(
            school=self.school,
            plan=plan,
            status="ACTIVE",
            starts_on=date(2026, 4, 1),
            ends_on=None,
        )

    def test_marks_subscription_past_due_on_overdue_issued_invoice(self):
        SubscriptionInvoice.objects.create(
            school=self.school,
            plan=self.sub.plan,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            amount="100.00",
            total_amount="100.00",
            due_date=date(2026, 4, 10),
            status="ISSUED",
        )
        out = StringIO()
        call_command("run_billing_automation", stdout=out)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "PAST_DUE")

    def test_dry_run_does_not_modify_subscription(self):
        SubscriptionInvoice.objects.create(
            school=self.school,
            plan=self.sub.plan,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            amount="100.00",
            total_amount="100.00",
            due_date=date(2026, 4, 10),
            status="ISSUED",
        )
        out = StringIO()
        call_command("run_billing_automation", "--dry-run", stdout=out)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "ACTIVE")


class ProvisioningApiSmokeTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Provision School",
            code="PS01",
            email="ps@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        self.token = IntegrationToken.objects.create(name="prov", token="t" * 64, scopes=["provision.users"], is_active=True)

    def test_upsert_requires_token(self):
        response = self.client.post("/api/provision/users/upsert/", data={"username": "x", "role": "TEACHER"}, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_upsert_creates_user(self):
        payload = {"username": "api_teacher", "role": "TEACHER", "school_id": self.school.id, "is_active": True}
        response = self.client.post(
            "/api/provision/users/upsert/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.token.token,
        )
        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        self.assertTrue(User.objects.filter(username="api_teacher").exists())

    def test_upsert_rejects_token_without_scope(self):
        bad = IntegrationToken.objects.create(name="bad", token="b" * 64, scopes=["reports.view"], is_active=True)
        payload = {"username": "api_teacher2", "role": "TEACHER", "school_id": self.school.id, "is_active": True}
        response = self.client.post(
            "/api/provision/users/upsert/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_KEY=bad.token,
        )
        self.assertEqual(response.status_code, 401)


class SsoGoogleStartSmokeTests(TestCase):
    def test_start_redirects_when_enabled(self):
        from django.test.utils import override_settings

        with override_settings(
            GOOGLE_OIDC_CLIENT_ID="x",
            GOOGLE_OIDC_CLIENT_SECRET="y",
            GOOGLE_OIDC_REDIRECT_URI="http://testserver/sso/google/callback/",
            GOOGLE_OIDC_ENABLED=True,
        ):
            response = self.client.get("/sso/google/start/")
            self.assertEqual(response.status_code, 302)
            self.assertIn("accounts.google.com", response["Location"])


class TwoFactorAllRolesSmokeTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="2FA School",
            code="2F01",
            email="2fa@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.teacher = User.objects.create_user(username="t2fa", password="pass123", role="TEACHER", school=self.school, email="t2fa@example.com", is_active=True)

    def test_login_redirects_to_verify_when_enabled(self):
        from django.test.utils import override_settings

        with override_settings(EMAIL_OTP_2FA_ENABLED=True):
            response = self.client.post("/login/", {"username": "t2fa", "password": "pass123"})
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/verify/", response["Location"])

    def test_login_redirects_to_verify_when_policy_requires_role(self):
        TwoFactorPolicy.objects.create(require_for_roles=["TEACHER"], require_for_user_ids=[])
        response = self.client.post("/login/", {"username": "t2fa", "password": "pass123"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/verify/", response["Location"])


class RoleUrlAccessTests(TestCase):
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
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.principal = User.objects.create_user(username="principal_role", password="pass123", role="PRINCIPAL", school=self.school)
        self.teacher = User.objects.create_user(username="teacher_role", password="pass123", role="TEACHER", school=self.school)
        self.accountant = User.objects.create_user(username="accountant_role", password="pass123", role="ACCOUNTANT", school=self.school)

    def test_non_superadmin_cannot_access_superadmin_urls(self):
        protected_urls = [
            "/users/",
            "/users/export/csv/",
            "/billing/invoices/",
            "/billing/plans/",
            "/platform/",
            "/settings/",
            "/activity/",
        ]
        for user in [self.principal, self.teacher, self.accountant]:
            self.client.force_login(user)
            for url in protected_urls:
                response = self.client.get(url)
                self.assertIn(response.status_code, {302, 403}, msg=f"{user.role} unexpectedly accessed {url} ({response.status_code})")


class SchoolOwnerRoleUiParityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Owner School",
            code="OS01",
            email="owner-school@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner_ui", password="pass123", role="SCHOOL_OWNER", school=self.school)

    def test_school_owner_navigation_has_management_modules_without_superadmin_surfaces(self):
        self.client.force_login(self.owner)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        nav_keys = response.context.get("nav_keys") or []
        self.assertIn("schools", nav_keys)
        self.assertIn("students", nav_keys)
        self.assertIn("admissions", nav_keys)
        self.assertIn("fees", nav_keys)
        self.assertIn("reports", nav_keys)
        self.assertNotIn("users", nav_keys)
        self.assertNotIn("settings", nav_keys)
        self.assertNotIn("platform", nav_keys)

    def test_school_owner_dashboard_shows_owner_control_board_and_insights(self):
        self.client.force_login(self.owner)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Owner Control Board")
        self.assertContains(response, "Insights")
        self.assertContains(response, "/schools/profile/")
        self.assertContains(response, "/students/")


class AdminRoleUiParityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Admin School",
            code="AS01",
            email="admin-school@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin_ui", password="pass123", role="ADMIN", school=self.school)

    def test_admin_navigation_has_admissions_but_not_users_or_settings(self):
        self.client.force_login(self.admin)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        nav_keys = response.context.get("nav_keys") or []
        self.assertIn("admissions", nav_keys)
        self.assertNotIn("users", nav_keys)
        self.assertNotIn("settings", nav_keys)
        self.assertNotIn("platform", nav_keys)

    def test_admin_reports_overview_hides_superadmin_only_links(self):
        self.client.force_login(self.admin)
        response = self.client.get("/reports/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/reports/builder/")
        self.assertNotContains(response, "/reports/scheduled/")

    def test_admin_cannot_open_superadmin_only_report_tools(self):
        self.client.force_login(self.admin)
        for url in ("/reports/builder/", "/reports/scheduled/"):
            response = self.client.get(url)
            self.assertIn(response.status_code, {302, 403}, msg=f"ADMIN unexpectedly accessed {url}")

    def test_admin_can_open_admissions_list(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admissions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admissions")

    def test_admin_dashboard_shows_admin_control_board(self):
        self.client.force_login(self.admin)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Control Board")


class PrincipalRoleUiParityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Principal School",
            code="PS01",
            email="principal-school@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.principal = User.objects.create_user(username="principal_ui", password="pass123", role="PRINCIPAL", school=self.school)

    def test_principal_navigation_is_ops_scoped_without_users_settings_platform(self):
        self.client.force_login(self.principal)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        nav_keys = response.context.get("nav_keys") or []
        self.assertIn("students", nav_keys)
        self.assertIn("academics", nav_keys)
        self.assertIn("attendance", nav_keys)
        self.assertIn("reports", nav_keys)
        self.assertNotIn("users", nav_keys)
        self.assertNotIn("settings", nav_keys)
        self.assertNotIn("platform", nav_keys)

    def test_principal_dashboard_shows_principal_control_board(self):
        self.client.force_login(self.principal)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Principal Control Board")
        self.assertContains(response, "/students/")
        self.assertContains(response, "/academics/")
        self.assertContains(response, "/attendance/")


class VicePrincipalRoleUiParityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Vice Principal School",
            code="VP01",
            email="vice-principal-school@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.vice_principal = User.objects.create_user(
            username="vice_principal_ui",
            password="pass123",
            role="VICE_PRINCIPAL",
            school=self.school,
        )

    def test_vice_principal_navigation_is_ops_scoped_without_users_settings_platform(self):
        self.client.force_login(self.vice_principal)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        nav_keys = response.context.get("nav_keys") or []
        self.assertIn("students", nav_keys)
        self.assertIn("academics", nav_keys)
        self.assertIn("attendance", nav_keys)
        self.assertIn("exams", nav_keys)
        self.assertIn("reports", nav_keys)
        self.assertNotIn("users", nav_keys)
        self.assertNotIn("settings", nav_keys)
        self.assertNotIn("platform", nav_keys)

    def test_vice_principal_dashboard_shows_oversight_desk(self):
        self.client.force_login(self.vice_principal)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vice Principal Desk")
        self.assertContains(response, "/students/")
        self.assertContains(response, "/academics/")
        self.assertContains(response, "/attendance/")


class ManagementTrusteeRoleUiParityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Trustee School",
            code="MT01",
            email="trustee-school@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.trustee = User.objects.create_user(
            username="trustee_ui",
            password="pass123",
            role="MANAGEMENT_TRUSTEE",
            school=self.school,
        )

    def test_management_trustee_navigation_is_leadership_scoped_without_users_settings_platform(self):
        self.client.force_login(self.trustee)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        nav_keys = response.context.get("nav_keys") or []
        self.assertIn("schools", nav_keys)
        self.assertIn("students", nav_keys)
        self.assertIn("academics", nav_keys)
        self.assertIn("attendance", nav_keys)
        self.assertIn("fees", nav_keys)
        self.assertIn("reports", nav_keys)
        self.assertNotIn("users", nav_keys)
        self.assertNotIn("settings", nav_keys)
        self.assertNotIn("platform", nav_keys)

    def test_management_trustee_dashboard_shows_leadership_board(self):
        self.client.force_login(self.trustee)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Management Trustee Board")
        self.assertContains(response, "/reports/")
        self.assertContains(response, "/schools/")


class ReportViewerRoleUiParityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Report Viewer School",
            code="RV01",
            email="report-viewer-school@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.report_viewer = User.objects.create_user(
            username="report_viewer_ui",
            password="pass123",
            role="REPORT_VIEWER",
            school=self.school,
        )

    def test_report_viewer_navigation_excludes_users_settings_platform(self):
        self.client.force_login(self.report_viewer)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        nav_keys = response.context.get("nav_keys") or []
        self.assertIn("reports", nav_keys)
        self.assertIn("students", nav_keys)
        self.assertIn("attendance", nav_keys)
        self.assertIn("fees", nav_keys)
        self.assertNotIn("users", nav_keys)
        self.assertNotIn("settings", nav_keys)
        self.assertNotIn("platform", nav_keys)

    def test_report_viewer_dashboard_shows_report_viewer_hub(self):
        self.client.force_login(self.report_viewer)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Report Viewer Hub")
        self.assertContains(response, "/reports/")

    def test_report_viewer_reports_page_shows_dedicated_home_banner(self):
        self.client.force_login(self.report_viewer)
        response = self.client.get("/reports/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Report Viewer Home")


class SuperAdminOpsWorkflowTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Ops School",
            code="OPS01",
            email="ops@example.com",
            phone="9999999999",
            address="Main road",
            city="Bhopal",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2001,
            is_active=True,
        )
        plan = SubscriptionPlan.objects.filter(code="PLATINUM", is_active=True).first() or SubscriptionPlan.objects.first()
        if plan:
            SchoolSubscription.objects.update_or_create(
                school=self.school,
                defaults={"plan": plan, "status": "ACTIVE", "starts_on": date(2026, 4, 1), "ends_on": None},
            )
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="superadmin_ops",
            password="pass123",
            role="SUPER_ADMIN",
            school=None,
        )
        self.student = Student.objects.create(
            school=self.school,
            admission_no="OPS-001",
            first_name="Ops",
            last_name="Student",
            gender="MALE",
            class_name="5",
            section="A",
            guardian_name="Guardian",
            guardian_phone="9999999999",
            is_active=True,
            slug="ops-student-001",
            admission_date=date(2026, 4, 1),
        )

    def test_platform_pages_index_loads(self):
        self.client.force_login(self.superadmin)
        response = self.client.get("/super-admin/pages/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pages Directory")
        self.assertContains(response, "/super-admin/transport/")

    def test_transport_assign_and_release(self):
        self.client.force_login(self.superadmin)
        route = TransportRoute.objects.create(
            school=self.school,
            route_code="R-01",
            route_name="Route 1",
            vehicle_number="MP04AB1234",
            driver_name="Driver",
            attendant_name="Attendant",
            stops=["Stop 1"],
            is_active=True,
        )
        assign = self.client.post(
            "/super-admin/transport/",
            {
                "action": "assign_student",
                "school_id": str(self.school.id),
                "route_id": str(route.id),
                "student_id": str(self.student.id),
                "pickup_stop": "Stop 1",
            },
        )
        self.assertEqual(assign.status_code, 302)
        self.assertTrue(TransportAssignment.objects.filter(route=route, student=self.student, active=True).exists())
        self.student.refresh_from_db()
        self.assertTrue(self.student.transport_required)
        active_assignment = TransportAssignment.objects.get(route=route, student=self.student, active=True)
        release = self.client.post(
            "/super-admin/transport/",
            {"action": "release_assignment", "assignment_id": str(active_assignment.id)},
        )
        self.assertEqual(release.status_code, 302)
        active_assignment.refresh_from_db()
        self.assertFalse(active_assignment.active)
        self.student.refresh_from_db()
        self.assertFalse(self.student.transport_required)

    def test_hostel_allocate_and_release(self):
        self.client.force_login(self.superadmin)
        room = HostelRoom.objects.create(
            school=self.school,
            room_number="H-101",
            block_name="A",
            bed_capacity=2,
            occupied_beds=0,
            warden_name="Warden",
            mess_plan="Veg",
            is_active=True,
        )
        allocate = self.client.post(
            "/super-admin/hostel/",
            {
                "action": "allocate_student",
                "school_id": str(self.school.id),
                "room_id": str(room.id),
                "student_id": str(self.student.id),
                "bed_label": "B1",
            },
        )
        self.assertEqual(allocate.status_code, 302)
        self.assertTrue(HostelAllocation.objects.filter(room=room, student=self.student, active=True).exists())
        room.refresh_from_db()
        self.assertEqual(room.occupied_beds, 1)
        active_allocation = HostelAllocation.objects.get(room=room, student=self.student, active=True)
        release = self.client.post(
            "/super-admin/hostel/",
            {"action": "release_allocation", "allocation_id": str(active_allocation.id)},
        )
        self.assertEqual(release.status_code, 302)
        active_allocation.refresh_from_db()
        self.assertFalse(active_allocation.active)
        room.refresh_from_db()
        self.assertEqual(room.occupied_beds, 0)

    def test_library_mark_lost_updates_issue_and_book(self):
        self.client.force_login(self.superadmin)
        book = LibraryBook.objects.create(
            school=self.school,
            accession_no="ACC-100",
            title="Ops Book",
            total_copies=2,
            available_copies=1,
            is_active=True,
        )
        issue = LibraryIssue.objects.create(
            school=self.school,
            book=book,
            student=self.student,
            status="ISSUED",
            issued_on=date(2026, 4, 1),
        )
        response = self.client.post(
            "/super-admin/library/",
            {"action": "mark_lost", "issue_id": str(issue.id), "fine_amount": "250"},
        )
        self.assertEqual(response.status_code, 302)
        issue.refresh_from_db()
        book.refresh_from_db()
        self.assertEqual(issue.status, "LOST")
        self.assertEqual(str(issue.fine_amount), "250.00")
        self.assertEqual(book.total_copies, 1)
        self.assertLessEqual(book.available_copies, book.total_copies)

    def test_inventory_move_stock_creates_movement(self):
        self.client.force_login(self.superadmin)
        item = InventoryItem.objects.create(
            school=self.school,
            sku="SKU-1",
            name="Marker",
            quantity_on_hand="10",
            reorder_level="2",
            unit="pcs",
            is_active=True,
        )
        response = self.client.post(
            "/super-admin/inventory/",
            {
                "action": "move_stock",
                "school_id": str(self.school.id),
                "item_id": str(item.id),
                "movement_type": "OUT",
                "quantity": "3",
                "notes": "Issued",
            },
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(str(item.quantity_on_hand), "7.00")
        self.assertTrue(InventoryMovement.objects.filter(item=item, movement_type="OUT").exists())

    def test_transport_assignment_creates_fee_ledger(self):
        self.client.force_login(self.superadmin)
        route = TransportRoute.objects.create(
            school=self.school,
            route_code="R-02",
            route_name="Route 2",
            vehicle_number="MP04AB2234",
            is_active=True,
        )
        response = self.client.post(
            "/super-admin/transport/",
            {
                "action": "assign_student",
                "school_id": str(self.school.id),
                "route_id": str(route.id),
                "student_id": str(self.student.id),
                "pickup_stop": "Stop 2",
                "fee_amount": "650",
            },
        )
        self.assertEqual(response.status_code, 302)
        structure = FeeStructure.objects.filter(school=self.school, class_name="TRANSPORT").first()
        self.assertIsNotNone(structure)
        self.assertTrue(StudentFeeLedger.objects.filter(student=self.student, fee_structure=structure).exists())

    def test_hostel_allocation_creates_fee_ledger(self):
        self.client.force_login(self.superadmin)
        room = HostelRoom.objects.create(
            school=self.school,
            room_number="H-102",
            block_name="A",
            bed_capacity=2,
            occupied_beds=0,
            is_active=True,
        )
        response = self.client.post(
            "/super-admin/hostel/",
            {
                "action": "allocate_student",
                "school_id": str(self.school.id),
                "room_id": str(room.id),
                "student_id": str(self.student.id),
                "bed_label": "B2",
                "fee_amount": "1400",
            },
        )
        self.assertEqual(response.status_code, 302)
        structure = FeeStructure.objects.filter(school=self.school, class_name="HOSTEL").first()
        self.assertIsNotNone(structure)
        self.assertTrue(StudentFeeLedger.objects.filter(student=self.student, fee_structure=structure).exists())

    def test_inventory_purchase_order_receive_updates_stock(self):
        self.client.force_login(self.superadmin)
        item = InventoryItem.objects.create(
            school=self.school,
            sku="SKU-2",
            name="Chalk",
            quantity_on_hand="5",
            reorder_level="2",
            unit="pcs",
            is_active=True,
        )
        vendor_resp = self.client.post(
            "/super-admin/inventory/",
            {
                "action": "create_vendor",
                "school_id": str(self.school.id),
                "name": "Stationery Vendor",
            },
        )
        self.assertEqual(vendor_resp.status_code, 302)
        vendor = InventoryVendor.objects.get(school=self.school, name="Stationery Vendor")
        po_resp = self.client.post(
            "/super-admin/inventory/",
            {
                "action": "create_po",
                "school_id": str(self.school.id),
                "vendor_id": str(vendor.id),
                "item_id": str(item.id),
                "po_number": "PO-1001",
                "quantity": "12",
                "unit_cost": "15",
            },
        )
        self.assertEqual(po_resp.status_code, 302)
        po = InventoryPurchaseOrder.objects.get(school=self.school, po_number="PO-1001")
        receive = self.client.post(
            "/super-admin/inventory/",
            {"action": "receive_po", "po_id": str(po.id)},
        )
        self.assertEqual(receive.status_code, 302)
        po.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(po.status, "RECEIVED")
        self.assertEqual(str(item.quantity_on_hand), "17.00")

    def test_transport_release_creates_refund_event(self):
        self.client.force_login(self.superadmin)
        route = TransportRoute.objects.create(
            school=self.school,
            route_code="R-03",
            is_active=True,
        )
        self.client.post(
            "/super-admin/transport/",
            {
                "action": "assign_student",
                "school_id": str(self.school.id),
                "route_id": str(route.id),
                "student_id": str(self.student.id),
                "fee_amount": "600",
            },
        )
        structure = FeeStructure.objects.filter(school=self.school, class_name="TRANSPORT").first()
        ledger = StudentFeeLedger.objects.get(student=self.student, fee_structure=structure)
        ledger.amount_paid = Decimal("300.00")
        ledger.status = "PARTIAL"
        ledger.save(update_fields=["amount_paid", "status"])
        assignment = TransportAssignment.objects.get(route=route, student=self.student, active=True)
        release = self.client.post(
            "/super-admin/transport/",
            {"action": "release_assignment", "assignment_id": str(assignment.id)},
        )
        self.assertEqual(release.status_code, 302)
        event = ServiceRefundEvent.objects.filter(student=self.student, service_type="TRANSPORT").first()
        self.assertIsNotNone(event)
        self.assertGreaterEqual(event.recommended_refund, Decimal("0"))

    def test_fee_reconciliation_shows_refund_analytics(self):
        self.client.force_login(self.superadmin)
        ServiceRefundEvent.objects.create(
            school=self.school,
            student=self.student,
            service_type="HOSTEL",
            billed_amount=Decimal("1200.00"),
            paid_amount=Decimal("1200.00"),
            policy_ratio=Decimal("0.5000"),
            days_remaining=15,
            total_days=30,
            recommended_refund=Decimal("600.00"),
            status="OPEN",
            notes="test",
        )
        response = self.client.get("/super-admin/fees/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Refund Exposure")
        self.assertContains(response, "600.00")
