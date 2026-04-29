from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.schools.models import School


class Student(models.Model):
    GENDER_CHOICES = (
        ("MALE", "Male"),
        ("FEMALE", "Female"),
        ("OTHER", "Other"),
    )
    BLOOD_GROUP_CHOICES = (
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="students")
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    admission_no = models.CharField(max_length=30)
    academic_year = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUP_CHOICES, blank=True)
    class_name = models.CharField(max_length=100)
    section = models.CharField(max_length=50)
    roll_number = models.CharField(max_length=30, blank=True)
    stream = models.CharField(max_length=100, blank=True)
    house = models.CharField(max_length=100, blank=True)
    student_phone = models.CharField(max_length=20, blank=True)
    alternate_mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    aadhar_number = models.CharField(max_length=20, blank=True)
    samagra_id = models.CharField(max_length=50, blank=True)
    pen_number = models.CharField(max_length=50, blank=True)
    udise_id = models.CharField(max_length=50, blank=True)
    religion = models.CharField(max_length=100, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    mother_tongue = models.CharField(max_length=100, blank=True)
    identification_mark_1 = models.CharField(max_length=255, blank=True)
    identification_mark_2 = models.CharField(max_length=255, blank=True)
    previous_school = models.CharField(max_length=255, blank=True)
    previous_class = models.CharField(max_length=100, blank=True)
    play_school_name = models.CharField(max_length=255, blank=True)
    transfer_certificate_number = models.CharField(max_length=100, blank=True)
    migration_certificate = models.CharField(max_length=100, blank=True)
    admission_status = models.CharField(max_length=50, blank=True)
    medical_conditions = models.TextField(blank=True)
    father_name = models.CharField(max_length=150, blank=True)
    father_phone = models.CharField(max_length=20, blank=True)
    father_email = models.EmailField(blank=True)
    father_occupation = models.CharField(max_length=150, blank=True)
    father_income = models.CharField(max_length=100, blank=True)
    father_aadhar = models.CharField(max_length=20, blank=True)
    mother_name = models.CharField(max_length=150, blank=True)
    mother_phone = models.CharField(max_length=20, blank=True)
    mother_email = models.EmailField(blank=True)
    mother_occupation = models.CharField(max_length=150, blank=True)
    mother_income = models.CharField(max_length=100, blank=True)
    mother_aadhar = models.CharField(max_length=20, blank=True)
    guardian_name = models.CharField(max_length=150)
    guardian_phone = models.CharField(max_length=20)
    guardian_email = models.EmailField(blank=True)
    guardian_occupation = models.CharField(max_length=150, blank=True)
    relation_with_student = models.CharField(max_length=50, blank=True)
    guardian_address = models.TextField(blank=True)
    admission_date = models.DateField()
    leaving_date = models.DateField(null=True, blank=True)
    current_address = models.TextField(blank=True)
    current_address_line1 = models.CharField(max_length=255, blank=True)
    current_address_line2 = models.CharField(max_length=255, blank=True)
    current_city = models.CharField(max_length=100, blank=True)
    current_state = models.CharField(max_length=100, blank=True)
    current_pincode = models.CharField(max_length=20, blank=True)
    permanent_same_as_current = models.BooleanField(default=False)
    permanent_address = models.TextField(blank=True)
    permanent_address_line1 = models.CharField(max_length=255, blank=True)
    permanent_address_line2 = models.CharField(max_length=255, blank=True)
    permanent_city = models.CharField(max_length=100, blank=True)
    permanent_state = models.CharField(max_length=100, blank=True)
    permanent_pincode = models.CharField(max_length=20, blank=True)
    disability = models.BooleanField(default=False)
    disability_details = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    chronic_disease = models.CharField(max_length=255, blank=True)
    doctor_name = models.CharField(max_length=150, blank=True)
    emergency_medical_notes = models.TextField(blank=True)
    subjects = models.TextField(blank=True)
    previous_percentage = models.CharField(max_length=20, blank=True)
    previous_grade = models.CharField(max_length=20, blank=True)
    fee_category = models.CharField(max_length=100, blank=True)
    scholarship = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    ifsc_code = models.CharField(max_length=50, blank=True)
    transport_required = models.BooleanField(default=False)
    route_number = models.CharField(max_length=100, blank=True)
    bus_number = models.CharField(max_length=100, blank=True)
    pickup_point = models.CharField(max_length=255, blank=True)
    driver_contact = models.CharField(max_length=20, blank=True)
    hostel_required = models.BooleanField(default=False)
    room_number = models.CharField(max_length=100, blank=True)
    warden_name = models.CharField(max_length=150, blank=True)
    mess_plan = models.CharField(max_length=100, blank=True)
    birth_certificate = models.FileField(upload_to="students/documents/", null=True, blank=True)
    aadhar_card = models.FileField(upload_to="students/documents/", null=True, blank=True)
    previous_marksheet = models.FileField(upload_to="students/documents/", null=True, blank=True)
    transfer_certificate_file = models.FileField(
        upload_to="students/documents/", null=True, blank=True
    )
    caste_certificate = models.FileField(upload_to="students/documents/", null=True, blank=True)
    income_certificate = models.FileField(upload_to="students/documents/", null=True, blank=True)
    passport_photo = models.FileField(upload_to="students/documents/", null=True, blank=True)
    student_username = models.CharField(max_length=150, blank=True)
    student_password = models.CharField(max_length=150, blank=True)
    parent_username = models.CharField(max_length=150, blank=True)
    parent_password = models.CharField(max_length=150, blank=True)
    photo = models.ImageField(upload_to="students/photos/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "admission_no"], name="uniq_student_admission_no_per_school"
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            name_part = (
                slugify(f"{self.first_name} {self.middle_name} {self.last_name}".strip())
                or "student"
            )
            admission_part = slugify(getattr(self, "admission_no", "") or "")
            base = name_part
            if admission_part:
                base = f"{name_part}-{admission_part}"
            candidate = base[:120]
            index = 1
            while Student.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                index += 1
                suffix = f"-{index}"
                candidate = base[: (120 - len(suffix))] + suffix
            self.slug = candidate
        super().save(*args, **kwargs)


class StudentDocument(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=150)
    document = models.FileField(upload_to="students/documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.student} - {self.title}"


class StudentPromotion(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="promotions")
    from_class = models.CharField(max_length=100)
    from_section = models.CharField(max_length=50)
    to_class = models.CharField(max_length=100)
    to_section = models.CharField(max_length=50)
    promoted_on = models.DateField()
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-promoted_on", "-created_at"]

    def __str__(self):
        return f"{self.student} promoted to {self.to_class} - {self.to_section}"


class TransferCertificate(models.Model):
    student = models.OneToOneField(
        Student, on_delete=models.CASCADE, related_name="transfer_certificate"
    )
    certificate_no = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField()
    reason = models.TextField(blank=True)
    destination_school = models.CharField(max_length=255, blank=True)
    is_issued = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]

    def __str__(self):
        return f"TC {self.certificate_no} - {self.student}"


class AdmissionWorkflowEvent(models.Model):
    STAGE_CHOICES = (
        ("INQUIRY", "Inquiry"),
        ("FORM_SUBMITTED", "Form Submitted"),
        ("DOCUMENT_VERIFICATION", "Document Verification"),
        ("APPROVAL", "Approval"),
        ("FEE_COLLECTION", "Fee Collection"),
        ("ENROLLED", "Enrolled"),
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("DONE", "Done"),
        ("REJECTED", "Rejected"),
    )

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="admission_workflow_events"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="admission_workflow_events"
    )
    stage = models.CharField(max_length=40, choices=STAGE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    note = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_workflow_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_id} {self.stage} {self.status}"


class StudentProfileEditHistory(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="profile_edit_history"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_profile_edit_history"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile_edit_history",
    )
    changed_fields = models.JSONField(default=list, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_id} profile edit"


class StudentClassChangeHistory(models.Model):
    SOURCE_CHOICES = (
        ("PROMOTION", "Promotion"),
        ("MANUAL", "Manual Update"),
    )

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="class_change_history"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_class_change_history"
    )
    from_class = models.CharField(max_length=100)
    from_section = models.CharField(max_length=50)
    to_class = models.CharField(max_length=100)
    to_section = models.CharField(max_length=50)
    reason = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="MANUAL")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_class_change_history",
    )
    changed_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_on", "-created_at"]

    def __str__(self):
        return f"{self.student_id} {self.from_class}-{self.from_section} -> {self.to_class}-{self.to_section}"


