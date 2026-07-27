"""
Central registry of models and fields eligible for automatic EN→AR translation.

No translation logic lives here — only declarative maps consumed by the service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db import models

# Populated once via populate_registry() after Django apps are ready.
TRANSLATED_FIELDS: dict[type[models.Model], list[str]] = {}

# JSONField names whose string values are translated in-structure.
TRANSLATED_JSON_FIELDS: dict[type[models.Model], list[str]] = {}

# User-visible JSON keys eligible for translation. All other keys are preserved as-is.
JSON_TRANSLATABLE_KEYS: frozenset[str] = frozenset(
    {
        "headline",
        "subtitle",
        "title",
        "cta_text",
        "placeholder",
        "instagram_handle",
    }
)

_populated = False


def populate_registry() -> None:
    """
    Load model classes into TRANSLATED_FIELDS / TRANSLATED_JSON_FIELDS.

    Idempotent. Must run after Django app registry is ready.
    """
    global _populated
    if _populated:
        return

    from catalog.models import (
        Brand,
        Category,
        Occasion,
        Product,
        ProductImage,
        ProductVariant,
        Recipient,
    )
    from cms.models import (
        BlogPost,
        FAQItem,
        HeroSlide,
        HomepageSection,
        Page,
        PolicyDocument,
    )
    from core.models import SiteSettings
    from delivery.models import City, Country, DeliverySlot, DeliveryZone
    from gifting.models import (
        GiftPhotoUploadOption,
        GiftWrapOption,
        GreetingCardDesign,
        RibbonOption,
    )
    from marketing.models import FlashSale

    TRANSLATED_FIELDS.update(
        {
            # Catalog
            Category: ["name", "meta_title", "meta_description"],
            Occasion: ["name"],
            Brand: ["name"],
            Recipient: ["name"],
            Product: ["name", "color", "meta_title", "meta_description"],
            ProductVariant: ["name"],
            ProductImage: ["alt_text"],
            # CMS
            HomepageSection: ["title"],
            HeroSlide: ["title"],
            BlogPost: ["title", "body", "excerpt", "meta_title", "meta_description"],
            Page: ["title", "body", "meta_title", "meta_description"],
            FAQItem: ["question", "answer"],
            PolicyDocument: ["title", "body", "meta_title", "meta_description"],
            # Gifting
            GreetingCardDesign: ["name"],
            GiftWrapOption: ["name"],
            RibbonOption: ["name"],
            GiftPhotoUploadOption: ["name"],
            # Delivery
            Country: ["name"],
            City: ["name"],
            DeliveryZone: ["name"],
            DeliverySlot: ["name"],
            # Marketing
            FlashSale: ["name"],
            # Core
            SiteSettings: ["site_name"],
        }
    )

    TRANSLATED_JSON_FIELDS.update(
        {
            HomepageSection: ["config"],
        }
    )

    _populated = True


def is_registered(model: type[models.Model]) -> bool:
    """Return True when the model participates in automatic translation."""
    populate_registry()
    return model in TRANSLATED_FIELDS or model in TRANSLATED_JSON_FIELDS


def get_translated_fields(model: type[models.Model]) -> list[str]:
    """Return registered Char/Text field names for a model (empty if none)."""
    populate_registry()
    return list(TRANSLATED_FIELDS.get(model, []))


def get_translated_json_fields(model: type[models.Model]) -> list[str]:
    """Return registered JSONField names for a model (empty if none)."""
    populate_registry()
    return list(TRANSLATED_JSON_FIELDS.get(model, []))
