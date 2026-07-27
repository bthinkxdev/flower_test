"""Django admin registrations for the catalog app."""

from __future__ import annotations

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline

from catalog.models import (
    Brand,
    Category,
    Occasion,
    Product,
    ProductImage,
    ProductRelation,
    ProductVariant,
    ProductVideo,
    Recipient,
    Review,
    ReviewPhoto,
)


@admin.register(Category)
class CategoryAdmin(TabbedTranslationAdmin):
    """Admin for category tree."""

    list_display = ("name", "slug", "parent", "display_order", "is_active", "updated_at")
    list_filter = ("is_active", "ar_translation_source")
    search_fields = ("name", "slug")
    list_select_related = ("parent",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")


@admin.register(Occasion)
class OccasionAdmin(TabbedTranslationAdmin):
    """Admin for gift occasions."""

    list_display = ("name", "slug", "is_seasonal", "active_from", "active_to", "updated_at")
    list_filter = ("is_seasonal", "ar_translation_source")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Recipient)
class RecipientAdmin(TabbedTranslationAdmin):
    """Admin for shop-by-recipient personas."""

    list_display = ("name", "slug", "display_order", "is_active", "updated_at")
    list_filter = ("is_active", "ar_translation_source")
    list_editable = ("display_order", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")


@admin.register(Brand)
class BrandAdmin(TabbedTranslationAdmin):
    """Admin for product brands."""

    list_display = ("name", "slug", "is_featured", "updated_at")
    list_filter = ("is_featured", "ar_translation_source")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(TranslationTabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(TranslationTabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(TabbedTranslationAdmin):
    """Admin for products — list_select_related prevents N+1 on list view."""

    list_display = (
        "name",
        "sku",
        "category",
        "brand",
        "base_price",
        "is_active",
        "is_bestseller",
        "stock_quantity",
        "updated_at",
    )
    list_filter = (
        "is_active",
        "is_bestseller",
        "is_new_arrival",
        "is_same_day_eligible",
        "supports_gift_customization",
        "ar_translation_source",
        "category",
        "brand",
    )
    search_fields = ("name", "slug", "sku")
    list_select_related = ("category", "brand", "primary_occasion")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("recipients",)
    inlines = [ProductVariantInline, ProductImageInline]
    ordering = ("name",)


@admin.register(ProductVariant)
class ProductVariantAdmin(TabbedTranslationAdmin):
    """Admin for product variants."""

    list_display = ("product", "variant_type", "name", "price_delta", "stock_quantity")
    list_filter = ("variant_type", "ar_translation_source")
    search_fields = ("product__name", "product__sku", "name")
    list_select_related = ("product",)


@admin.register(ProductImage)
class ProductImageAdmin(TabbedTranslationAdmin):
    """Admin for product images."""

    list_display = ("product", "display_order", "is_primary", "updated_at")
    list_filter = ("is_primary", "ar_translation_source")
    search_fields = ("product__name", "alt_text")
    list_select_related = ("product",)


@admin.register(ProductVideo)
class ProductVideoAdmin(admin.ModelAdmin):
    """Admin for product videos."""

    list_display = ("product", "video_url", "updated_at")
    search_fields = ("product__name",)
    list_select_related = ("product",)


@admin.register(ProductRelation)
class ProductRelationAdmin(admin.ModelAdmin):
    """Admin for product relationships."""

    list_display = ("product", "related_product", "relation_type", "updated_at")
    list_filter = ("relation_type",)
    search_fields = ("product__name", "related_product__name")
    list_select_related = ("product", "related_product")


class ReviewPhotoInline(admin.TabularInline):
    model = ReviewPhoto
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin for customer reviews."""

    list_display = (
        "product",
        "customer",
        "rating",
        "moderation_status",
        "is_verified_purchase",
        "updated_at",
    )
    list_filter = ("moderation_status", "rating", "is_verified_purchase")
    search_fields = ("product__name", "customer__user__email", "title")
    list_select_related = ("product", "customer", "customer__user", "moderated_by")
    inlines = [ReviewPhotoInline]


@admin.register(ReviewPhoto)
class ReviewPhotoAdmin(admin.ModelAdmin):
    """Admin for review photos."""

    list_display = ("review", "updated_at")
    list_select_related = ("review", "review__product")
