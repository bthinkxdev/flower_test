"""Storefront URL language-prefix helpers for i18n_patterns."""

from __future__ import annotations

from django.conf import settings

# Paths served by i18n_patterns in floward_clone.urls (prefix_default_language=False).
_I18N_PREFIXES: tuple[str, ...] = (
    "/shop/",
    "/gifting/",
    "/cart/",
    "/checkout/",
    "/orders/",
    "/corporate/",
)


def strip_language_prefix(path: str) -> str:
    """Remove a non-default language prefix (e.g. /ar/...) from a path."""
    normalized = path or "/"
    for code, _label in settings.LANGUAGES:
        if code == settings.LANGUAGE_CODE:
            continue
        prefix = f"/{code}"
        if normalized == prefix or normalized == f"{prefix}/":
            return "/"
        if normalized.startswith(f"{prefix}/"):
            return normalized[len(prefix) :] or "/"
    return normalized


def is_i18n_storefront_path(path: str) -> bool:
    """True when the path belongs to the i18n_patterns storefront routes."""
    normalized = strip_language_prefix(path)
    if normalized == "/":
        return True
    return any(normalized.startswith(prefix) for prefix in _I18N_PREFIXES)


def localize_storefront_path(path: str, language: str) -> str:
    """
    Return ``path`` with the correct language prefix for ``language``.

    English (default): no prefix. Arabic: ``/ar/...``.
    Non-i18n routes (about-us, accounts, preferences, etc.) are unchanged
    aside from stripping a stale ``/ar`` prefix if present.
    """
    normalized = strip_language_prefix(path or "/")
    if not is_i18n_storefront_path(normalized):
        return normalized

    if language == settings.LANGUAGE_CODE:
        return normalized

    if normalized == "/":
        return f"/{language}/"
    return f"/{language}{normalized}"
