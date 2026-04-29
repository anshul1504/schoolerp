from django.conf import settings
from django.db import models
from django.db.models import JSONField

from apps.schools.models import School
from apps.students.models import Student


class ActivityLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs"
    )

    view_name = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=200, blank=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=255, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)

    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)

    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        actor = getattr(self.actor, "username", None) or "Unknown"
        return f"{actor} {self.method} {self.path} ({self.status_code})"


class PlatformSettings(models.Model):
    product_name = models.CharField(max_length=80, default="SchoolFlow")
    product_meta = models.CharField(max_length=120, default="A product by The Webfix")
    support_email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="platform/", null=True, blank=True)
    favicon = models.ImageField(upload_to="platform/", null=True, blank=True)
    theme_primary = models.CharField(max_length=16, blank=True)
    theme_secondary = models.CharField(max_length=16, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Platform Settings"


class TwoFactorPolicy(models.Model):
    """
    Platform-level 2FA policy (email OTP) to enforce beyond SUPER_ADMIN.

    This complements the env flag `EMAIL_OTP_2FA_ENABLED`:
    - env flag forces 2FA for everyone
    - this model allows targeted enforcement (roles/users)
    """

    require_for_roles = JSONField(default=list, blank=True)
    require_for_user_ids = JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return "2FA Policy"


class RoleSectionsOverride(models.Model):
    role = models.CharField(max_length=40, unique=True)
    sections = JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Role override {self.role}"


class RolePermissionsOverride(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="role_overrides", null=True, blank=True
    )
    role = models.CharField(max_length=40)
    permissions = JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school", "role")

    def __str__(self):
        return (
            f"Permissions override {self.role} for {self.school.name if self.school else 'Global'}"
        )


class ScheduledReport(models.Model):
    REPORT_CHOICES = (
        ("INVOICES", "Billing Invoices (CSV)"),
        ("ACTIVITY", "Activity Log (CSV)"),
        ("STUDENTS", "Students Export (CSV)"),
    )
    FREQUENCY_CHOICES = (
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
    )

    name = models.CharField(max_length=120)
    report_type = models.CharField(max_length=20, choices=REPORT_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="WEEKLY")
    recipients = models.TextField(help_text="Comma-separated emails")
    filters = JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name


class ScheduledReportRun(models.Model):
    STATUS_CHOICES = (
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("SKIPPED", "Skipped"),
    )

    report = models.ForeignKey(ScheduledReport, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    recipients = models.TextField(blank=True)
    filename = models.CharField(max_length=120, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.report_id} {self.status} {self.created_at:%Y-%m-%d %H:%M}"


class PlatformAnnouncement(models.Model):
    SEVERITY_CHOICES = (
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("DANGER", "Danger"),
        ("SUCCESS", "Success"),
    )

    title = models.CharField(max_length=120)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="INFO")
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class SupportTicket(models.Model):
    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    )
    PRIORITY_CHOICES = (
        ("LOW", "Low"),
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    )

    school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_tickets"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets_created",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets_assigned",
    )

    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="NORMAL")

    requester_email = models.EmailField(blank=True)
    requester_phone = models.CharField(max_length=32, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title


class SupportTicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_messages",
    )
    body = models.TextField()
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Ticket {self.ticket_id} message"


class AuthSecurityEvent(models.Model):
    EVENT_CHOICES = (
        ("LOGIN_SUCCESS", "Login success"),
        ("LOGIN_FAIL", "Login failed"),
        ("LOGIN_LOCKED", "Login locked"),
        ("OTP_SENT", "OTP sent"),
        ("OTP_VERIFY_SUCCESS", "OTP verified"),
        ("OTP_VERIFY_FAIL", "OTP verify failed"),
        ("THROTTLED", "Throttled"),
    )

    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    username = models.CharField(max_length=150, blank=True)
    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.event} {self.username} {self.ip_address}"


