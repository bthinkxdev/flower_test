"""Django admin registrations for the gifting app."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from gifting.models import (
    GiftAddonEligibility,
    GiftCustomizationConfig,
    GiftCustomizationSnapshot,
    GiftLineItemRef,
    GiftPhotoUploadOption,
    GiftSnapshotAddon,
    GiftWrapOption,
    GreetingCardDesign,
    RibbonOption,
)


class GiftAddonEligibilityInline(GenericTabularInline):
    model = GiftAddonEligibility
    extra = 0


@admin.register(GiftCustomizationConfig)
class GiftCustomizationConfigAdmin(admin.ModelAdmin):
    list_display = (
        "content_type",
        "object_id",
        "allows_personal_message",
        "allows_ribbon",
        "allows_addons",
    )
    list_filter = ("allows_ribbon", "allows_gift_wrap", "allows_photo_upload")


@admin.register(GreetingCardDesign)
class GreetingCardDesignAdmin(admin.ModelAdmin):
    list_display = ("name", "occasion", "is_active")
    list_filter = ("is_active", "occasion")


@admin.register(GiftWrapOption)
class GiftWrapOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "price_delta", "is_active")


@admin.register(RibbonOption)
class RibbonOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "price_delta", "is_active")


@admin.register(GiftPhotoUploadOption)
class GiftPhotoUploadOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "price_delta", "is_active")


@admin.register(GiftAddonEligibility)
class GiftAddonEligibilityAdmin(admin.ModelAdmin):
    list_display = ("content_type", "object_id", "addon_product")


class GiftSnapshotAddonInline(admin.TabularInline):
    model = GiftSnapshotAddon
    extra = 0
    readonly_fields = ("addon_product", "price_at_time_of_purchase")


@admin.register(GiftCustomizationSnapshot)
class GiftCustomizationSnapshotAdmin(admin.ModelAdmin):
    list_display = ("pk", "delivery_date", "is_anonymous", "is_gift_receipt", "created_at")
    inlines = [GiftSnapshotAddonInline]
    readonly_fields = ("snapshot_json",)


@admin.register(GiftLineItemRef)
class GiftLineItemRefAdmin(admin.ModelAdmin):
    list_display = ("pk", "created_at")
