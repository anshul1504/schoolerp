from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.schools.models import School, SchoolSubscription, SubscriptionPlan

from .models import CallLog, Enquiry, EnquiryFollowUp, MeetingRequest, MessageCampaign, MessageDeliveryLog, MessageTemplate, VisitorLog


class FrontofficeModuleTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Front Desk School",
            code="FDS01",
            email="frontdesk@example.com",
            phone="9999999999",
            address="Main road",
            city="Indore",
            state="Madhya Pradesh",
            principal_name="Principal",
            established_year=2005,
            is_active=True,
        )
        self.plan = SubscriptionPlan.objects.get(code="PLATINUM")
        SchoolSubscription.objects.create(
            school=self.school,
            plan=self.plan,
            status="ACTIVE",
        )
        User = get_user_model()
        self.receptionist = User.objects.create_user(
            username="reception",
            password="pass123",
            role="RECEPTIONIST",
            school=self.school,
        )
        self.teacher = User.objects.create_user(
            username="teacher",
            password="pass123",
            role="TEACHER",
            school=self.school,
        )

    def test_receptionist_can_create_enquiry(self):
        self.client.force_login(self.receptionist)
        response = self.client.post(
            "/frontoffice/enquiries/create/",
            {
                "student_name": "Aarav Singh",
                "guardian_name": "Rohan Singh",
                "phone": "9876543210",
                "interested_class": "Class 4",
                "source": "CALL",
                "status": "NEW",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Enquiry.objects.filter(student_name="Aarav Singh", school=self.school).exists())

    def test_receptionist_can_log_visitor(self):
        self.client.force_login(self.receptionist)
        response = self.client.post(
            "/frontoffice/visitors/create/",
            {
                "visitor_name": "Vendor Person",
                "purpose": "DELIVERY",
                "person_to_meet": "Admin Office",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(VisitorLog.objects.filter(visitor_name="Vendor Person", school=self.school).exists())

    def test_receptionist_can_log_follow_up(self):
        enquiry = Enquiry.objects.create(
            school=self.school,
            student_name="Aarav Singh",
            guardian_name="Rohan Singh",
            phone="9876543210",
            created_by=self.receptionist,
        )
        self.client.force_login(self.receptionist)
        response = self.client.post(
            f"/frontoffice/enquiries/{enquiry.id}/follow-ups/create/",
            {
                "follow_up_on": "2026-04-21",
                "outcome": "CALL_BACK",
                "next_follow_up_date": "2026-04-22",
                "summary": "Parent asked for a callback tomorrow.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(EnquiryFollowUp.objects.filter(enquiry=enquiry, outcome="CALL_BACK").exists())

    def test_enquiry_convert_prefills_student_admission(self):
        enquiry = Enquiry.objects.create(
            school=self.school,
            student_name="Aarav Singh",
            guardian_name="Rohan Singh",
            phone="9876543210",
            email="guardian@example.com",
            interested_class="Class 4",
            created_by=self.receptionist,
        )
        self.client.force_login(self.receptionist)
        response = self.client.post(f"/frontoffice/enquiries/{enquiry.id}/convert/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/students/create/?", response.url)
        self.assertIn("guardian_name=Rohan+Singh", response.url)

    def test_receptionist_can_open_frontoffice_pages(self):
        self.client.force_login(self.receptionist)
        for url in [
            "/frontoffice/",
            "/frontoffice/enquiries/",
            "/frontoffice/follow-ups/",
            "/frontoffice/meetings/",
            "/frontoffice/messages/",
            "/frontoffice/visitors/",
            "/dashboard/",
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_receptionist_can_delete_enquiry(self):
        enquiry = Enquiry.objects.create(
            school=self.school,
            student_name="To Delete",
            guardian_name="Parent",
            phone="9999999999",
            created_by=self.receptionist,
        )
        self.client.force_login(self.receptionist)
        response = self.client.post(f"/frontoffice/enquiries/{enquiry.id}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Enquiry.objects.filter(id=enquiry.id).exists())

    def test_receptionist_can_delete_visitor(self):
        visitor = VisitorLog.objects.create(
            school=self.school,
            visitor_name="Delete Visitor",
            created_by=self.receptionist,
        )
        self.client.force_login(self.receptionist)
        response = self.client.post(f"/frontoffice/visitors/{visitor.id}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(VisitorLog.objects.filter(id=visitor.id).exists())

    def test_receptionist_can_create_meeting_request(self):
        self.client.force_login(self.receptionist)
        response = self.client.post(
            "/frontoffice/meetings/create/",
            {
                "guardian_name": "Parent A",
                "guardian_phone": "9999999999",
                "student_name": "Student A",
                "mode": "CALL",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MeetingRequest.objects.filter(school=self.school, guardian_name="Parent A").exists())

    def test_receptionist_can_create_template_and_campaign(self):
        self.client.force_login(self.receptionist)
        response = self.client.post(
            "/frontoffice/messages/templates/create/",
            {
                "name": "Follow-up",
                "channel": "EMAIL",
                "target": "PARENTS",
                "subject": "Admission follow-up",
                "body": "Please visit school tomorrow.",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        template = MessageTemplate.objects.filter(school=self.school, name="Follow-up").first()
        self.assertIsNotNone(template)

        response = self.client.post(
            "/frontoffice/messages/campaigns/create/",
            {
                "template_id": str(template.id),
                "channel": "EMAIL",
                "target": "PARENTS",
                "title": "Campaign 1",
                "subject": "Hello",
                "body": "Body",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MessageCampaign.objects.filter(school=self.school, title="Campaign 1").exists())

    def test_receptionist_can_mark_delivery_read(self):
        campaign = MessageCampaign.objects.create(
            school=self.school,
            title="Campaign 2",
            body="Body",
            channel="EMAIL",
            target="PARENTS",
            status="SENT",
            created_by=self.receptionist,
        )
        delivery = MessageDeliveryLog.objects.create(
            campaign=campaign,
            channel="EMAIL",
            recipient_label="Parent",
            recipient_contact="parent@example.com",
            status="SENT",
        )
        self.client.force_login(self.receptionist)
        response = self.client.post(
            f"/frontoffice/messages/campaigns/{campaign.id}/",
            {"delivery_id": str(delivery.id), "action": "mark_read"},
        )
        self.assertEqual(response.status_code, 302)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.read_at)

    def test_receptionist_can_retry_failed_delivery(self):
        campaign = MessageCampaign.objects.create(
            school=self.school,
            title="Campaign 3",
            body="Body",
            channel="EMAIL",
            target="PARENTS",
            status="SENT",
            created_by=self.receptionist,
        )
        delivery = MessageDeliveryLog.objects.create(
            campaign=campaign,
            channel="EMAIL",
            recipient_label="Parent",
            recipient_contact="parent@example.com",
            status="FAILED",
            error="Boom",
        )
        self.client.force_login(self.receptionist)
        response = self.client.post(
            f"/frontoffice/messages/campaigns/{campaign.id}/",
            {"delivery_id": str(delivery.id), "action": "retry"},
        )
        self.assertEqual(response.status_code, 302)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "SENT")
        self.assertGreaterEqual(delivery.attempt_count, 1)

    def test_receptionist_can_create_call_log(self):
        self.client.force_login(self.receptionist)
        response = self.client.post(
            "/frontoffice/calls/create/",
            {
                "phone": "9000000000",
                "caller_name": "Caller",
                "call_type": "INCOMING",
                "status": "OPEN",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CallLog.objects.filter(school=self.school, phone="9000000000").exists())

    def test_teacher_cannot_access_frontoffice(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/frontoffice/")

        self.assertEqual(response.status_code, 302)
