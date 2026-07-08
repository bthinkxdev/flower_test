"""Storefront template helpers for currency display."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


@register.filter
def in_display_currency(amount, currency) -> str:
    """Convert a base-currency amount into the active display currency."""
    if amount is None or amount == "":
        return ""
    if currency is None:
        return str(amount)
    base = Decimal(str(amount))
    rate = Decimal(str(currency.exchange_rate_to_base))
    if rate <= 0:
        return f"{base.quantize(Decimal('0.01'), ROUND_HALF_UP)}"
    converted = (base / rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return f"{converted}"


@register.simple_tag
def money_label(amount, currency) -> str:
    """Format amount with currency code for templates."""
    code = getattr(currency, "code", "QAR") if currency else "QAR"
    value = in_display_currency(amount, currency)
    return f"{value} {code}"
