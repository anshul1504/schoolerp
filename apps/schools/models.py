from django.db import models
from django.utils import timezone
from django.conf import settings

class School(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)

    email = models.EmailField()
    phone = models.CharField(max_length=20)
    support_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    address = models.TextField()
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=12, blank=True)

    principal_name = models.CharField(max_length=255)
    board = models.CharField(max_length=80, blank=True)
    medium = models.CharField(max_length=40, blank=True)
    established_year = models.IntegerField()
    student_capacity = models.PositiveIntegerField(default=1000)
    allowed_campuses = models.PositiveIntegerField(default=1)

    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Campus(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="campuses")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=12, blank=True)

    is_main = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_main", "name", "id"]
        unique_together = [("school", "code")]

    def __str__(self):
        return f"{self.school}: {self.name}"


class SchoolDomain(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="domains")
    domain = models.CharField(max_length=190, unique=True, help_text="Example: erp.yourschool.com")
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "domain", "id"]

    def __str__(self):
        return self.domain


class SchoolCommunicationSettings(models.Model):
    WHATSAPP_PROVIDER_CHOICES = (
        ("NONE", "Not configured"),
        ("TWILIO", "Twilio WhatsApp"),
        ("META_CLOUD", "Meta WhatsApp Cloud API"),
        ("GUPSHUP", "Gupshup"),
        ("OTHER", "Other"),
    )

    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="communication_settings")

    # SMTP
    smtp_enabled = models.BooleanField(default=False)
    smtp_host = models.CharField(max_length=150, blank=True)
    smtp_port = models.PositiveIntegerField(default=465)
    smtp_use_ssl = models.BooleanField(default=True)
    smtp_use_tls = models.BooleanField(default=False)
    smtp_username = models.CharField(max_length=150, blank=True)
    smtp_password = models.CharField(max_length=200, blank=True)
    smtp_from_email = models.EmailField(blank=True)
    smtp_from_name = models.CharField(max_length=150, blank=True)

    # WhatsApp
    whatsapp_enabled = models.BooleanField(default=False)
    whatsapp_provider = models.CharField(max_length=30, choices=WHATSAPP_PROVIDER_CHOICES, default="NONE")
    whatsapp_sender = models.CharField(max_length=80, blank=True)
    whatsapp_access_token = models.CharField(max_length=400, blank=True)
    whatsapp_phone_number_id = models.CharField(max_length=120, blank=True)
    whatsapp_webhook_secret = models.CharField(max_length=120, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comm settings: {self.school}"


class SubscriptionPlan(models.Model):
    TIER_CHOICES = (
        ("SILVER", "Silver"),
        ("GOLD", "Gold"),
        ("PLATINUM", "Platinum"),
    )

    BILLING_MODE_CHOICES = (
        ("FLAT", "Flat monthly"),
        ("PER_STUDENT", "Per student"),
        ("PER_500", "Per 500 students"),
    )

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default="SILVER")

    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_mode = models.CharField(max_length=20, choices=BILLING_MODE_CHOICES, default="FLAT")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    max_students = models.PositiveIntegerField(default=1000)
    max_campuses = models.PositiveIntegerField(default=1)
    features = models.ManyToManyField("PlanFeature", blank=True, related_name="plans")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SchoolSubscription(models.Model):
    STATUS_CHOICES = (
        ("TRIAL", "Trial"),
        ("ACTIVE", "Active"),
        ("PAST_DUE", "Past Due"),
        ("CANCELLED", "Cancelled"),
    )

    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TRIAL")
    starts_on = models.DateField(default=timezone.now)
    ends_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.school} - {self.plan} ({self.status})"

    def is_valid_access(self, today=None):
        today = today or timezone.now().date()
        if not self.school.is_active:
            return False
        if self.status not in {"TRIAL", "ACTIVE"}:
            return False
        if self.ends_on and today > self.ends_on:
            return False
        if today < self.starts_on:
            return False
        return True


class SubscriptionInvoice(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("ISSUED", "Issued"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="subscription_invoices")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="invoices")
    period_start = models.DateField()
    period_end = models.DateField()
    # Billing amounts: keep `amount` as subtotal for backwards compatibility.
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Invoice {self.school} {self.period_start} - {self.period_end}"


class ImplementationProject(models.Model):
    """
    Per-school implementation tracker for SUPER_ADMIN onboarding/rollout.
    """

    STATUS_CHOICES = (
        ("NOT_STARTED", "Not started"),
        ("IN_PROGRESS", "In progress"),
        ("BLOCKED", "Blocked"),
        ("DONE", "Done"),
    )

    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="implementation_project")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NOT_STARTED")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"Implementation: {self.school}"


class ImplementationTask(models.Model):
    STATUS_CHOICES = (
        ("TODO", "To do"),
        ("IN_PROGRESS", "In progress"),
        ("BLOCKED", "Blocked"),
        ("DONE", "Done"),
    )

    project = models.ForeignKey(ImplementationProject, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TODO")
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="implementation_tasks",
    )
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-updated_at", "-id"]

    def __str__(self):
        return self.title


class SubscriptionPayment(models.Model):
    METHOD_CHOICES = (
        ("CASH", "Cash"),
        ("BANK", "Bank Transfer"),
        ("UPI", "UPI"),
        ("CARD", "Card"),
        ("OTHER", "Other"),
    )

    invoice = models.ForeignKey(SubscriptionInvoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="BANK")
    transaction_ref = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at", "-created_at"]

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice_id}"


class SubscriptionCoupon(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ("PERCENT", "Percent"),
        ("FIXED", "Fixed amount"),
    )

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default="PERCENT")
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    used_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "code"]

    def __str__(self):
        return self.code


class PlanFeature(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
