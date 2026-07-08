"""Domain exceptions for the corporate app."""

from __future__ import annotations


class CorporateOrderError(Exception):
    """Raised when a corporate order operation is invalid."""
