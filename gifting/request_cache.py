"""Per-request cache helpers for gifting selectors."""

from __future__ import annotations

from typing import Any, Optional

from django.http import HttpRequest

_REQUEST_CACHE_ATTR = "_gifting_request_cache"


def get_request_cache(request: HttpRequest) -> dict[str, Any]:
    """Return the mutable per-request cache dict, creating it if needed."""
    cache = getattr(request, _REQUEST_CACHE_ATTR, None)
    if cache is None:
        cache = {}
        setattr(request, _REQUEST_CACHE_ATTR, cache)
    return cache


def get_cached_value(*, request: HttpRequest, key: str) -> Optional[Any]:
    """Read a value from the per-request cache."""
    return get_request_cache(request).get(key)


def set_cached_value(*, request: HttpRequest, key: str, value: Any) -> None:
    """Store a value in the per-request cache."""
    get_request_cache(request)[key] = value
