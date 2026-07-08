"""Django admin registrations for the corporate app."""

from __future__ import annotations

from django.contrib import admin

from corporate.models import CorporateInvoice, CorporateOrder, CorporateOrderItem


class CorporateOrderItemInline(admin.TabularInline):
    model = CorporateOrderItem
    extra = 0


@admin.register(CorporateOrder)
class CorporateOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "corporate_account", "quote_status", "is_recurring", "created_at")
    list_filter = ("quote_status", "is_recurring")
    inlines = [CorporateOrderItemInline]


@admin.register(CorporateInvoice)
class CorporateInvoiceAdmin(admin.ModelAdmin):
    list_display = ("corporate_order", "pdf_url", "generated_at")
