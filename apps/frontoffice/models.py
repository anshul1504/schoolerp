from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.schools.models import School


class Enquiry(models.Model):
    STATUS_CHOICES = (
        ("NEW", "New"),
        ("FOLLOW_UP", "Follow Up"),
        ("ADMISSION_IN_PROGRESS", "Admission In Progress"),
        ("CLOSED", "Closed"),
    )
    SOURCE_CHOICES = (
        ("WALK_IN", "Walk In"),
        ("CALL", "Call"),
        ("WHATSAPP", "WhatsApp"),
        ("EMAIL", "Email"),
        ("REFERENCE", "Reference"),
        ("WEBSITE", "Website"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="enquiries")
    student_name = models.CharField(max_length=150)
    guardian_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    interested_class = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="WALK_IN")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="NEW")
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    converted_student = models.ForeignKey(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_enquiries",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_enquiries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["follow_up_date", "-created_at"]

    def __str__(self):
        return f"{self.student_name} enquiry"


class EnquiryFollowUp(models.Model):
    OUTCOME_CHOICES = (
        ("NO_RESPONSE", "No Response"),
        ("INTERESTED", "Interested"),
        ("VISIT_SCHEDULED", "Visit Scheduled"),
        ("CALL_BACK", "Call Back"),
        ("NOT_INTERESTED", "Not Interested"),
    )

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="follow_ups")
    follow_up_on = models.DateField(default=timezone.localdate)
    outcome = models.CharField(max_length=30, choices=OUTCOME_CHOICES, default="CALL_BACK")
    next_follow_up_date = models.DateField(null=True, blank=True)
    summary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frontoffice_follow_ups",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-follow_up_on", "-created_at"]

    def __str__(self):
        return f"{self.enquiry.student_name} follow-up"


class VisitorLog(models.Model):
    PURPOSE_CHOICES = (
        ("ADMISSION", "Admission Enquiry"),
        ("PARENT_MEETING", "Parent Meeting"),
        ("DELIVERY", "Delivery"),
        ("OFFICIAL", "Official Work"),
        ("OTHER", "Other"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="visitor_logs")
    visitor_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    person_to_meet = models.CharField(max_length=150, blank=True)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default="OTHER")
    entry_time = models.DateTimeField(default=timezone.now)
    exit_time = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_visitor_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entry_time", "-created_at"]

    def __str__(self):
        return self.visitor_name


class MeetingRequest(models.Model):
    STATUS_CHOICES = (
        ("REQUESTED", "Requested"),
        ("SCHEDULED", "Scheduled"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    )
    MODE_CHOICES = (
        ("IN_PERSON", "In Person"),
        ("CALL", "Call"),
        ("VIDEO", "Video"),
    )
    SOCIAL_CHOICES = (
        ("WHATSAPP", "WhatsApp"),
        ("INSTAGRAM", "Instagram"),
        ("FACEBOOK", "Facebook"),
        ("X", "X / Twitter"),
        ("OTHER", "Other"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="meeting_requests")
    enquiry = models.ForeignKey(
        Enquiry, on_delete=models.SET_NULL, null=True, blank=True, related_name="meeting_requests"
    )
    principal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_meetings",
    )
    guardian_name = models.CharField(max_length=150)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_email = models.EmailField(blank=True)
    student_name = models.CharField(max_length=150, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="IN_PERSON")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="REQUESTED")
    reference_name = models.CharField(max_length=150, blank=True)
    reference_social = models.CharField(max_length=20, choices=SOCIAL_CHOICES, default="WHATSAPP")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_meeting_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Meeting: {self.guardian_name}"


class MessageTemplate(models.Model):
    CHANNEL_CHOICES = (
        ("EMAIL", "Email"),
        ("WHATSAPP", "WhatsApp"),
    )
    TARGET_CHOICES = (
        ("PARENTS", "Parents"),
        ("STUDENTS", "Students"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="message_templates")
    name = models.CharField(max_length=120)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="EMAIL")
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default="PARENTS")
    subject = models.CharField(max_length=150, blank=True)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_message_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class MessageCampaign(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
    )
    CHANNEL_CHOICES = MessageTemplate.CHANNEL_CHOICES
    TARGET_CHOICES = MessageTemplate.TARGET_CHOICES

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="message_campaigns")
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns"
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="EMAIL")
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default="PARENTS")
    title = models.CharField(max_length=150)
    subject = models.CharField(max_length=150, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_message_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class MessageDeliveryLog(models.Model):
    STATUS_CHOICES = (
        ("QUEUED", "Queued"),
        ("SENT", "Sent"),
        ("FAILED", "Failed"),
        ("SKIPPED", "Skipped"),
    )
    channel = models.CharField(max_length=20, choices=MessageTemplate.CHANNEL_CHOICES)

    campaign = models.ForeignKey(
        MessageCampaign, on_delete=models.CASCADE, related_name="deliveries"
    )
    recipient_label = models.CharField(max_length=150, blank=True)
    recipient_contact = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="QUEUED")
    attempt_count = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.campaign_id} {self.status}"


class CallLog(models.Model):
    TYPE_CHOICES = (
        ("INCOMING", "Incoming"),
        ("OUTGOING", "Outgoing"),
        ("MISSED", "Missed"),
    )
    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="call_logs")
    enquiry = models.ForeignKey(
        Enquiry, on_delete=models.SET_NULL, null=True, blank=True, related_name="call_logs"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="call_logs",
    )
    caller_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20)
    call_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="INCOMING")
    purpose = models.CharField(max_length=150, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_call_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone} ({self.call_type})"
