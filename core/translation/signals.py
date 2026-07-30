"""
Shared post_save hook for automatic content translation.

One signal for the entire application — no per-model handlers.
"""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.translation.registry import (
    get_translated_fields,
    get_translated_json_fields,
    is_registered,
    populate_registry,
)
from core.translation.service import translate_and_save

populate_registry()


def _touches_source_fields(model: type, update_fields: frozenset[str] | set[str]) -> bool:
    """True when the save touched English / source fields that drive translation."""
    names = get_translated_fields(model) + get_translated_json_fields(model)
    relevant: set[str] = set()
    for name in names:
        relevant.add(name)
        relevant.add(f"{name}_en")
    return bool(relevant & set(update_fields))


@receiver(post_save)
def on_registered_model_saved(
    sender: type,
    instance,
    *,
    created: bool,
    raw: bool = False,
    update_fields=None,
    **kwargs,
) -> None:
    """
    After any registered model is saved, keep Arabic fields in sync with English.

    Flow: model.save() → this signal → translate_and_save() → deep-translator → *_ar.
    """
    if raw:
        return
    if not is_registered(sender):
        return
    if update_fields is not None and not created:
        if not _touches_source_fields(sender, update_fields):
            return
    translate_and_save(instance)
