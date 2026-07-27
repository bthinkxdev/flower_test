"""Django admin registrations for the core app."""

from __future__ import annotations

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from core.forms import CurrencyAdminForm
from core.models import Currency, SiteSettings


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """Admin interface for storefront currencies."""

    form = CurrencyAdminForm
    list_display = ("code", "symbol", "exchange_rate_to_base", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("code", "symbol")
    ordering = ("code",)


@admin.register(SiteSettings)
class SiteSettingsAdmin(TabbedTranslationAdmin):
    """Singleton site settings — only one row (pk=1)."""

    list_filter = ("ar_translation_source",)

    def has_add_permission(self, request) -> bool:
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
