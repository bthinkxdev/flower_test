"""Write operations and business rules for the cms app."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

from cms.models import HomepageSection
from cms.selectors import HOMEPAGE_SECTIONS_CACHE_KEY, HOMEPAGE_SECTIONS_CACHE_TTL


def build_homepage_sections_snapshot() -> list[dict[str, Any]]:
    """
    Build a serializable bilingual snapshot of active homepage sections.

    Query guarantee: exactly 1 SELECT on cms_homepagesection ordered by display_order.

    Stores language-specific fields so readers can localize without a DB hit:
    title_en/title_ar and config_en/config_ar.

    Returns:
        List of section dicts safe for Redis JSON serialization.
    """
    return [
        {
            "id": section.pk,
            "section_type": section.section_type,
            "title_en": section.title_en or "",
            "title_ar": section.title_ar or "",
            "display_order": section.display_order,
            "config_en": section.config_en or {},
            "config_ar": section.config_ar or {},
        }
        for section in HomepageSection.objects.filter(is_active=True).order_by(
            "display_order", "id"
        )
    ]


def refresh_homepage_cache() -> int:
    """
    Rebuild and store the homepage sections Redis snapshot.

    Returns:
        Number of sections written to cache.
    """
    snapshot = build_homepage_sections_snapshot()
    try:
        cache.set(HOMEPAGE_SECTIONS_CACHE_KEY, snapshot, timeout=HOMEPAGE_SECTIONS_CACHE_TTL)
    except Exception:
        pass
    return len(snapshot)


def get_section_render_context(
    *,
    section: dict[str, Any],
    product_rails: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build template context for a homepage section by dispatching to catalog selectors.

    Params:
        section: Serialized section dict from get_active_homepage_sections().
    Returns:
        Context dict passed to cms/sections/<section_type>.html partials.
    """
    from cms.section_context import build_section_context

    return build_section_context(section=section, product_rails=product_rails)
