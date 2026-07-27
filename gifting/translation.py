"""django-modeltranslation registrations for gifting models."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, translator

from gifting.models import (
    GiftPhotoUploadOption,
    GiftWrapOption,
    GreetingCardDesign,
    RibbonOption,
)


class GreetingCardDesignTranslation(TranslationOptions):
    fields = ("name",)


class GiftWrapOptionTranslation(TranslationOptions):
    fields = ("name",)


class RibbonOptionTranslation(TranslationOptions):
    fields = ("name",)


class GiftPhotoUploadOptionTranslation(TranslationOptions):
    fields = ("name",)


translator.register(GreetingCardDesign, GreetingCardDesignTranslation)
translator.register(GiftWrapOption, GiftWrapOptionTranslation)
translator.register(RibbonOption, RibbonOptionTranslation)
translator.register(GiftPhotoUploadOption, GiftPhotoUploadOptionTranslation)
