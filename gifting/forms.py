"""Django forms for the gifting app."""

from __future__ import annotations

from typing import Any

from django import forms

from gifting.constants import PERSONAL_MESSAGE_MAX_LENGTH


class GiftBuilderForm(forms.Form):
    """Parse gift builder POST data into a selections dict for the service layer."""

    personal_message = forms.CharField(
        required=False,
        max_length=PERSONAL_MESSAGE_MAX_LENGTH,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
    )
    greeting_card_id = forms.IntegerField(required=False)
    gift_wrap_id = forms.IntegerField(required=False)
    ribbon_id = forms.IntegerField(required=False)
    photo_upload_id = forms.IntegerField(required=False)
    addon_product_ids = forms.CharField(required=False)
    delivery_date = forms.DateField(required=False)
    delivery_slot_id = forms.IntegerField(required=False)
    delivery_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    recipient_phone = forms.CharField(required=False, max_length=30)
    is_anonymous = forms.BooleanField(required=False)
    reveal_sender_after_delivery = forms.BooleanField(required=False)
    is_gift_receipt = forms.BooleanField(required=False)

    def to_selections(self) -> dict[str, Any]:
        """Return a plain dict suitable for build_gift_customization_snapshot."""
        cleaned = self.cleaned_data
        addon_raw = cleaned.get("addon_product_ids") or ""
        addon_ids = [int(x) for x in addon_raw.split(",") if x.strip().isdigit()]
        return {
            "personal_message": cleaned.get("personal_message", ""),
            "greeting_card_id": cleaned.get("greeting_card_id"),
            "gift_wrap_id": cleaned.get("gift_wrap_id"),
            "ribbon_id": cleaned.get("ribbon_id"),
            "photo_upload_id": cleaned.get("photo_upload_id"),
            "addon_product_ids": addon_ids,
            "delivery_date": cleaned.get("delivery_date"),
            "delivery_slot_id": cleaned.get("delivery_slot_id"),
            "delivery_instructions": cleaned.get("delivery_instructions", ""),
            "recipient_phone": cleaned.get("recipient_phone", ""),
            "is_anonymous": cleaned.get("is_anonymous", False),
            "reveal_sender_after_delivery": cleaned.get("reveal_sender_after_delivery", False),
            "is_gift_receipt": cleaned.get("is_gift_receipt", False),
        }
