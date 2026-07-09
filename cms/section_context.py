"""Homepage section context builders — delegates to catalog selectors, never ORM."""

from __future__ import annotations

from typing import Any

from catalog.selectors import (
    get_featured_brands,
    get_homepage_product_rails,
    get_occasions_for_display,
    get_products_for_section_config,
    get_recent_approved_reviews,
    get_recipients_for_display,
    get_root_categories,
)
from cms.selectors import get_hero_slides


def build_section_context(
    *,
    section: dict[str, Any],
    product_rails: dict[str, list] | None = None,
) -> dict[str, Any]:
    """
    Dispatch section_type to the appropriate data source.

    Every section pulls live catalog/cms config data — nothing is hardcoded in templates.
    """
    section_type = section["section_type"]
    config = section.get("config") or {}
    base = {
        "section": section,
        "title": section.get("title", ""),
        "config": config,
    }

    builders = {
        "hero_slider": _hero_slider,
        "shop_by_occasion": _shop_by_occasion,
        "shop_by_recipient": _shop_by_recipient,
        "shop_by_category": _shop_by_category,
        "premium_collection": _product_collection,
        "seasonal_collection": _product_collection,
        "luxury_collection": _product_collection,
        "same_day_delivery": _same_day,
        "trending": _trending,
        "best_sellers": _best_sellers,
        "featured_brands": _featured_brands,
        "corporate_gifts_banner": _banner,
        "subscription_banner": _banner,
        "marketing_features": _marketing_features,
        "reviews": _reviews,
        "instagram_gallery": _instagram,
        "newsletter": _newsletter,
    }
    builder = builders.get(section_type, _empty)
    if section_type in ("same_day_delivery", "trending", "best_sellers"):
        base.update(builder(config, product_rails=product_rails))
    else:
        base.update(builder(config))
    return base


def _rails(product_rails: dict[str, list] | None, key: str) -> list:
    if product_rails is not None:
        return product_rails.get(key, [])
    return get_homepage_product_rails().get(key, [])


def _hero_slider(config: dict[str, Any]) -> dict[str, Any]:
    """Prefer uploaded photo/video slides; fall back to legacy URL-based config."""
    slides = get_hero_slides()
    if slides:
        return {"slides": slides}
    fallback = [
        {
            "type": "image",
            "src": slide.get("image", ""),
            "poster": "",
            "title": slide.get("title") or slide.get("headline") or "",
        }
        for slide in config.get("slides", [])
        if slide.get("image")
    ]
    return {"slides": fallback}


def _shop_by_occasion(config: dict[str, Any]) -> dict[str, Any]:
    return {"occasions": get_occasions_for_display()}


def _shop_by_recipient(config: dict[str, Any]) -> dict[str, Any]:
    return {"recipients": get_recipients_for_display()}


def _shop_by_category(config: dict[str, Any]) -> dict[str, Any]:
    return {"categories": get_root_categories(category_ids=None)}


def _product_collection(config: dict[str, Any]) -> dict[str, Any]:
    return {"products": get_products_for_section_config(config=config)}


def _same_day(
    config: dict[str, Any], product_rails: dict[str, list] | None = None
) -> dict[str, Any]:
    return {"products": _rails(product_rails, "same_day")}


def _trending(
    config: dict[str, Any], product_rails: dict[str, list] | None = None
) -> dict[str, Any]:
    return {"products": _rails(product_rails, "trending")}


def _best_sellers(
    config: dict[str, Any], product_rails: dict[str, list] | None = None
) -> dict[str, Any]:
    return {"products": _rails(product_rails, "bestsellers")}


def _featured_brands(config: dict[str, Any]) -> dict[str, Any]:
    brand_ids = config.get("brand_ids")
    return {"brands": get_featured_brands(brand_ids=brand_ids)}


def _banner(config: dict[str, Any]) -> dict[str, Any]:
    return {"banner": config}


def _marketing_features(config: dict[str, Any]) -> dict[str, Any]:
    return {"cards": config.get("cards", [])}


def _reviews(config: dict[str, Any]) -> dict[str, Any]:
    limit = config.get("limit", 6)
    return {"reviews": get_recent_approved_reviews(limit=limit)}


def _instagram(config: dict[str, Any]) -> dict[str, Any]:
    return {"images": config.get("images", [])}


def _newsletter(config: dict[str, Any]) -> dict[str, Any]:
    return {"placeholder": config.get("placeholder", "")}


def _empty(config: dict[str, Any]) -> dict[str, Any]:
    return {}
