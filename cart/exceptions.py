"""Domain exceptions for the cart app."""

from __future__ import annotations


class CartError(Exception):
    """Base exception for cart services."""


class CartNotFoundError(CartError):
    """Raised when no cart can be resolved for the request context."""