class TransferCertificateRequest(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CLOSED", "Closed"),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="tc_requests")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="tc_requests")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_tc_requests",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_tc_requests",
    )
    reason = models.TextField(blank=True)
    destination_school = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    review_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"TC request {self.student_id} {self.status}"


class StudentDisciplineIncident(models.Model):
    SEVERITY_CHOICES = (
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    )
    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    )

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="discipline_incidents"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_discipline_incidents"
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="LOW")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    incident_date = models.DateField(null=True, blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_student_discipline_incidents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-incident_date", "-created_at"]

    def __str__(self):
        return f"{self.student_id} {self.title}"


class StudentHealthRecord(models.Model):
    TYPE_CHOICES = (
        ("CHECKUP", "Checkup"),
        ("VACCINATION", "Vaccination"),
        ("ALERT", "Health Alert"),
        ("SICK_LEAVE", "Sick Leave"),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="health_records")
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_health_records"
    )
    record_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="CHECKUP")
    title = models.CharField(max_length=150)
    notes = models.TextField(blank=True)
    record_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_health_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-record_date", "-created_at"]

    def __str__(self):
        return f"{self.student_id} {self.record_type}"


class StudentComplianceReminder(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("DONE", "Done"),
    )

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="compliance_reminders"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_compliance_reminders"
    )
    reminder_type = models.CharField(max_length=100)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_compliance_reminders",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]

    def __str__(self):
        return f"{self.student_id} {self.reminder_type} {self.status}"


