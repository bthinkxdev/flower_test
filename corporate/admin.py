"""Django admin registrations for the corporate app."""

from __future__ import annotations

from django.contrib import admin, messages

from corporate.exceptions import CorporateOrderError
from corporate.models import CorporateInvoice, CorporateOrder, CorporateOrderItem, CorporateQuoteStatus
from corporate.services import approve_and_convert_to_order, generate_corporate_invoice


class CorporateOrderItemInline(admin.TabularInline):
    model = CorporateOrderItem
    extra = 0


@admin.register(CorporateOrder)
class CorporateOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "corporate_account", "quote_status", "is_recurring", "created_at")
    list_filter = ("quote_status", "is_recurring")
    inlines = [CorporateOrderItemInline]
    actions = ["approve_and_convert", "generate_invoice"]

    @admin.action(description="Approve & convert selected quotes to orders")
    def approve_and_convert(self, request, queryset):
        converted = 0
        for corporate_order in queryset:
            try:
                approve_and_convert_to_order(corporate_order=corporate_order)
                converted += 1
            except CorporateOrderError as exc:
                self.message_user(request, f"Order #{corporate_order.pk}: {exc}", level=messages.ERROR)
        if converted:
            self.message_user(request, f"Converted {converted} order(s).", level=messages.SUCCESS)

    @admin.action(description="Generate invoice for selected orders")
    def generate_invoice(self, request, queryset):
        generated = 0
        for corporate_order in queryset:
            if corporate_order.quote_status != CorporateQuoteStatus.ORDERED:
                self.message_user(
                    request,
                    f"Order #{corporate_order.pk}: must be converted to an order before invoicing.",
                    level=messages.ERROR,
                )
                continue
            generate_corporate_invoice(
                corporate_order=corporate_order,
                pdf_url=f"/media/invoices/corporate-order-{corporate_order.pk}.pdf",
            )
            generated += 1
        if generated:
            self.message_user(request, f"Generated {generated} invoice(s).", level=messages.SUCCESS)


@admin.register(CorporateInvoice)
class CorporateInvoiceAdmin(admin.ModelAdmin):
    list_display = ("corporate_order", "pdf_url", "generated_at")
