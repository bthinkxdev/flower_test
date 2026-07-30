"""Data layer for the catalog app — models only, no business logic."""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import ArabicTranslationMixin, TimeStampedModel


class Category(ArabicTranslationMixin, TimeStampedModel):
    """Hierarchical product category tree."""

    name = models.CharField(
        max_length=120,
        verbose_name="Name",
        help_text="Display name of the category.",
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        db_index=True,
        verbose_name="Slug",
        help_text="URL-friendly category identifier.",
    )
    meta_title = models.CharField(max_length=70, blank=True, verbose_name="Meta title")
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="Meta description")
    og_image = models.ImageField(
        upload_to="seo/categories/",
        blank=True,
        null=True,
        verbose_name="Open Graph image",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Parent category",
        help_text="Parent node in the category tree; null for top-level.",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Display order",
        help_text="Lower values appear first in navigation.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Is active",
        help_text="When False, category is hidden from the storefront.",
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["is_active"], name="cat_category_is_active_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Occasion(ArabicTranslationMixin, TimeStampedModel):
    """Gift occasion used for merchandising and PLP filters."""

    name = models.CharField(max_length=120, verbose_name="Name")
    slug = models.SlugField(
        max_length=120,
        unique=True,
        db_index=True,
        verbose_name="Slug",
    )
    icon = models.ImageField(
        upload_to="occasions/icons/",
        blank=True,
        verbose_name="Icon",
        help_text="Small icon shown on occasion chips.",
    )
    is_seasonal = models.BooleanField(
        default=False,
        verbose_name="Is seasonal",
        help_text="When True, occasion is only promoted within active date range.",
    )
    active_from = models.DateField(
        null=True,
        blank=True,
        verbose_name="Active from",
        help_text="First day this seasonal occasion is promoted.",
    )
    active_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="Active to",
        help_text="Last day this seasonal occasion is promoted.",
    )

    class Meta:
        verbose_name = "Occasion"
        verbose_name_plural = "Occasions"
        indexes = [
            models.Index(fields=["slug"], name="cat_occasion_slug_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Brand(ArabicTranslationMixin, TimeStampedModel):
    """Product brand for filtering and brand pages."""

    name = models.CharField(max_length=120, verbose_name="Name")
    slug = models.SlugField(
        max_length=120,
        unique=True,
        db_index=True,
        verbose_name="Slug",
    )
    logo = models.ImageField(
        upload_to="brands/logos/",
        blank=True,
        verbose_name="Logo",
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is featured",
        help_text="Featured brands appear on the homepage.",
    )

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"
        indexes = [
            models.Index(fields=["is_featured"], name="cat_brand_is_featured_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Recipient(ArabicTranslationMixin, TimeStampedModel):
    """Recipient persona for shop-by-recipient merchandising (e.g. Mother, Father)."""

    name = models.CharField(max_length=120, verbose_name="Name")
    slug = models.SlugField(
        max_length=120,
        unique=True,
        db_index=True,
        verbose_name="Slug",
        help_text="URL-friendly recipient identifier.",
    )
    icon = models.ImageField(
        upload_to="recipients/icons/",
        blank=True,
        verbose_name="Icon",
        help_text="Small icon shown on recipient chips.",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Display order",
        help_text="Lower values appear first.",
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")

    class Meta:
        verbose_name = "Recipient"
        verbose_name_plural = "Recipients"
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["is_active"], name="cat_recipient_active_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Product(ArabicTranslationMixin, TimeStampedModel):
    """Core sellable product — highest read volume entity in the platform."""

    name = models.CharField(max_length=255, verbose_name="Name")
    slug = models.SlugField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name="Slug",
    )
    sku = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="SKU",
        help_text="Stock keeping unit identifier.",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Category",
    )
    primary_occasion = models.ForeignKey(
        Occasion,
        on_delete=models.PROTECT,
        related_name="primary_products",
        verbose_name="Primary occasion",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Brand",
    )
    recipients = models.ManyToManyField(
        Recipient,
        blank=True,
        related_name="products",
        verbose_name="Recipients",
        help_text="Recipient personas this product is suitable for.",
    )
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Base price",
        help_text="Default price before variant deltas.",
    )
    color = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name="Color",
        help_text="Primary color for PLP color-filter chips.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Is active",
    )
    is_same_day_eligible = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Same-day eligible",
    )
    is_bestseller = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is bestseller",
    )
    is_new_arrival = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is new arrival",
    )
    supports_gift_customization = models.BooleanField(
        default=False,
        verbose_name="Supports gift customization",
        help_text="When True, gifting app attaches customization options via ContentType.",
    )
    stock_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Stock quantity",
    )
    meta_title = models.CharField(max_length=70, blank=True, verbose_name="Meta title")
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="Meta description")
    og_image = models.ImageField(
        upload_to="seo/products/",
        blank=True,
        null=True,
        verbose_name="Open Graph image",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        verbose_name="Low stock threshold",
        help_text="Triggers low-stock alerts when stock falls at or below this value.",
    )

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        indexes = [
            models.Index(
                fields=["is_active", "category_id"],
                name="cat_prod_active_category_idx",
            ),
            models.Index(
                fields=["is_active", "is_bestseller"],
                name="cat_prod_active_bestseller_idx",
            ),
            models.Index(fields=["is_active", "is_new_arrival"], name="cat_prod_active_new_idx"),
            models.Index(
                fields=["is_active", "is_same_day_eligible"], name="cat_prod_same_day_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_in_stock(self) -> bool:
        """True when aggregate product stock is available."""
        return self.stock_quantity > 0


class VariantType(models.TextChoices):
    """Allowed product variant dimensions."""

    SIZE = "size", "Size"
    PACKAGING = "packaging", "Packaging"


class ProductVariant(ArabicTranslationMixin, TimeStampedModel):
    """Purchasable variant altering price and/or stock."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="Product",
    )
    variant_type = models.CharField(
        max_length=50,
        verbose_name="Variant type",
    )
    name = models.CharField(max_length=120, verbose_name="Name")
    price_delta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Price delta",
        help_text="Amount added to the product base price.",
    )
    sku_suffix = models.CharField(
        max_length=32,
        verbose_name="SKU suffix",
        help_text="Appended to the parent product SKU.",
    )
    stock_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Stock quantity",
    )

    class Meta:
        verbose_name = "Product variant"
        verbose_name_plural = "Product variants"
        unique_together = [("product", "variant_type", "name")]

    def __str__(self) -> str:
        return f"{self.product.sku}-{self.sku_suffix}"


class ProductImage(ArabicTranslationMixin, TimeStampedModel):
    """Gallery image for a product."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Product",
    )
    image = models.ImageField(
        upload_to="products/images/",
        verbose_name="Image",
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Alt text",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Display order",
    )
    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is primary",
        help_text="Primary image shown on PLP cards and homepage rails.",
    )

    class Meta:
        verbose_name = "Product image"
        verbose_name_plural = "Product images"
        ordering = ["display_order"]
        indexes = [
            models.Index(
                fields=["product", "is_primary"],
                name="cat_img_product_primary_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Image for {self.product.slug}"


class ProductVideo(TimeStampedModel):
    """Hosted or external video for a product detail page."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="videos",
        verbose_name="Product",
    )
    video_url = models.URLField(verbose_name="Video URL")
    thumbnail = models.ImageField(
        upload_to="products/video_thumbs/",
        blank=True,
        verbose_name="Thumbnail",
    )

    class Meta:
        verbose_name = "Product video"
        verbose_name_plural = "Product videos"

    def __str__(self) -> str:
        return f"Video for {self.product.slug}"


class RelationType(models.TextChoices):
    """Types of product-to-product relationships."""

    RELATED = "related", "Related"
    FREQUENTLY_BOUGHT_TOGETHER = "fbt", "Frequently Bought Together"


class ProductRelation(TimeStampedModel):
    """Directed relationship between two products."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="relations",
        verbose_name="Product",
    )
    related_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="related_from",
        verbose_name="Related product",
    )
    relation_type = models.CharField(
        max_length=20,
        choices=RelationType.choices,
        verbose_name="Relation type",
    )

    class Meta:
        verbose_name = "Product relation"
        verbose_name_plural = "Product relations"
        unique_together = [("product", "related_product", "relation_type")]

    def __str__(self) -> str:
        return f"{self.product.slug} -> {self.related_product.slug} ({self.relation_type})"


class ModerationStatus(models.TextChoices):
    """Review moderation workflow states."""

    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Review(TimeStampedModel):
    """Customer product review subject to moderation."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Product",
    )
    customer = models.ForeignKey(
        "accounts.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Customer",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Rating",
    )
    title = models.CharField(max_length=200, verbose_name="Title")
    body = models.TextField(verbose_name="Body")
    is_verified_purchase = models.BooleanField(
        default=False,
        verbose_name="Verified purchase",
    )
    moderation_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
        verbose_name="Moderation status",
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews",
        verbose_name="Moderated by",
    )

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        indexes = [
            models.Index(
                fields=["product", "moderation_status"],
                name="cat_review_product_mod_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rating}★ — {self.product.slug}"


class ReviewPhoto(TimeStampedModel):
    """Photo attached to a customer review."""

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Review",
    )
    image = models.ImageField(
        upload_to="reviews/photos/",
        verbose_name="Image",
    )

    class Meta:
        verbose_name = "Review photo"
        verbose_name_plural = "Review photos"

    def __str__(self) -> str:
        return f"Photo for review {self.review_id}"
