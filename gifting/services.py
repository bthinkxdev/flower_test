"""Write operations and business rules for the gifting app."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from gifting.constants import PERSONAL_MESSAGE_MAX_LENGTH
from gifting.exceptions import GiftCustomizationValidationError,GiftSnapshotLockedError
from gifting.models import (
    GiftCustomizationConfig,
    GiftCustomizationSnapshot,
    GiftLineItemRef,
    GiftPhotoUploadOption,
    GiftSnapshotAddon,
    GiftWrapOption,
    GreetingCardDesign,
    RibbonOption,
)
from gifting.selectors import (
    get_available_greeting_cards,
    get_eligible_addons,
    get_gift_customization_config,
)


def create_line_item_reference() -> GiftLineItemRef:
    """
    Create an opaque line-item anchor for a gift builder session.

    Phase 6 cart line items replace this as the snapshot GFK target.
    """
    return GiftLineItemRef.objects.create()


def _err(errors: dict[str, list[str]]) -> None:
    raise GiftCustomizationValidationError(errors)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in {"1", "true", "on", "yes"}


def _parse_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


def _parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@transaction.atomic
def build_gift_customization_snapshot(
    *,
    product_instance: Any,
    selections: dict[str, Any],
    line_item_reference: Any,
) -> GiftCustomizationSnapshot:
    """
    Validate selections against config, resolve prices, and persist an immutable snapshot.

    Raises:
        GiftCustomizationValidationError: field-level ``errors`` dict when invalid.
        GiftSnapshotLockedError: if a locked (already-ordered) snapshot exists
            for this exact line-item reference — this must never be caught and
            "handled" by silently proceeding; it means an upstream bug is
            re-running the builder against an ordered line.
    """
    line_item_ct = ContentType.objects.get_for_model(line_item_reference.__class__)

    existing = GiftCustomizationSnapshot.objects.filter(
        line_item_content_type=line_item_ct,
        line_item_object_id=line_item_reference.pk,
    ).first()
    if existing is not None and existing.is_locked:
        raise GiftSnapshotLockedError(
            f"Snapshot for {line_item_ct}:{line_item_reference.pk} is locked "
            "and cannot be rebuilt."
        )

    config = get_gift_customization_config(product_instance=product_instance)
    if config is None:
        _err({"__all__": ["Gift customization is not enabled for this product."]})

    resolved, snapshot_json = _resolve_selections(
        product_instance=product_instance,
        config=config,
        selections=selections,
    )

    snapshot, _created = GiftCustomizationSnapshot.objects.update_or_create(
        line_item_content_type=line_item_ct,
        line_item_object_id=line_item_reference.pk,
        defaults={
            "personal_message": resolved.get("personal_message", ""),
            "greeting_card_id": resolved.get("greeting_card_id"),
            "gift_wrap_id": resolved.get("gift_wrap_id"),
            "ribbon_id": resolved.get("ribbon_id"),
            "photo_upload_id": resolved.get("photo_upload_id"),
            "delivery_date": resolved.get("delivery_date"),
            "delivery_slot_id": resolved.get("delivery_slot_id"),
            "delivery_instructions": resolved.get("delivery_instructions", ""),
            "recipient_phone": resolved.get("recipient_phone", ""),
            "is_anonymous": resolved.get("is_anonymous", False),
            "reveal_sender_after_delivery": resolved.get(
                "reveal_sender_after_delivery",
                False,
            ),
            "is_gift_receipt": resolved.get("is_gift_receipt", False),
            "snapshot_json": snapshot_json,
        },
    )

    GiftSnapshotAddon.objects.filter(snapshot=snapshot).delete()
    for addon in resolved.get("addons", []):
        GiftSnapshotAddon.objects.create(
            snapshot=snapshot,
            addon_product_id=addon["product_id"],
            price_at_time_of_purchase=addon["price"],
        )

    return snapshot

@transaction.atomic
def lock_gift_customization_snapshot(*, line_item_reference: Any) -> Optional[GiftCustomizationSnapshot]:
    """
    Permanently lock the snapshot tied to a line-item reference.

    Call this exactly ONCE — from orders.services at the moment an order is
    placed (e.g. inside place_order() / transition_order_status() when an
    order first reaches a confirmed state), passing the OrderItem (or
    equivalent) that the CartItem's gift customization was copied onto.
    Never call this from cart or gifting code.
    """
    from gifting.selectors import get_gift_customization_snapshot

    line_item_ct = ContentType.objects.get_for_model(line_item_reference.__class__)
    updated = GiftCustomizationSnapshot.objects.filter(
        line_item_content_type=line_item_ct,
        line_item_object_id=line_item_reference.pk,
        is_locked=False,
    ).update(is_locked=True)
    if not updated:
        return None
    return get_gift_customization_snapshot(line_item_reference=line_item_reference)

def _resolve_selections(
    *,
    product_instance: Any,
    config: GiftCustomizationConfig,
    selections: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate raw selections and build resolved dict + snapshot_json."""
    errors: dict[str, list[str]] = {}
    resolved: dict[str, Any] = {}
    pricing: dict[str, Any] = {"options": [], "addons": [], "total_delta": "0.00"}
    total_delta = Decimal("0.00")

    message = (selections.get("personal_message") or "").strip()
    if message:
        if not config.allows_personal_message:
            errors.setdefault("personal_message", []).append(
                "Personal message is not allowed for this product."
            )
        elif len(message) > PERSONAL_MESSAGE_MAX_LENGTH:
            errors.setdefault("personal_message", []).append(
                f"Message must be at most {PERSONAL_MESSAGE_MAX_LENGTH} characters."
            )
        else:
            resolved["personal_message"] = message

    greeting_card_id = _parse_int(selections.get("greeting_card_id"))
    greeting_card: Optional[GreetingCardDesign] = None
    if greeting_card_id:
        if not config.allows_greeting_card:
            errors.setdefault("greeting_card_id", []).append(
                "Greeting card is not allowed for this product."
            )
        else:
            occasion_id = getattr(product_instance, "primary_occasion_id", None)
            cards = {c.pk: c for c in get_available_greeting_cards(occasion_id=occasion_id)}
            greeting_card = cards.get(greeting_card_id)
            if greeting_card is None:
                errors.setdefault("greeting_card_id", []).append("Invalid greeting card.")
            else:
                resolved["greeting_card_id"] = greeting_card.pk

    gift_wrap_id = _parse_int(selections.get("gift_wrap_id"))
    gift_wrap: Optional[GiftWrapOption] = None
    if gift_wrap_id:
        if not config.allows_gift_wrap:
            errors.setdefault("gift_wrap_id", []).append(
                "Gift wrap is not allowed for this product."
            )
        else:
            gift_wrap = GiftWrapOption.objects.filter(pk=gift_wrap_id, is_active=True).first()
            if gift_wrap is None:
                errors.setdefault("gift_wrap_id", []).append("Invalid gift wrap option.")
            else:
                resolved["gift_wrap_id"] = gift_wrap.pk
                total_delta += gift_wrap.price_delta
                pricing["options"].append(
                    {
                        "type": "gift_wrap",
                        "id": gift_wrap.pk,
                        "label": gift_wrap.get_name_display(),
                        "price": str(gift_wrap.price_delta),
                    }
                )

    ribbon_id = _parse_int(selections.get("ribbon_id"))
    ribbon: Optional[RibbonOption] = None
    if ribbon_id:
        if not config.allows_ribbon:
            errors.setdefault("ribbon_id", []).append("Ribbon is not allowed for this product.")
        else:
            ribbon = RibbonOption.objects.filter(pk=ribbon_id, is_active=True).first()
            if ribbon is None:
                errors.setdefault("ribbon_id", []).append("Invalid ribbon option.")
            else:
                resolved["ribbon_id"] = ribbon.pk
                total_delta += ribbon.price_delta
                pricing["options"].append(
                    {
                        "type": "ribbon",
                        "id": ribbon.pk,
                        "label": ribbon.get_name_display(),
                        "price": str(ribbon.price_delta),
                    }
                )

    photo_upload_id = _parse_int(selections.get("photo_upload_id"))
    photo_upload: Optional[GiftPhotoUploadOption] = None
    if photo_upload_id:
        if not config.allows_photo_upload:
            errors.setdefault("photo_upload_id", []).append(
                "Photo upload is not allowed for this product."
            )
        else:
            photo_upload = GiftPhotoUploadOption.objects.filter(
                pk=photo_upload_id,
                is_active=True,
            ).first()
            if photo_upload is None:
                errors.setdefault("photo_upload_id", []).append("Invalid photo upload option.")
            else:
                resolved["photo_upload_id"] = photo_upload.pk
                total_delta += photo_upload.price_delta
                pricing["options"].append(
                    {
                        "type": "photo_upload",
                        "id": photo_upload.pk,
                        "label": photo_upload.name,
                        "price": str(photo_upload.price_delta),
                    }
                )

    addon_ids = selections.get("addon_product_ids") or []
    if isinstance(addon_ids, str):
        addon_ids = [int(x) for x in addon_ids.split(",") if x.strip()]
    addon_ids = [int(x) for x in addon_ids if x]
    resolved_addons: list[dict[str, Any]] = []
    if addon_ids:
        if not config.allows_addons:
            errors.setdefault("addon_product_ids", []).append(
                "Add-ons are not allowed for this product."
            )
        else:
            eligible = {p.pk: p for p in get_eligible_addons(product_instance=product_instance)}
            for addon_id in addon_ids:
                product = eligible.get(addon_id)
                if product is None:
                    errors.setdefault("addon_product_ids", []).append(
                        f"Add-on {addon_id} is not eligible or is out of stock."
                    )
                else:
                    resolved_addons.append({"product_id": product.pk, "price": product.base_price})
                    total_delta += product.base_price
                    pricing["addons"].append(
                        {
                            "product_id": product.pk,
                            "name": product.name,
                            "price": str(product.base_price),
                        }
                    )
    resolved["addons"] = resolved_addons

    is_anonymous = _parse_bool(selections.get("is_anonymous"))
    if is_anonymous and not config.allows_anonymous:
        errors.setdefault("is_anonymous", []).append("Anonymous delivery is not allowed.")
    else:
        resolved["is_anonymous"] = is_anonymous

    is_gift_receipt = _parse_bool(selections.get("is_gift_receipt"))
    if is_gift_receipt and not config.allows_gift_receipt:
        errors.setdefault("is_gift_receipt", []).append("Gift receipt is not allowed.")
    else:
        resolved["is_gift_receipt"] = is_gift_receipt

    resolved["reveal_sender_after_delivery"] = _parse_bool(
        selections.get("reveal_sender_after_delivery")
    )

    delivery_date = _parse_date(selections.get("delivery_date"))
    if delivery_date:
        resolved["delivery_date"] = delivery_date

    delivery_slot_id = _parse_int(selections.get("delivery_slot_id"))
    if delivery_slot_id:
        from delivery.models import DeliverySlot

        slot = DeliverySlot.objects.filter(pk=delivery_slot_id, is_active=True).first()
        if slot is None:
            errors.setdefault("delivery_slot_id", []).append("Invalid delivery slot.")
        elif slot.is_midnight and not config.allows_midnight_delivery:
            errors.setdefault("delivery_slot_id", []).append(
                "Midnight delivery is not allowed for this product."
            )
        else:
            resolved["delivery_slot_id"] = slot.pk

    resolved["delivery_instructions"] = (selections.get("delivery_instructions") or "").strip()
    resolved["recipient_phone"] = (selections.get("recipient_phone") or "").strip()

    if errors:
        _err(errors)

    pricing["total_delta"] = str(total_delta)
    snapshot_json = {
        "product": {
            "content_type_id": ContentType.objects.get_for_model(product_instance).pk,
            "object_id": product_instance.pk,
            "name": getattr(product_instance, "name", str(product_instance)),
        },
        "selections": {
            "personal_message": resolved.get("personal_message", ""),
            "greeting_card_id": resolved.get("greeting_card_id"),
            "gift_wrap_id": resolved.get("gift_wrap_id"),
            "ribbon_id": resolved.get("ribbon_id"),
            "photo_upload_id": resolved.get("photo_upload_id"),
            "addon_product_ids": [a["product_id"] for a in resolved_addons],
            "delivery_date": (
                resolved["delivery_date"].isoformat() if resolved.get("delivery_date") else None
            ),
            "delivery_slot_id": resolved.get("delivery_slot_id"),
            "delivery_instructions": resolved.get("delivery_instructions", ""),
            "recipient_phone": resolved.get("recipient_phone", ""),
            "is_anonymous": resolved.get("is_anonymous", False),
            "reveal_sender_after_delivery": resolved.get(
                "reveal_sender_after_delivery",
                False,
            ),
            "is_gift_receipt": resolved.get("is_gift_receipt", False),
        },
        "pricing": pricing,
        "resolved_labels": _build_resolved_labels(
            greeting_card=greeting_card,
            gift_wrap=gift_wrap,
            ribbon=ribbon,
            photo_upload=photo_upload,
            addons=resolved_addons,
        ),
    }
    return resolved, snapshot_json