class StudentCommunicationLog(models.Model):
    CHANNEL_CHOICES = (
        ("CALL", "Call"),
        ("SMS", "SMS"),
        ("EMAIL", "Email"),
        ("WHATSAPP", "WhatsApp"),
        ("MEETING", "Meeting"),
        ("NOTE", "Internal Note"),
    )

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="communication_logs"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_communication_logs"
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="NOTE")
    subject = models.CharField(max_length=150, blank=True)
    message = models.TextField(blank=True)
    logged_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_communication_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at", "-created_at"]

    def __str__(self):
        return f"{self.student_id} {self.channel}"


class StudentHistoryEvent(models.Model):
    ACTION_CHOICES = (
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("DOCUMENT_UPLOADED", "Document Uploaded"),
        ("PROMOTED", "Promoted"),
        ("TC_ISSUED", "Transfer Certificate Issued"),
        ("DELETED", "Deleted"),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="history_events")
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_history_events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_history_events",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    message = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_id} {self.action}"


class Guardian(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="guardians")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    occupation = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name", "id"]
        unique_together = ("school", "full_name", "phone")

    def __str__(self):
        return self.full_name


class StudentGuardian(models.Model):
    RELATION_CHOICES = (
        ("FATHER", "Father"),
        ("MOTHER", "Mother"),
        ("GUARDIAN", "Guardian"),
        ("OTHER", "Other"),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardian_links")
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name="student_links")
    relation = models.CharField(max_length=20, choices=RELATION_CHOICES, default="GUARDIAN")
    relation_text = models.CharField(max_length=60, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "guardian"], name="uniq_guardian_per_student"
            ),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.guardian_id}"
