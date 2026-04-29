from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from apps.alumni import views as alumni_views
from apps.alumni.models import Alumni, SuccessStory
from apps.core.models import EntityChangeLog
from apps.schools.models import School, SchoolSubscription, SubscriptionPlan
from apps.students.models import Student


class AlumniManagerSecurityTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(
            name="School A",
            code="SCHA",
            email="a@example.com",
            phone="1234567890",
            address="Addr A",
            city="City",
            state="State",
            principal_name="Principal A",
            established_year=2000,
        )
        self.school_b = School.objects.create(
            name="School B",
            code="SCHB",
            email="b@example.com",
            phone="1234567891",
            address="Addr B",
            city="City",
            state="State",
            principal_name="Principal B",
            established_year=2001,
        )
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            code="TEST_PLAN",
            tier="SILVER",
            price_monthly=0,
            billing_mode="FLAT",
            unit_price=0,
        )
        SchoolSubscription.objects.create(school=self.school_a, plan=plan, status="ACTIVE")
        SchoolSubscription.objects.create(school=self.school_b, plan=plan, status="ACTIVE")
        User = get_user_model()
        self.user = User.objects.create_user(
            username="alumni_mgr",
            password="pass1234",
            role="ALUMNI_MANAGER",
            school=self.school_a,
        )
        self.client.force_login(self.user)
        self.factory = RequestFactory()

    def _make_student(self, school, suffix):
        return Student.objects.create(
            school=school,
            admission_no=f"A{suffix}",
            first_name=f"Stu{suffix}",
            last_name="X",
            gender="MALE",
            class_name="10",
            section="A",
            guardian_name="Guardian",
            guardian_phone="9999999999",
            admission_date="2024-01-01",
        )

    def _build_request(self, method, path, data=None):
        request_method = getattr(self.factory, method.lower())
        request = request_method(path, data=data or {})
        request.user = self.user
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        return request

    def test_alumni_create_rejects_student_from_other_school(self):
        other_school_student = self._make_student(self.school_b, "B1")
        request = self._build_request(
            "POST",
            "/alumni/list/add/",
            data={
                "student": other_school_student.pk,
                "full_name": "Injected Alumni",
                "graduation_year": 2020,
                "batch": "2016-2020",
                "current_occupation": "Engineer",
                "current_organization": "Org",
                "location": "Loc",
                "email": "x@example.com",
                "phone": "99999",
                "linkedin_profile": "",
                "is_verified": "on",
            },
        )
        response = alumni_views.alumni_create(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Alumni.objects.filter(full_name="Injected Alumni").exists())

    def test_story_create_rejects_alumni_from_other_school(self):
        alumni_b = Alumni.objects.create(
            school=self.school_b,
            full_name="Alumni B",
            graduation_year=2018,
            batch="2014-2018",
            email="alb@example.com",
        )
        request = self._build_request(
            "POST",
            "/alumni/stories/publish/",
            data={
                "alumni": alumni_b.pk,
                "title": "Cross-school story",
                "content": "Content",
                "is_featured": "on",
            },
        )
        response = alumni_views.story_create(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SuccessStory.objects.filter(title="Cross-school story").exists())

    def test_toggle_verification_only_allows_post(self):
        alumni = Alumni.objects.create(
            school=self.school_a,
            full_name="Alumni A",
            graduation_year=2017,
            batch="2013-2017",
            email="ala@example.com",
            is_verified=False,
        )
        get_request = self._build_request("GET", f"/alumni/list/verify/{alumni.pk}/")
        get_response = alumni_views.toggle_verification(get_request, pk=alumni.pk)
        self.assertEqual(get_response.status_code, 302)
        alumni.refresh_from_db()
        self.assertFalse(alumni.is_verified)

        post_request = self._build_request("POST", f"/alumni/list/verify/{alumni.pk}/")
        post_response = alumni_views.toggle_verification(post_request, pk=alumni.pk)
        self.assertEqual(post_response.status_code, 302)
        alumni.refresh_from_db()
        self.assertTrue(alumni.is_verified)

    def test_alumni_edit_rejects_student_from_other_school(self):
        local_student = self._make_student(self.school_a, "A1")
        other_student = self._make_student(self.school_b, "B2")
        alumni = Alumni.objects.create(
            school=self.school_a,
            student=local_student,
            full_name="Edit Target",
            graduation_year=2019,
            batch="2015-2019",
            email="edit@example.com",
        )
        request = self._build_request(
            "POST",
            f"/alumni/list/edit/{alumni.pk}/",
            data={
                "student": other_student.pk,
                "full_name": "Edit Target Updated",
                "graduation_year": 2019,
                "batch": "2015-2019",
                "current_occupation": "",
                "current_organization": "",
                "location": "",
                "email": "edit@example.com",
                "phone": "",
                "linkedin_profile": "",
                "is_verified": "on",
            },
        )
        response = alumni_views.alumni_edit(request, pk=alumni.pk)
        self.assertEqual(response.status_code, 200)
        alumni.refresh_from_db()
        self.assertEqual(alumni.student_id, local_student.pk)

    def test_story_edit_rejects_alumni_from_other_school(self):
        local_alumni = Alumni.objects.create(
            school=self.school_a,
            full_name="Alumni A Story",
            graduation_year=2016,
            batch="2012-2016",
            email="asa@example.com",
        )
        other_alumni = Alumni.objects.create(
            school=self.school_b,
            full_name="Alumni B Story",
            graduation_year=2016,
            batch="2012-2016",
            email="asb@example.com",
        )
        story = SuccessStory.objects.create(
            alumni=local_alumni,
            title="Original Story",
            content="Original content",
            is_featured=False,
        )
        request = self._build_request(
            "POST",
            f"/alumni/stories/edit/{story.pk}/",
            data={
                "alumni": other_alumni.pk,
                "title": "Attempted Cross School Update",
                "content": "Updated content",
                "is_featured": "on",
            },
        )
        response = alumni_views.story_edit(request, pk=story.pk)
        self.assertEqual(response.status_code, 200)
        story.refresh_from_db()
        self.assertEqual(story.alumni_id, local_alumni.pk)

    def test_add_contribution_rejects_negative_amount(self):
        alumni = Alumni.objects.create(
            school=self.school_a,
            full_name="Contribution Target",
            graduation_year=2015,
            batch="2011-2015",
            email="ct@example.com",
        )
        request = self._build_request(
            "POST",
            f"/alumni/list/contribution/{alumni.pk}/",
            data={"type": "DONATION", "amount": "-10", "notes": "bad"},
        )
        response = alumni_views.add_contribution(request, pk=alumni.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(alumni.contributions.count(), 0)

    def test_toggle_verification_creates_audit_log(self):
        alumni = Alumni.objects.create(
            school=self.school_a,
            full_name="Audit Alumni",
            graduation_year=2014,
            batch="2010-2014",
            email="audit@example.com",
            is_verified=False,
        )
        request = self._build_request("POST", f"/alumni/list/verify/{alumni.pk}/")
        _ = alumni_views.toggle_verification(request, pk=alumni.pk)
        self.assertTrue(
            EntityChangeLog.objects.filter(
                entity="alumni.Alumni",
                object_id=str(alumni.pk),
                action="UPDATED",
            ).exists()
        )
