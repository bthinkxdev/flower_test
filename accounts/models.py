"""Data layer for the accounts app — models only, no business logic."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class OTPPurpose(models.TextChoices):
    """Allowed purposes for a one-time password request."""

    LOGIN = "login", "Login"
    SIGNUP = "signup", "Sign Up"
    PASSWORD_RESET = "password_reset", "Password Reset"
    EMAIL_LOGIN = "email_login", "Email Login"


class CorporateApprovalStatus(models.TextChoices):
    """Approval workflow states for B2B corporate accounts."""

    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class CustomerProfile(TimeStampedModel):
    """Extended profile for a registered retail customer."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
        verbose_name="User",
        help_text="Linked Django auth user.",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        verbose_name="Phone number",
        help_text="Customer mobile number used for OTP login.",
    )
    phone_verified = models.BooleanField(
        default=False,
        verbose_name="Phone verified",
        help_text="True after a successful OTP verification for this phone.",
    )
    preferred_language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name="Preferred language",
        help_text="Customer's preferred storefront language.",
    )
    preferred_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT,
        related_name="customer_profiles",
        verbose_name="Preferred currency",
        help_text="Currency used to display prices for this customer.",
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date of birth",
        help_text="Optional date of birth for personalization.",
    )
    default_address = models.ForeignKey(
        "accounts.Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Default address",
        help_text="Customer's primary delivery address.",
    )
    notify_via_email = models.BooleanField(
        default=True,
        verbose_name="Email notifications",
        help_text="Receive order updates via email.",
    )
    notify_via_sms = models.BooleanField(
        default=True,
        verbose_name="SMS notifications",
        help_text="Receive order updates via SMS.",
    )
    notify_via_whatsapp = models.BooleanField(
        default=False,
        verbose_name="WhatsApp notifications",
        help_text="Receive order updates via WhatsApp.",
    )

    class Meta:
        verbose_name = "Customer profile"
        verbose_name_plural = "Customer profiles"
        indexes = [
            models.Index(fields=["phone"], name="accounts_profile_phone_idx"),
        ]

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.email or str(self.pk)