def _build_resolved_labels(
    *,
    greeting_card: Optional[GreetingCardDesign],
    gift_wrap: Optional[GiftWrapOption],
    ribbon: Optional[RibbonOption],
    photo_upload: Optional[GiftPhotoUploadOption],
    addons: list[dict[str, Any]],
) -> dict[str, Any]:
    """Human-readable labels for the Order Preview panel."""
    from catalog.models import Product

    addon_labels = []
    if addons:
        products = Product.objects.filter(pk__in=[a["product_id"] for a in addons])
        name_by_id = {p.pk: p.name for p in products}
        addon_labels = [
            {"name": name_by_id.get(a["product_id"], ""), "price": str(a["price"])} for a in addons
        ]
    return {
        "greeting_card": greeting_card.name if greeting_card else None,
        "gift_wrap": gift_wrap.get_name_display() if gift_wrap else None,
        "ribbon": ribbon.get_name_display() if ribbon else None,
        "photo_upload": photo_upload.name if photo_upload else None,
        "addons": addon_labels,
    }


def ensure_gift_customization_config(
    *,
    product_instance: Any,
    **flags: bool,
) -> GiftCustomizationConfig:
    """Create or update a GiftCustomizationConfig for a product instance."""
    content_type = ContentType.objects.get_for_model(product_instance.__class__)
    defaults = {k: v for k, v in flags.items() if k.startswith("allows_")}
    config, _created = GiftCustomizationConfig.objects.update_or_create(
        content_type=content_type,
        object_id=product_instance.pk,
        defaults=defaults or {"allows_personal_message": True},
    )
    return config
