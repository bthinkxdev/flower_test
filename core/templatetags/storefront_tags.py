"""Storefront template helpers for currency display."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


@register.filter
def display_label(value) -> str:
    """Humanize CMS/option labels (e.g. Luxury_box → Luxury box)."""
    if value is None:
        return ""
    text = str(value).replace("_", " ").strip()
    return " ".join(text.split())


@register.filter
def dict_get(mapping, key):
    """Safe dict lookup for template badge / option labels."""
    if not isinstance(mapping, dict):
        return key
    return mapping.get(key, key)

def _format_money_amount(amount: Decimal) -> str:
    """Render money without trailing .00 when the amount is a whole number."""
    quantized = amount.quantize(Decimal("0.01"), ROUND_HALF_UP)
    if quantized == quantized.to_integral_value():
        return str(int(quantized))
    return f"{quantized:.2f}"


@register.filter
def in_display_currency(amount, currency) -> str:
    """Convert a base-currency amount into the active display currency."""
    if amount is None or amount == "":
        return ""
    if currency is None:
        return _format_money_amount(Decimal(str(amount)))
    base = Decimal(str(amount))
    rate = Decimal(str(currency.exchange_rate_to_base))
    if rate <= 0:
        return _format_money_amount(base)
    converted = base / rate
    return _format_money_amount(converted)


@register.simple_tag
def money_label(amount, currency) -> str:
    """Format amount with currency code for templates."""
    code = getattr(currency, "code", "QAR") if currency else "QAR"
    value = in_display_currency(amount, currency)
    return f"{value} {code}"
