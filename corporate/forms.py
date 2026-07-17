"""Django forms for the corporate app."""

from __future__ import annotations

import json

from django import forms

from recurring.models import RecurrenceFrequency


class CorporateQuoteRequestForm(forms.Form):
    """
    Bulk quote request. Line items arrive as JSON built by the product-picker
    widget on the page — unit prices are NEVER trusted from the client; the
    view resolves them server-side via catalog.selectors.get_variant_price.
    """

    items_json = forms.CharField(widget=forms.HiddenInput())
    notes = forms.CharField(widget=forms.Textarea, required=False)
    is_recurring = forms.BooleanField(required=False)
    frequency = forms.ChoiceField(choices=RecurrenceFrequency.choices, required=False)
    next_run_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=False)

    def clean_items_json(self):
        raw = self.cleaned_data["items_json"]
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raise forms.ValidationError("Invalid items payload.")
        if not isinstance(items, list) or not items:
            raise forms.ValidationError("Add at least one product line.")

        cleaned = []
        for row in items:
            try:
                product_id = int(row["product_id"])
                quantity = int(row["quantity"])
            except (KeyError, TypeError, ValueError):
                raise forms.ValidationError("Each line needs a valid product and quantity.")
            if quantity < 1:
                raise forms.ValidationError("Quantity must be at least 1.")
            variant_id = row.get("variant_id")
            cleaned.append(
                {
                    "product_id": product_id,
                    "variant_id": int(variant_id) if variant_id else None,
                    "quantity": quantity,
                }
            )
        return cleaned

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_recurring") and (not cleaned.get("frequency") or not cleaned.get("next_run_date")):
            raise forms.ValidationError("Recurring orders need a frequency and a first run date.")
        return cleaned