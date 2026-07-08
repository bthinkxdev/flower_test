"""Data layer for the corporate app — models only, no business logic."""

from __future__ import annotations

from django.db import models

from core.models import TimeStampedModel


class CorporateQuoteStatus(models.TextChoices):
    """B2B quote workflow states."""

    REQUESTED = "requested", "Requested"
    QUOTED = "quoted", "Quoted"
    APPROVED = "approved", "Approved"
    ORDERED = "ordered", "Ordered"


class CorporateOrder(TimeStampedModel):
    """Bulk B2B order or recurring corporate order template."""

    corporate_account = models.ForeignKey(
        "accounts.CorporateAccount",
        on_delete=models.CASCADE,
        related_name="corporate_orders",
        verbose_name="Corporate account",
    )
    is_recurring = models.BooleanField(default=False, verbose_name="Is recurring")
    recurring_schedule = models.ForeignKey(
        "recurring.RecurringSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corporate_orders",
        verbose_name="Recurring schedule",
    )
    quote_status = models.CharField(
        max_length=20,
        choices=CorporateQuoteStatus.choices,
        default=CorporateQuoteStatus.REQUESTED,
        db_index=True,
        verbose_name="Quote status",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    retail_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corporate_orders",
        verbose_name="Converted retail order",
    )

    class Meta:
        verbose_name = "Corporate order"
        verbose_name_plural = "Corporate orders"
        indexes = [
            models.Index(
                fields=["corporate_account", "quote_status"],
                name="corp_order_account_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Corporate order #{self.pk} ({self.quote_status})"


class CorporateOrderItem(TimeStampedModel):
    """Line on a corporate order with FK integrity to catalog."""

    corporate_order = models.ForeignKey(
        CorporateOrder,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Corporate order",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="corporate_order_items",
        verbose_name="Product",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corporate_order_items",
        verbose_name="Variant",
    )
    quantity = models.PositiveIntegerField(verbose_name="Quantity")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Unit price")

    class Meta:
        verbose_name = "Corporate order item"
        verbose_name_plural = "Corporate order items"

    def __str__(self) -> str:
        return f"{self.product_id} x{self.quantity}"


class CorporateInvoice(TimeStampedModel):
    """Generated invoice PDF for a corporate order."""

    corporate_order = models.ForeignKey(
        CorporateOrder,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name="Corporate order",
    )
    pdf_url = models.URLField(verbose_name="PDF URL")
    generated_at = models.DateTimeField(verbose_name="Generated at")

    class Meta:
        verbose_name = "Corporate invoice"
        verbose_name_plural = "Corporate invoices"
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"Invoice for corporate order #{self.corporate_order_id}"
