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

class GiftSnapshotLockedError(Exception):
    """
    Raised when code attempts to rebuild a snapshot that is already locked
    (i.e. already part of a placed order). This must never happen through
    normal cart/checkout flow — surfacing it means something upstream tried
    to re-run the gift builder against an already-ordered line.
    """