class Address(TimeStampedModel):
    """Saved delivery address belonging to a customer profile."""

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="addresses",
        verbose_name="Customer profile",
        help_text="Owner of this address.",
    )
    contact_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    label = models.CharField(
        max_length=50,
        verbose_name="Label",
        help_text="Short label, e.g. Home or Office.",
    )
    line1 = models.CharField(
        max_length=255,
        verbose_name="Address line 1",
        help_text="Street address or building name.",
    )
    line2 = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Address line 2",
        help_text="Apartment, floor, or additional directions.",
    )
    city = models.ForeignKey(
        "delivery.City",
        on_delete=models.PROTECT,
        related_name="addresses",
        verbose_name="City",
        help_text="Deliverable city for this address.",
    )
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is default",
        help_text="When True, this is the customer's primary delivery address.",
    )

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"
        indexes = [
            models.Index(
                fields=["customer_profile", "is_default"],
                name="accounts_address_default_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["customer_profile"],
                condition=models.Q(is_default=True),
                name="accounts_one_default_address_per_customer",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label}: {self.line1}"


class SavedPaymentMethod(TimeStampedModel):
    """Tokenized payment method — never stores raw card data."""

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="saved_payment_methods",
        verbose_name="Customer profile",
        help_text="Owner of this saved payment method.",
    )
    gateway_token = models.CharField(
        max_length=255,
        verbose_name="Gateway token",
        help_text="Opaque token returned by the payment gateway.",
    )
    card_brand = models.CharField(
        max_length=30,
        verbose_name="Card brand",
        help_text="Card network, e.g. Visa or Mastercard.",
    )
    last4 = models.CharField(
        max_length=4,
        verbose_name="Last four digits",
        help_text="Last four digits of the card number for display.",
    )
    expiry_month = models.PositiveSmallIntegerField(
        verbose_name="Expiry month",
        help_text="Card expiry month (1–12).",
    )
    expiry_year = models.PositiveSmallIntegerField(
        verbose_name="Expiry year",
        help_text="Card expiry four-digit year.",
    )
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is default",
        help_text="When True, this card is pre-selected at checkout.",
    )

    class Meta:
        verbose_name = "Saved payment method"
        verbose_name_plural = "Saved payment methods"
        constraints = [
            models.UniqueConstraint(
                fields=["customer_profile"],
                condition=models.Q(is_default=True),
                name="accounts_one_default_payment_per_customer",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.card_brand} •••• {self.last4}"


class CorporateAccount(TimeStampedModel):
    """B2B corporate account linked to a Django user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="corporate_account",
        verbose_name="User",
        help_text="Corporate account manager login.",
    )
    company_name = models.CharField(
        max_length=200,
        verbose_name="Company name",
        help_text="Registered legal or trading name.",
    )
    trade_license_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="Trade license number",
        help_text="Government-issued trade license identifier.",
    )
    approval_status = models.CharField(
        max_length=20,
        choices=CorporateApprovalStatus.choices,
        default=CorporateApprovalStatus.PENDING,
        db_index=True,
        verbose_name="Approval status",
        help_text="Current admin review state.",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_corporate_accounts",
        verbose_name="Approved by",
        help_text="Admin user who approved or rejected this account.",
    )

    class Meta:
        verbose_name = "Corporate account"
        verbose_name_plural = "Corporate accounts"
        indexes = [
            models.Index(
                fields=["approval_status"],
                name="acct_corp_approval_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.company_name


class OTPRequest(TimeStampedModel):
    """Hashed one-time password issued for phone-based authentication."""

    phone = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        verbose_name="Phone number",
        help_text="Phone number the OTP was sent to.",
    )
    email = models.CharField(
        max_length=254,
        blank=True,
        db_index=True,
        verbose_name="Email address",
        help_text="Email the OTP was sent to (email-based purposes only).",
    )
    otp_hash = models.CharField(
        max_length=128,
        verbose_name="OTP hash",
        help_text="Hashed OTP value — plaintext is never stored.",
    )
    purpose = models.CharField(
        max_length=20,
        choices=OTPPurpose.choices,
        db_index=True,
        verbose_name="Purpose",
        help_text="Reason this OTP was issued.",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        verbose_name="Expires at",
        help_text="Timestamp after which this OTP is invalid.",
    )
    is_used = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is used",
        help_text="True once the OTP has been successfully verified.",
    )
    attempt_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Attempt count",
        help_text="Number of failed verification attempts.",
    )

    class Meta:
        verbose_name = "OTP request"
        verbose_name_plural = "OTP requests"
        indexes = [
            models.Index(
                fields=["phone", "purpose", "is_used"],
                name="accounts_otp_phone_purpose_idx",
            ),
            models.Index(
                fields=["email", "purpose", "is_used"], 
                name="accounts_otp_email_purpose_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"OTP {self.purpose} for {self.phone}"


class SubscriptionStatus(models.TextChoices):
    """Customer-facing subscription lifecycle (mirrors recurring schedule)."""

    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    CANCELLED = "cancelled", "Cancelled"


class Subscription(TimeStampedModel):
    """Customer product subscription, e.g. weekly flowers."""

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name="Customer profile",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Product",
    )
    recurring_schedule = models.OneToOneField(
        "recurring.RecurringSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription",
        verbose_name="Recurring schedule",
    )
    delivery_address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Delivery address",
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
        verbose_name="Status",
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantity")

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        indexes = [
            models.Index(fields=["customer_profile", "status"], name="acct_sub_customer_idx"),
        ]

    def __str__(self) -> str:
        return f"Subscription #{self.pk} — {self.product.name}"


class Wishlist(TimeStampedModel):
    """Persistent wishlist for a customer or guest session."""

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wishlists",
        verbose_name="Customer profile",
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Session key",
    )
    share_token = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name="Share token",
        help_text="Signed token for read-only shared access.",
    )

    class Meta:
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(customer_profile__isnull=False, session_key__isnull=True)
                    | models.Q(customer_profile__isnull=True, session_key__isnull=False)
                ),
                name="wishlist_owner_xor",
            ),
        ]

    def __str__(self) -> str:
        owner = self.customer_profile_id or self.session_key
        return f"Wishlist #{self.pk} ({owner})"


class WishlistItem(TimeStampedModel):
    """Product saved on a wishlist."""

    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Wishlist",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="wishlist_items",
        verbose_name="Product",
    )

    class Meta:
        verbose_name = "Wishlist item"
        verbose_name_plural = "Wishlist items"
        constraints = [
            models.UniqueConstraint(fields=["wishlist", "product"], name="wishlist_item_unique"),
        ]

    def __str__(self) -> str:
        return f"Wishlist item {self.product_id}"


class GiftOccasionType(models.TextChoices):
    """Occasion types for gift calendar reminders."""

    BIRTHDAY = "birthday", "Birthday"
    ANNIVERSARY = "anniversary", "Anniversary"
    VALENTINE = "valentine", "Valentine's Day"
    MOTHERS_DAY = "mothers_day", "Mother's Day"
    FATHERS_DAY = "fathers_day", "Father's Day"
    RAMADAN = "ramadan", "Ramadan"
    EID = "eid", "Eid"
    CUSTOM = "custom", "Custom"


class GiftReminder(TimeStampedModel):
    """Customer gift calendar reminder."""

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="gift_reminders",
        verbose_name="Customer profile",
    )
    occasion_type = models.CharField(
        max_length=20,
        choices=GiftOccasionType.choices,
        verbose_name="Occasion type",
    )
    reminder_date = models.DateField(db_index=True, verbose_name="Reminder date")
    recipient_name = models.CharField(max_length=120, verbose_name="Recipient name")
    notes = models.TextField(blank=True, verbose_name="Notes")
    notify_days_before = models.PositiveSmallIntegerField(
        default=7,
        verbose_name="Notify days before",
    )
    last_notified_on = models.DateField(
        null=True,
        blank=True,
        verbose_name="Last notified on",
    )

    class Meta:
        verbose_name = "Gift reminder"
        verbose_name_plural = "Gift reminders"
        ordering = ["reminder_date"]
        indexes = [
            models.Index(
                fields=["customer_profile", "reminder_date"],
                name="gift_rem_customer_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.occasion_type} for {self.recipient_name}"
