"""Django admin registrations for the delivery app."""

from __future__ import annotations

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from delivery.models import (
    City,
    Country,
    DeliverySlot,
    DeliverySlotBooking,
    DeliveryZone,
)


@admin.register(Country)
class CountryAdmin(TabbedTranslationAdmin):
    list_display = ("name", "code", "is_active", "updated_at")
    list_filter = ("is_active", "ar_translation_source")
    search_fields = ("name", "code")


@admin.register(City)
class CityAdmin(TabbedTranslationAdmin):
    """Admin interface for deliverable cities."""

    list_display = (
        "name",
        "slug",
        "country",
        "delivery_charge_base",
        "same_day_cutoff_hour",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "country", "ar_translation_source")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(TabbedTranslationAdmin):
    list_display = ("name", "city", "radius_km", "is_active")
    list_filter = ("is_active", "city", "ar_translation_source")


@admin.register(DeliverySlot)
class DeliverySlotAdmin(TabbedTranslationAdmin):
    list_display = (
        "name",
        "slot_type",
        "start_time",
        "end_time",
        "max_capacity_per_day",
        "is_active",
    )
    list_filter = ("is_active", "slot_type", "ar_translation_source")


@admin.register(DeliverySlotBooking)
class DeliverySlotBookingAdmin(admin.ModelAdmin):
    list_display = ("slot", "date", "current_bookings", "updated_at")
    list_filter = ("date",)
