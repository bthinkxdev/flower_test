"""Django forms for the core app."""

from __future__ import annotations

from django import forms

from core.models import Currency, ContactMessage


class ContactForm(forms.ModelForm):
    """Public-facing Contact Us form."""

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "john@example.com"}),
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Subject"}),
            "message": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "placeholder": "Tell us how we can help you…"}
            ),
        }


class CurrencyAdminForm(forms.ModelForm):
    """Admin form for Currency with uppercase code normalization."""

    class Meta:
        model = Currency
        fields = ("code", "symbol", "exchange_rate_to_base", "is_default")

    def clean_code(self) -> str:
        """Normalize currency code to uppercase."""
        return self.cleaned_data["code"].upper()
