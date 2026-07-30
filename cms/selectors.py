"""Read-only query functions for the cms app; views must not call the ORM directly."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.utils.translation import get_language

HOMEPAGE_SECTIONS_CACHE_KEY = "cms:homepage_sections:active:v2"
HOMEPAGE_SECTIONS_CACHE_TTL = 300


def _active_language() -> str:
    """Return the active storefront language code (en|ar)."""
    lang = (get_language() or "en").split("-")[0].lower()
    return lang if lang in {"en", "ar"} else "en"


def localize_homepage_section(section: dict[str, Any], *, language: str | None = None) -> dict[str, Any]:
    """
    Resolve bilingual snapshot fields into request-language ``title`` / ``config``.

    English is the fallback when the active-language value is empty.
    """
    lang = language or _active_language()
    title = section.get(f"title_{lang}") or section.get("title_en") or section.get("title") or ""
    config = section.get(f"config_{lang}") or section.get("config_en") or section.get("config") or {}
    localized = dict(section)
    localized["title"] = title
    localized["config"] = config
    return localized


def get_active_homepage_sections() -> list[dict[str, Any]]:
    """
    Return ordered active homepage sections from the Redis-cached snapshot.

    Query guarantee: 0 DB queries on cache hit. On cache miss the Celery task
    `cms.tasks.refresh_homepage_cache` repopulates the snapshot (1 SELECT).

    Cache key: cms:homepage_sections:active:v2
    TTL: 300 seconds (HOMEPAGE_SECTIONS_CACHE_TTL)

    The cached snapshot stores bilingual fields (title_en/title_ar, config_en/config_ar).
    Titles and config are localized to the active request language on read.

    Returns:
        List of section dicts with keys: id, section_type, title, display_order, config.
    """
    cached = cache.get(HOMEPAGE_SECTIONS_CACHE_KEY)
    if cached is None:
        from cms.services import build_homepage_sections_snapshot

        snapshot = build_homepage_sections_snapshot()
        try:
            cache.set(HOMEPAGE_SECTIONS_CACHE_KEY, snapshot, timeout=HOMEPAGE_SECTIONS_CACHE_TTL)
        except Exception:
            pass
        cached = snapshot

    lang = _active_language()
    return [localize_homepage_section(section, language=lang) for section in cached]


def get_hero_slides() -> list[dict[str, Any]]:
    """
    Return active hero slides (uploaded photos/videos) ordered for display.

    Query guarantee: exactly 1 SELECT on cms_heroslide.

    Returns:
        List of slide dicts with keys: type, src, poster, title.
        Slides without any media file are skipped.
    """
    from cms.models import HeroSlide

    slides: list[dict[str, Any]] = []
    for slide in HeroSlide.objects.filter(is_active=True).order_by("display_order", "id"):
        src = slide.media_src
        if not src:
            continue
        slides.append(
            {
                "type": slide.media_type,
                "src": src,
                "poster": slide.poster_src,
                "title": slide.title,
            }
        )
    return slides