class AuditLogExport(models.Model):
    """
    Immutable export record for ActivityLog.

    "Immutable" here means: exports are write-once (new row + new file), never edited or deleted via the UI,
    and each export stores a SHA256 checksum and links to the previous export checksum for tamper-evidence.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_log_exports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    filters = JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)

    prev_sha256 = models.CharField(max_length=64, blank=True)
    sha256 = models.CharField(max_length=64)
    file = models.FileField(upload_to="audit_exports/")
    immutable_copy_path = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Audit export {self.id} {self.created_at:%Y-%m-%d %H:%M} ({self.row_count})"


class RBACChangeEvent(models.Model):
    """
    Immutable audit history for RBAC changes (role sections/permissions overrides).
    """

    KIND_CHOICES = (
        ("ROLE_SECTIONS_OVERRIDE", "Role sections override"),
        ("ROLE_PERMISSIONS_OVERRIDE", "Role permissions override"),
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rbac_change_events",
    )
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    role = models.CharField(max_length=20)

    before = JSONField(default=dict, blank=True)
    after = JSONField(default=dict, blank=True)

    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        who = getattr(self.actor, "username", None) or "Unknown"
        return f"{who} {self.kind} {self.role} {self.created_at:%Y-%m-%d %H:%M}"


class EntityChangeLog(models.Model):
    """
    Field-level change history for key entities (tamper-evident at DB layer via append-only usage).

    This is intentionally generic so we can attach it to multiple models without duplicating tables.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entity_change_logs",
    )
    entity = models.CharField(max_length=80)  # e.g. "schools.School"
    object_id = models.CharField(max_length=64)  # store as str to support int/uuid
    action = models.CharField(max_length=20)  # CREATED/UPDATED/DELETED
    changes = JSONField(default=dict, blank=True)  # {"field": {"before":..., "after":...}}
    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["entity", "object_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.entity}:{self.object_id} {self.action} {self.created_at:%Y-%m-%d %H:%M}"


class ReportTemplate(models.Model):
    DATASET_CHOICES = (
        ("SCHOOLS", "Schools"),
        ("USERS", "Users"),
        ("ACTIVITY", "Activity Log"),
        ("STUDENTS", "Students"),
        ("FEES_PAYMENTS", "Fee Payments"),
        ("FEES_LEDGER", "Fee Ledgers"),
    )

    name = models.CharField(max_length=140)
    dataset = models.CharField(max_length=30, choices=DATASET_CHOICES)
    filters = JSONField(default=dict, blank=True)
    columns = JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.name


class BillingWebhookEvent(models.Model):
    provider = models.CharField(max_length=40, default="GENERIC")
    event_id = models.CharField(max_length=120, unique=True)
    event_type = models.CharField(max_length=80, blank=True)
    invoice_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=40, blank=True)
    payload = JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    process_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.provider}:{self.event_id}"


class IntegrationToken(models.Model):
    name = models.CharField(max_length=120)
    token = models.CharField(max_length=64, unique=True)
    scopes = JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="inventory_items")
    sku = models.CharField(max_length=40)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=80, blank=True)
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=20, default="unit")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "name", "-id"]
        unique_together = ("school", "sku")

    def __str__(self):
        return f"{self.school.code} {self.sku}"


class InventoryVendor(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="inventory_vendors")
    name = models.CharField(max_length=160)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    gstin = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "name", "-id"]
        unique_together = ("school", "name")

    def __str__(self):
        return f"{self.school.code} {self.name}"


class InventoryPurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PLACED", "Placed"),
        ("RECEIVED", "Received"),
        ("CANCELLED", "Cancelled"),
    )

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="inventory_purchase_orders"
    )
    vendor = models.ForeignKey(
        InventoryVendor, on_delete=models.CASCADE, related_name="purchase_orders"
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="purchase_orders"
    )
    po_number = models.CharField(max_length=40)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLACED")
    notes = models.CharField(max_length=255, blank=True)
    ordered_on = models.DateField(auto_now_add=True)
    received_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("school", "po_number")

    def __str__(self):
        return f"{self.school.code} {self.po_number}"


class InventoryMovement(models.Model):
    MOVEMENT_CHOICES = (
        ("IN", "Stock In"),
        ("OUT", "Stock Out"),
        ("ADJUST", "Adjustment"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="inventory_movements")
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.school.code} {self.item_id} {self.movement_type} {self.quantity}"


class ServiceRefundEvent(models.Model):
    SERVICE_CHOICES = (
        ("TRANSPORT", "Transport"),
        ("HOSTEL", "Hostel"),
    )
    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("SETTLED", "Settled"),
    )

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="service_refund_events"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="service_refund_events"
    )
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    fee_ledger = models.ForeignKey(
        "fees.StudentFeeLedger",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_refund_events",
    )
    source = models.CharField(max_length=40, blank=True)
    source_ref = models.CharField(max_length=64, blank=True)
    billed_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    policy_ratio = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    days_remaining = models.PositiveIntegerField(default=0)
    total_days = models.PositiveIntegerField(default=0)
    recommended_refund = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.school.code} {self.student_id} {self.service_type} {self.recommended_refund}"


class LabRoom(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="lab_rooms")
    room_number = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    capacity = models.PositiveIntegerField(default=30)
    in_charge_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "name"]
        unique_together = ("school", "room_number")

    def __str__(self):
        return f"{self.school.code} - {self.name} ({self.room_number})"


class LabEquipment(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="lab_equipment")
    lab = models.ForeignKey(LabRoom, on_delete=models.CASCADE, related_name="equipments")
    name = models.CharField(max_length=180)
    sku = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=40, default="GOOD")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["lab__name", "name"]

    def __str__(self):
        return f"{self.lab.name} - {self.name}"


class LabBooking(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("COMPLETED", "Completed"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="lab_bookings")
    lab = models.ForeignKey(LabRoom, on_delete=models.CASCADE, related_name="bookings")
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="lab_bookings"
    )
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    purpose = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-booking_date", "-start_time"]

    def __str__(self):
        return f"{self.lab.name} on {self.booking_date}"


class SystemBackup(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    )

    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="backups/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    size_bytes = models.BigIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} ({self.status})"


class ServiceConfiguration(models.Model):
    """
    Platform-wide service configurations (Cloud Gateway).
    """

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_secret = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key
