"""Data layer for the gifting app — models only, no business logic."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from catalog.models import Occasion, Product
from core.models import TimeStampedModel
from gifting.constants import PERSONAL_MESSAGE_MAX_LENGTH


class BaseCustomizationOption(TimeStampedModel):
    """
    Abstract base for priced, toggleable customization options.

    PLUG-AND-PLAY EXTENSION PATTERN
    -------------------------------
    To add a new option type (e.g. Photo Upload) without touching cart/checkout:

    1. Subclass this model::
           class GiftPhotoUploadOption(BaseCustomizationOption):
               name = models.CharField(max_length=120)

    2. Add ``allows_photo_upload`` (or similar) boolean to GiftCustomizationConfig.

    3. Add one validation/resolution branch in
       ``gifting.services.build_gift_customization_snapshot``.

    Cart, checkout, and order confirmation only consume GiftCustomizationSnapshot
    via ``get_gift_customization_snapshot`` — zero changes required in those apps.
    """

    price_delta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Price delta",
        help_text="Amount added to the line item when this option is selected.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Is active",
        help_text="When False, option is hidden from the gift builder.",
    )

    class Meta:
        abstract = True


class GiftCustomizationConfig(TimeStampedModel):
    """
    Per-instance gift customization toggles attached via ContentType.

    Never hard-FK to catalog.Product — any current or future product type can
    receive a config row without a catalog migration.
    """

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="gift_customization_configs",
        verbose_name="Content type",
        help_text="Django content type of the customizable product instance.",
    )
    object_id = models.PositiveBigIntegerField(
        verbose_name="Object ID",
        help_text="Primary key of the customizable product instance.",
    )
    target = GenericForeignKey("content_type", "object_id")

    allows_personal_message = models.BooleanField(default=True, verbose_name="Personal message")
    allows_greeting_card = models.BooleanField(default=True, verbose_name="Greeting card")
    allows_gift_wrap = models.BooleanField(default=True, verbose_name="Gift wrap")
    allows_ribbon = models.BooleanField(default=True, verbose_name="Ribbon")
    allows_addons = models.BooleanField(default=True, verbose_name="Add-ons")
    allows_anonymous = models.BooleanField(default=True, verbose_name="Anonymous delivery")
    allows_gift_receipt = models.BooleanField(default=True, verbose_name="Gift receipt")
    allows_midnight_delivery = models.BooleanField(default=False, verbose_name="Midnight delivery")
    allows_photo_upload = models.BooleanField(
        default=False,
        verbose_name="Photo upload",
        help_text="When True, customer may attach a photo upload option at checkout.",
    )

    class Meta:
        verbose_name = "Gift customization config"
        verbose_name_plural = "Gift customization configs"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="gifting_config_unique_target",
            ),
        ]
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="gifting_config_ct_obj_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Gift config for {self.content_type_id}:{self.object_id}"


class GreetingCardDesign(TimeStampedModel):
    """Shared greeting-card design library — coupled to occasions, not products."""

    name = models.CharField(max_length=120, verbose_name="Name")
    occasion = models.ForeignKey(
        Occasion,
        on_delete=models.PROTECT,
        related_name="greeting_card_designs",
        verbose_name="Occasion",
        help_text="Occasion this design is associated with.",
    )
    image = models.ImageField(
        upload_to="gifting/greeting_cards/",
        verbose_name="Image",
        help_text="Preview image shown in the greeting card gallery.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Is active",
    )

    class Meta:
        verbose_name = "Greeting card design"
        verbose_name_plural = "Greeting card designs"
        indexes = [
            models.Index(
                fields=["is_active", "occasion_id"],
                name="gifting_card_active_occ_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class GiftWrapName(models.TextChoices):
    """Allowed gift-wrap styles."""

    STANDARD = "standard", "Standard"
    PREMIUM = "premium", "Premium"
    LUXURY_BOX = "luxury_box", "Luxury Box"
    TRANSPARENT = "transparent", "Transparent"
    ECO_FRIENDLY = "eco_friendly", "Eco Friendly"


class GiftWrapOption(BaseCustomizationOption):
    """Selectable gift-wrap style with a price delta."""

    name = models.CharField(
        max_length=30,
        choices=GiftWrapName.choices,
        unique=True,
        verbose_name="Name",
    )

    class Meta:
        verbose_name = "Gift wrap option"
        verbose_name_plural = "Gift wrap options"

    def __str__(self) -> str:
        return self.get_name_display()


class RibbonName(models.TextChoices):
    """Allowed ribbon colours."""

    RED = "red", "Red"
    GOLD = "gold", "Gold"
    WHITE = "white", "White"
    BLACK = "black", "Black"
    PINK = "pink", "Pink"
    BLUE = "blue", "Blue"
    THEME = "theme", "Theme"


class RibbonOption(BaseCustomizationOption):
    """Selectable ribbon colour with a price delta."""

    name = models.CharField(
        max_length=20,
        choices=RibbonName.choices,
        unique=True,
        verbose_name="Name",
    )

    class Meta:
        verbose_name = "Ribbon option"
        verbose_name_plural = "Ribbon options"

    def __str__(self) -> str:
        return self.get_name_display()


class GiftPhotoUploadOption(BaseCustomizationOption):
    """
    Example plug-and-play option type — photo upload surcharge.

    Proves the extension pattern documented on BaseCustomizationOption.
    """

    name = models.CharField(max_length=120, verbose_name="Name")

    class Meta:
        verbose_name = "Photo upload option"
        verbose_name_plural = "Photo upload options"

    def __str__(self) -> str:
        return self.name


class GiftAddonEligibility(TimeStampedModel):
    """
    Links eligible add-on catalog products to a primary customizable instance.

    Uses ContentType so eligibility is not hard-FK'd to catalog.Product as the
    primary target (though add-ons themselves are catalog.Product rows).
    """

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="gift_addon_eligibilities",
        verbose_name="Content type",
    )
    object_id = models.PositiveBigIntegerField(verbose_name="Object ID")
    target = GenericForeignKey("content_type", "object_id")
    addon_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="gift_addon_eligibilities",
        verbose_name="Add-on product",
        help_text="Catalog product offered as an add-on for the primary target.",
    )

    class Meta:
        verbose_name = "Gift add-on eligibility"
        verbose_name_plural = "Gift add-on eligibilities"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "addon_product"],
                name="gifting_addon_eligibility_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="gifting_addon_elig_ct_obj_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Add-on {self.addon_product_id} for {self.content_type_id}:{self.object_id}"


class GiftLineItemRef(TimeStampedModel):
    """
    Opaque line-item anchor for snapshots before cart owns line items (Phase 6).

    GiftCustomizationSnapshot attaches here via GenericForeignKey so gifting
    has zero dependency on the cart app today.
    """

    class Meta:
        verbose_name = "Gift line item reference"
        verbose_name_plural = "Gift line item references"

    def __str__(self) -> str:
        return f"LineItemRef #{self.pk}"


class GiftCustomizationSnapshot(TimeStampedModel):
    """
    Immutable resolved gift customization attached to a line-item reference.

    ``snapshot_json`` captures prices at creation time so later admin edits to
    option pricing never retroactively alter historical orders.
    """

    line_item_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="gift_snapshots",
        verbose_name="Line item content type",
    )
    line_item_object_id = models.PositiveBigIntegerField(verbose_name="Line item object ID")
    line_item = GenericForeignKey("line_item_content_type", "line_item_object_id")

    personal_message = models.TextField(
        blank=True,
        max_length=PERSONAL_MESSAGE_MAX_LENGTH,
        verbose_name="Personal message",
    )
    greeting_card = models.ForeignKey(
        GreetingCardDesign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
        verbose_name="Greeting card",
    )
    gift_wrap = models.ForeignKey(
        GiftWrapOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
        verbose_name="Gift wrap",
    )
    ribbon = models.ForeignKey(
        RibbonOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
        verbose_name="Ribbon",
    )
    photo_upload = models.ForeignKey(
        GiftPhotoUploadOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
        verbose_name="Photo upload",
    )
    delivery_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Delivery date",
    )
    delivery_slot = models.ForeignKey(
        "delivery.DeliverySlot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gift_snapshots",
        verbose_name="Delivery slot",
    )
    delivery_instructions = models.TextField(blank=True, verbose_name="Delivery instructions")
    recipient_phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Recipient phone",
    )
    is_anonymous = models.BooleanField(default=False, verbose_name="Anonymous delivery")
    reveal_sender_after_delivery = models.BooleanField(
        default=False,
        verbose_name="Reveal sender after delivery",
    )
    is_gift_receipt = models.BooleanField(
        default=False,
        verbose_name="Gift receipt",
        help_text="When True, pricing is excluded from the packing slip.",
    )
    snapshot_json = models.JSONField(
        default=dict,
        verbose_name="Snapshot JSON",
        help_text="Full resolved selection and prices at snapshot creation time.",
    )

    class Meta:
        verbose_name = "Gift customization snapshot"
        verbose_name_plural = "Gift customization snapshots"
        indexes = [
            models.Index(
                fields=["line_item_content_type", "line_item_object_id"],
                name="gifting_snapshot_line_item_idx",
            ),
            models.Index(fields=["delivery_date"], name="gifting_snapshot_del_date_idx"),
        ]

    def __str__(self) -> str:
        return f"Gift snapshot #{self.pk}"


class GiftSnapshotAddon(TimeStampedModel):
    """Through model capturing add-on price at snapshot creation time."""

    snapshot = models.ForeignKey(
        GiftCustomizationSnapshot,
        on_delete=models.CASCADE,
        related_name="snapshot_addons",
        verbose_name="Snapshot",
    )
    addon_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="gift_snapshot_addons",
        verbose_name="Add-on product",
    )
    price_at_time_of_purchase = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Price at purchase",
        help_text="Resolved catalog price when the snapshot was created.",
    )

    class Meta:
        verbose_name = "Gift snapshot add-on"
        verbose_name_plural = "Gift snapshot add-ons"
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "addon_product"],
                name="gifting_snapshot_addon_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.addon_product_id} @ {self.price_at_time_of_purchase}"
