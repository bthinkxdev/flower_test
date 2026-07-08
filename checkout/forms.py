"""Django forms for the checkout app."""

from __future__ import annotations

from django import forms


class CheckoutAddressForm(forms.Form):
    """Select delivery address for checkout."""

    address_id = forms.IntegerField()


class CheckoutDeliveryForm(forms.Form):
    """Delivery date and slot selection."""

    delivery_date = forms.DateField(required=False)
    delivery_slot_id = forms.IntegerField(required=False)


class CheckoutPaymentForm(forms.Form):
    """Payment gateway selection."""

    gateway_key = forms.CharField(max_length=40)
    idempotency_key = forms.CharField(max_length=64)
    voucher_code = forms.CharField(required=False, max_length=40)
