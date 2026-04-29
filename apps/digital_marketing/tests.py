from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.digital_marketing.models import (
    DigitalMarketingReportRun,
    DigitalMarketingReportSchedule,
    MarketingCampaign,
    MarketingLead,
    SocialPost,
    WebsiteFormIntegration,
)
from apps.schools.models import School, SchoolSubscription, SubscriptionPlan


class DigitalMarketingModuleTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="DM School",
            code="DMSCH",
            email="dm@example.com",
            phone="1234567890",
            address="Addr",
            city="City",
            state="State",
            principal_name="Principal",
            established_year=2001,
        )
        plan = SubscriptionPlan.objects.create(
            name="P", code="PC", tier="SILVER", price_monthly=0, billing_mode="FLAT", unit_price=0
        )
        SchoolSubscription.objects.create(school=self.school, plan=plan, status="ACTIVE")
        User = get_user_model()
        self.user = User.objects.create_user(
            username="dm", password="pass1234", role="DIGITAL_MARKETING_MANAGER", school=self.school
        )
        self.client.force_login(self.user)

    def test_overview_loads(self):
        response = self.client.get("/digital-marketing/")
        self.assertEqual(response.status_code, 200)

    def test_campaign_and_lead_create(self):
        c = MarketingCampaign.objects.create(school=self.school, name="Summer", channel="Meta Ads")
        MarketingLead.objects.create(
            school=self.school, campaign=c, student_name="Lead One", phone="9999999999"
        )
        self.assertEqual(MarketingCampaign.objects.filter(school=self.school).count(), 1)
        self.assertEqual(MarketingLead.objects.filter(school=self.school).count(), 1)

    def test_social_post_approval_workflow(self):
        post = SocialPost.objects.create(school=self.school, title="Organic Reel")
        submit_url = reverse("digital_marketing:social_post_submit_review", args=[post.id])
        approve_url = reverse("digital_marketing:social_post_approve", args=[post.id])
        publish_url = reverse("digital_marketing:social_post_publish", args=[post.id])

        self.client.post(submit_url)
        post.refresh_from_db()
        self.assertEqual(post.status, "IN_REVIEW")

        self.client.post(approve_url, data={"review_notes": "Looks good"})
        post.refresh_from_db()
        self.assertEqual(post.status, "APPROVED")
        self.assertIsNotNone(post.reviewed_by)
        self.assertEqual(post.review_notes, "Looks good")

        self.client.post(publish_url)
        post.refresh_from_db()
        self.assertEqual(post.status, "FAILED")

    def test_lead_export_followup_filter(self):
        today = timezone.localdate()
        yesterday = today - timezone.timedelta(days=1)
        MarketingLead.objects.create(
            school=self.school,
            student_name="Today Lead",
            phone="1111111111",
            next_followup_on=today,
            stage="NEW",
        )
        MarketingLead.objects.create(
            school=self.school,
            student_name="Overdue Lead",
            phone="2222222222",
            next_followup_on=yesterday,
            stage="CONTACTED",
        )
        MarketingLead.objects.create(
            school=self.school, student_name="Future Lead", phone="3333333333", stage="NEW"
        )

        export_url = reverse("digital_marketing:lead_export_csv")
        response_today = self.client.get(export_url, {"followup": "today"})
        self.assertEqual(response_today.status_code, 200)
        self.assertIn("Today Lead", response_today.content.decode("utf-8"))
        self.assertNotIn("Overdue Lead", response_today.content.decode("utf-8"))

        response_overdue = self.client.get(export_url, {"followup": "overdue"})
        self.assertEqual(response_overdue.status_code, 200)
        self.assertIn("Overdue Lead", response_overdue.content.decode("utf-8"))

    def test_social_post_reject_requires_note_and_sets_audit(self):
        post = SocialPost.objects.create(
            school=self.school, title="Review Post", status="IN_REVIEW"
        )
        reject_url = reverse("digital_marketing:social_post_reject", args=[post.id])

        # Rejection without note should not proceed.
        self.client.post(reject_url, data={"review_notes": ""})
        post.refresh_from_db()
        self.assertEqual(post.status, "IN_REVIEW")
        self.assertIsNone(post.reviewed_by)
        self.assertIsNone(post.reviewed_at)

        # Rejection with note should mark FAILED and fill audit fields.
        self.client.post(reject_url, data={"review_notes": "Caption not compliant"})
        post.refresh_from_db()
        self.assertEqual(post.status, "FAILED")
        self.assertEqual(post.review_notes, "Caption not compliant")
        self.assertIsNotNone(post.reviewed_by)
        self.assertIsNotNone(post.reviewed_at)

    def test_run_dm_report_schedules_command(self):
        schedule = DigitalMarketingReportSchedule.objects.create(
            school=self.school,
            name="Weekly DM Snapshot",
            frequency="WEEKLY",
            delivery_email="principal@example.com",
            is_active=True,
            last_run_at=timezone.now() - timezone.timedelta(days=8),
        )
        call_command("run_dm_report_schedules")
        schedule.refresh_from_db()
        self.assertIsNotNone(schedule.last_run_at)
        self.assertTrue(
            DigitalMarketingReportRun.objects.filter(schedule=schedule, status="SUCCESS").exists()
        )

    def test_website_integration_ingest_with_field_mapping(self):
        integration = WebsiteFormIntegration.objects.create(
            school=self.school,
            name="Main Site Form",
            website_url="https://school.example.com",
            source_label="Website Form",
            auth_key="secret-key",
            field_mapping={
                "student_name": "full_name",
                "phone": "mobile",
                "email": "email_id",
                "guardian_name": "parent_name",
                "class_interest": "grade",
            },
            is_active=True,
        )
        url = reverse("digital_marketing:website_integration_ingest", args=[integration.id])
        response = self.client.post(
            url,
            data={
                "full_name": "Riya Sharma",
                "mobile": "9990001112",
                "email_id": "riya@example.com",
                "parent_name": "Amit Sharma",
                "grade": "Class 8",
            },
            HTTP_X_INTEGRATION_KEY="secret-key",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            MarketingLead.objects.filter(
                school=self.school,
                student_name="Riya Sharma",
                phone="9990001112",
                class_interest="Class 8",
            ).exists()
        )
