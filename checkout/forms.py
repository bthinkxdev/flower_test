"""Django forms for the checkout app."""

from __future__ import annotations

from django import forms


class CheckoutAddressForm(forms.Form):
    """Select delivery address for checkout."""

    address_id = forms.IntegerField()


class CheckoutDeliveryForm(forms.Form):
    """Delivery date and slot selection."""

    delivery_date = forms.DateField(required=True)
    delivery_slot_id = forms.IntegerField(required=True)


class CheckoutPaymentForm(forms.Form):
    """Payment gateway selection."""

    gateway_key = forms.CharField(max_length=40)
    idempotency_key = forms.CharField(max_length=64)
    voucher_code = forms.CharField(required=False, max_length=40)

class CheckoutGuestDetailsForm(forms.Form):
    """Delivery + contact details for guest checkout (no saved Address row exists)."""

    full_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    line1 = forms.CharField(max_length=255)
    line2 = forms.CharField(max_length=255, required=False)
    city = forms.ModelChoiceField(queryset=None)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from delivery.models import City

        self.fields["city"].queryset = City.objects.filter(is_active=True)
