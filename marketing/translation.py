"""django-modeltranslation registrations for marketing models."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, translator

from marketing.models import FlashSale


class FlashSaleTranslation(TranslationOptions):
    fields = ("name",)


translator.register(FlashSale, FlashSaleTranslation)
