"""SEO helpers — meta tags, canonical URLs, hreflang, and JSON-LD."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest
from django.templatetags.static import static
from django.urls import translate_url
from django.utils.translation import get_language


DEFAULT_SOCIAL_IMAGE = "img/logo.png"
OG_LOCALES = {
    "ar": "ar_QA",
    "en": "en_US",
}


def resolve_meta_title(*, obj: Any, fallback: str) -> str:
    """Return meta_title from an SEOModel-capable object or fallback."""
    title = (getattr(obj, "meta_title", None) or "").strip()
    return (title or fallback)[:70]


def resolve_meta_description(*, obj: Any, fallback: str) -> str:
    """Return meta_description from an SEOModel-capable object or fallback."""
    description = (getattr(obj, "meta_description", None) or "").strip()
    return (description or fallback)[:160]


def resolve_og_image_url(*, obj: Any, request: HttpRequest) -> str:
    """Return an absolute object, product-gallery, or brand image URL."""
    og_image = getattr(obj, "og_image", None) if obj is not None else None
    if og_image and getattr(og_image, "url", None):
        return request.build_absolute_uri(og_image.url)

    images = getattr(obj, "image_list", None) if obj is not None else None
    if images is None and obj is not None:
        images = getattr(obj, "images", None)
        if images is not None and hasattr(images, "all"):
            images = images.all()

    if images:
        image_list = list(images)
        primary = next((item for item in image_list if getattr(item, "is_primary", False)), None)
        product_image = getattr(primary or image_list[0], "image", None)
        if product_image and getattr(product_image, "url", None):
            return request.build_absolute_uri(product_image.url)

    return request.build_absolute_uri(static(DEFAULT_SOCIAL_IMAGE))


def build_hreflang_urls(*, request: HttpRequest) -> list[dict[str, str]]:
    """
    Build EN/AR alternate URLs for the current path.

    Uses Django's translate_url to swap locale prefix without duplicating routes.
    """
    alternates: list[dict[str, str]] = []
    current_path = request.get_full_path()
    for lang_code, _label in settings.LANGUAGES:
        localized = translate_url(current_path, lang_code)
        alternates.append(
            {
                "lang_code": lang_code,
                "url": request.build_absolute_uri(localized),
            }
        )
    alternates.append(
        {
            "lang_code": "x-default",
            "url": request.build_absolute_uri(translate_url(current_path, settings.LANGUAGE_CODE)),
        }
    )
    return alternates


def build_plp_canonical_url(
    *,
    request: HttpRequest,
    category_slug: str | None = None,
) -> str:
    """
    Canonical URL for PLP — filtered query params canonicalize to category or shop root.

    Prevents duplicate-content penalties from sort/filter query strings.
    """
    from django.urls import reverse

    if category_slug:
        path = reverse("catalog:plp-category", kwargs={"category_slug": category_slug})
    else:
        path = reverse("catalog:plp")
    return request.build_absolute_uri(path)


def build_product_json_ld(
    *,
    product: Any,
    price: Decimal | str,
    request: HttpRequest,
    average_rating: Optional[float] = None,
    review_count: int = 0,
) -> dict[str, Any]:
    """
    Build schema.org Product JSON-LD for Google Rich Results.

    Includes Offer (price/availability) and AggregateRating when reviews exist.
    """
    from django.urls import reverse

    availability = (
        "https://schema.org/InStock" if product.is_in_stock else "https://schema.org/OutOfStock"
    )
    image_url = ""
    images = getattr(product, "image_list", None) or getattr(product, "images", None)
    if images:
        first = images[0] if isinstance(images, list) else images.first()
        if first and getattr(first, "image", None):
            image_url = request.build_absolute_uri(first.image.url)

    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "sku": product.sku,
        "url": request.build_absolute_uri(reverse("catalog:pdp", kwargs={"slug": product.slug})),
        "offers": {
            "@type": "Offer",
            "priceCurrency": "QAR",
            "price": str(price),
            "availability": availability,
            "url": request.build_absolute_uri(
                reverse("catalog:pdp", kwargs={"slug": product.slug})
            ),
        },
    }
    if image_url:
        data["image"] = image_url

    description = resolve_meta_description(obj=product, fallback=product.name)
    if description:
        data["description"] = description

    if review_count > 0 and average_rating is not None:
        data["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(float(average_rating), 1),
            "reviewCount": review_count,
        }

    return data


def seo_context(
    *,
    request: HttpRequest,
    obj: Any | None = None,
    title: str,
    description: str,
    canonical_url: str | None = None,
    og_type: str = "website",
) -> dict[str, Any]:
    """Assemble standard SEO template context for any page."""
    if obj is not None:
        title = resolve_meta_title(obj=obj, fallback=title)
        description = resolve_meta_description(obj=obj, fallback=description)

    canonical = canonical_url or request.build_absolute_uri(request.path)
    language = get_language() or settings.LANGUAGE_CODE
    return {
        "seo_title": title,
        "seo_description": description,
        "seo_canonical_url": canonical,
        "seo_og_image": resolve_og_image_url(obj=obj, request=request),
        "seo_og_image_alt": title,
        "seo_og_type": og_type,
        "seo_og_locale": OG_LOCALES.get(language, language.replace("-", "_")),
        "seo_hreflang_urls": build_hreflang_urls(request=request),
        "seo_lang": language,
    }
