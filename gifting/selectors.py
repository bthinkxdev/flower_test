"""Read-only query functions for the gifting app; views must not call the ORM directly."""

from __future__ import annotations

from typing import Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch
from django.http import HttpRequest

from gifting.models import (
    GiftAddonEligibility,
    GiftCustomizationConfig,
    GiftCustomizationSnapshot,
    GiftLineItemRef,
    GiftSnapshotAddon,
    GreetingCardDesign,
)
from gifting.request_cache import set_cached_value


def _content_type_for_instance(*, instance: Any) -> ContentType:
    return ContentType.objects.get_for_model(instance.__class__)


def _config_cache_key(*, instance: Any) -> str:
    ct = ContentType.objects.get_for_model(instance.__class__)
    return f"gift_config:{ct.pk}:{instance.pk}"


def get_gift_customization_config(
    *,
    product_instance: Any,
    request: Optional[HttpRequest] = None,
) -> Optional[GiftCustomizationConfig]:
    """
    Return the gift customization config for any product-like instance.

    Query guarantee: exactly 1 SELECT on gifting_giftcustomizationconfig filtered
    by content_type + object_id.

    Cached per-request (not per-process) when ``request`` is supplied — the gift
    builder calls this multiple times while rendering sections.
    """
    from gifting.request_cache import get_request_cache

    cache_key = _config_cache_key(instance=product_instance)
    if request is not None:
        cache = get_request_cache(request)
        if cache_key in cache:
            return cache[cache_key]

    content_type = _content_type_for_instance(instance=product_instance)
    config = GiftCustomizationConfig.objects.filter(
        content_type=content_type,
        object_id=product_instance.pk,
    ).first()

    if request is not None:
        set_cached_value(request=request, key=cache_key, value=config)
    return config


def get_available_greeting_cards(*, occasion_id: Optional[int] = None) -> list[GreetingCardDesign]:
    """
    Return active greeting card designs, optionally filtered by occasion.

    Query guarantee: 1 SELECT with select_related(occasion).
    """
    qs = GreetingCardDesign.objects.filter(is_active=True).select_related("occasion")
    if occasion_id is not None:
        qs = qs.filter(occasion_id=occasion_id)
    return list(qs.order_by("name"))


def _curated_or_fallback(*, product_instance, eligibility_model, option_field, fallback_qs):
    content_type = _content_type_for_instance(instance=product_instance)
    curated = (
        eligibility_model.objects.filter(
            content_type=content_type,
            object_id=product_instance.pk,
            **{f"{option_field}__is_active": True},
        )
        .select_related(option_field)
        .order_by(f"{option_field}__name")
    )
    curated_list = [getattr(row, option_field) for row in curated]
    return curated_list if curated_list else list(fallback_qs)


def get_eligible_greeting_cards(*, product_instance: Any) -> list[GreetingCardDesign]:
    """Curated cards win; else occasion-match; query guarantee: 1–2 SELECTs."""
    from gifting.models import GiftCardEligibility
    curated = _curated_or_fallback(
        product_instance=product_instance,
        eligibility_model=GiftCardEligibility,
        option_field="greeting_card",
        fallback_qs=[],
    )
    if curated:
        return curated
    occasion_id = getattr(product_instance, "primary_occasion_id", None)
    return get_available_greeting_cards(occasion_id=occasion_id)


def get_eligible_gift_wrap_options(*, product_instance: Any) -> list:
    from gifting.models import GiftWrapEligibility, GiftWrapOption
    return _curated_or_fallback(
        product_instance=product_instance,
        eligibility_model=GiftWrapEligibility,
        option_field="gift_wrap",
        fallback_qs=GiftWrapOption.objects.filter(is_active=True).order_by("name"),
    )


def get_eligible_ribbon_options(*, product_instance: Any) -> list:
    from gifting.models import RibbonEligibility, RibbonOption
    return _curated_or_fallback(
        product_instance=product_instance,
        eligibility_model=RibbonEligibility,
        option_field="ribbon",
        fallback_qs=RibbonOption.objects.filter(is_active=True).order_by("name"),
    )


def get_eligible_photo_upload_options(*, product_instance: Any) -> list:
    from gifting.models import GiftPhotoUploadEligibility, GiftPhotoUploadOption
    return _curated_or_fallback(
        product_instance=product_instance,
        eligibility_model=GiftPhotoUploadEligibility,
        option_field="photo_upload",
        fallback_qs=GiftPhotoUploadOption.objects.filter(is_active=True).order_by("name"),
    )


def get_eligible_addons(*, product_instance: Any) -> list:
    """
    Return add-on catalog products eligible for a primary product instance.

    Respects catalog ``is_active`` and in-stock flags — out-of-stock add-ons are
    excluded even when an eligibility row exists.

    Query guarantee: 1 SELECT on eligibility + select_related addon category/brand.
    """
    content_type = _content_type_for_instance(instance=product_instance)
    eligibilities = (
        GiftAddonEligibility.objects.filter(
            content_type=content_type,
            object_id=product_instance.pk,
            addon_product__is_active=True,
            addon_product__stock_quantity__gt=0,
        )
        .select_related("addon_product", "addon_product__category", "addon_product__brand")
        .order_by("addon_product__name")
    )
    return [row.addon_product for row in eligibilities]


def get_gift_customization_snapshot(
    *,
    line_item_reference: Any,
) -> Optional[GiftCustomizationSnapshot]:
    """
    Hydrate the gift customization snapshot for a line-item reference.

    **Order Preview data source** — cart summary, checkout review, and order
    confirmation MUST call this selector exclusively. All three UI surfaces stay
    in sync by construction because they share one read path.

    Query guarantee: 1 SELECT on snapshot + prefetch_related for greeting_card,
    gift_wrap, ribbon, photo_upload, delivery_slot, and snapshot_addons with
    addon_product category/brand (constant query count regardless of add-on count).
    """
    content_type = _content_type_for_instance(instance=line_item_reference)
    addon_prefetch = Prefetch(
        "snapshot_addons",
        queryset=GiftSnapshotAddon.objects.select_related(
            "addon_product",
            "addon_product__category",
            "addon_product__brand",
        ).order_by("id"),
    )
    return (
        GiftCustomizationSnapshot.objects.filter(
            line_item_content_type=content_type,
            line_item_object_id=line_item_reference.pk,
        )
        .select_related(
            "greeting_card",
            "greeting_card__occasion",
            "gift_wrap",
            "ribbon",
            "photo_upload",
            "delivery_slot",
        )
        .prefetch_related(addon_prefetch)
        .first()
    )


def get_line_item_ref_by_id(*, line_item_id: int) -> Optional[GiftLineItemRef]:
    """
    Return a gift line-item reference by primary key.

    Query guarantee: exactly 1 SELECT on gifting_giftlineitemref.
    """
    return GiftLineItemRef.objects.filter(pk=line_item_id).first()
