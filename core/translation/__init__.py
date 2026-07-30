"""
Application-wide content translation.

Architecture:
    registry.py  — declarative model/field maps (no logic)
    service.py   — sole place that calls deep-translator and writes *_ar
    signals.py   — one shared post_save → translate_and_save()

django-modeltranslation discovers TranslationOptions in this package for the
core app (SiteSettings). Other apps register via their own translation.py.
"""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, translator

from core.models import SiteSettings


class SiteSettingsTranslation(TranslationOptions):
    """modeltranslation registration for SiteSettings."""

    fields = ("site_name",)


translator.register(SiteSettings, SiteSettingsTranslation)
