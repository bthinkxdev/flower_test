"""Django forms for the checkout app."""

from __future__ import annotations

from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class CheckoutAddressForm(forms.Form):
    """Select delivery address for checkout."""

    address_id = forms.IntegerField(
        error_messages={
            "required": _("Please select a delivery address."),
            "invalid": _("Please select a valid delivery address."),
        },
    )


class CheckoutDeliveryForm(forms.Form):
    """Delivery date and slot selection."""

    delivery_date = forms.DateField(
        required=True,
        error_messages={
            "required": _("Please select a delivery date."),
            "invalid": _("Please enter a valid delivery date."),
        },
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
            },
        ),
    )
    delivery_slot_id = forms.IntegerField(
        required=True,
        error_messages={
            "required": _("Please select a delivery time slot."),
            "invalid": _("Please select a valid delivery time slot."),
        },
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["delivery_date"].widget.attrs.update(
            {
                "hx-post": reverse("checkout:update-session"),
                "hx-trigger": "change",
                "hx-include": "#checkout-form",
                "hx-target": "this",
                "hx-swap": "none",
            }
        )


class CheckoutPaymentForm(forms.Form):
    """Payment gateway selection."""

    gateway_key = forms.CharField(
        max_length=40,
        error_messages={"required": _("Please select a payment method.")},
    )
    idempotency_key = forms.CharField(max_length=64)
    voucher_code = forms.CharField(
        required=False,
        max_length=40,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": _("Optional"),
            },
        ),
    )


class CheckoutGuestDetailsForm(forms.Form):
    """Delivery + contact details for guest checkout (no saved Address row exists)."""

    full_name = forms.CharField(
        max_length=120,
        error_messages={"required": _("Please enter your full name.")},
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        error_messages={
            "required": _("Please enter your email address."),
            "invalid": _("Please enter a valid email address."),
        },
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        max_length=20,
        error_messages={"required": _("Please enter your phone number.")},
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    line1 = forms.CharField(
        max_length=255,
        error_messages={"required": _("Please enter your address line 1.")},
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    line2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    city = forms.ModelChoiceField(
        queryset=None,
        error_messages={
            "required": _("Please select a city."),
            "invalid_choice": _("Please select a valid city."),
        },
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from delivery.models import City

        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["city"].widget.attrs.update(
            {
                "hx-post": reverse("checkout:preview-delivery"),
                "hx-trigger": "change",
                "hx-target": "this",
                "hx-swap": "none",
            }
        )
