"""
Single translation service for the entire application.

This is the only module allowed to call deep-translator, write Arabic fields,
and decide whether a manual translation lock applies.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from deep_translator import GoogleTranslator
from django.db import models

from core.models import ArTranslationSource
from core.translation.registry import (
    JSON_TRANSLATABLE_KEYS,
    get_translated_fields,
    get_translated_json_fields,
)

logger = logging.getLogger(__name__)

_translator: GoogleTranslator | None = None


def _get_translator() -> GoogleTranslator:
    """Return a shared GoogleTranslator instance (en → ar)."""
    global _translator
    if _translator is None:
        _translator = GoogleTranslator(source="en", target="ar")
    return _translator


def _translate_text(text: str) -> str | None:
    """
    Translate a non-empty English string to Arabic.

    Returns:
        Translated string on success, None on failure (caller must leave Arabic unchanged).
        Empty / whitespace-only input returns "" (no API call).
    """
    if not text or not str(text).strip():
        return ""
    try:
        return _get_translator().translate(str(text))
    except Exception:
        logger.exception("Automatic EN→AR translation failed")
        return None


def _read_english(instance: models.Model, field_name: str) -> Any:
    """Read the English source value for a modeltranslation field."""
    en_attr = f"{field_name}_en"
    if hasattr(instance, en_attr):
        return getattr(instance, en_attr)
    return getattr(instance, field_name, None)


def _translate_json(value: Any) -> Any | None:
    """
    Deep-copy ``value`` and translate user-visible string keys.

    Returns None if any string translation fails (entire JSON field left unchanged).
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if key in JSON_TRANSLATABLE_KEYS and isinstance(child, str):
                translated = _translate_text(child)
                if translated is None:
                    return None
                result[key] = translated
            else:
                nested = _translate_json(child)
                if nested is None:
                    return None
                result[key] = nested
        return result

    if isinstance(value, list):
        items: list[Any] = []
        for child in value:
            nested = _translate_json(child)
            if nested is None:
                return None
            items.append(nested)
        return items

    return deepcopy(value)


def translate_and_save(instance: models.Model) -> None:
    """
    Translate English source fields to Arabic and persist.

    Rules:
    - English is the source of truth.
    - When ``ar_translation_source == manual``, Arabic is never overwritten.
    - On translation failure, log and leave that Arabic field unchanged.
    - Persistence uses QuerySet.update() so post_save is not re-entered.
    """
    source = getattr(instance, "ar_translation_source", ArTranslationSource.AUTO)
    if source == ArTranslationSource.MANUAL:
        return

    model = instance.__class__
    field_names = get_translated_fields(model)
    json_field_names = get_translated_json_fields(model)
    if not field_names and not json_field_names:
        return

    if instance.pk is None:
        return

    updates: dict[str, Any] = {}

    for field_name in field_names:
        en_value = _read_english(instance, field_name)
        if en_value is None:
            continue
        if not isinstance(en_value, str):
            en_value = str(en_value)
        translated = _translate_text(en_value)
        if translated is None:
            continue
        updates[f"{field_name}_ar"] = translated

    for field_name in json_field_names:
        en_value = _read_english(instance, field_name)
        if en_value in (None, "", {}, []):
            continue
        translated_json = _translate_json(en_value)
        if translated_json is None:
            continue
        updates[f"{field_name}_ar"] = translated_json

    if not updates:
        return

    model.objects.filter(pk=instance.pk).update(**updates)
    for attr, value in updates.items():
        setattr(instance, attr, value)
