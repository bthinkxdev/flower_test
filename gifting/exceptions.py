"""Domain exceptions for the gifting app."""

from __future__ import annotations


class GiftCustomizationValidationError(Exception):
    """
    Raised when gift customization selections fail validation.

    ``errors`` is a field-level mapping suitable for HTMX form highlighting,
    e.g. ``{"ribbon_id": ["Ribbon is not allowed for this product."]}``.
    """

    def __init__(self, errors: dict[str, list[str]]) -> None:
        self.errors = errors
        super().__init__(errors)

    def as_dict(self) -> dict[str, list[str]]:
        """Return the field-level error mapping."""
        return self.errors
