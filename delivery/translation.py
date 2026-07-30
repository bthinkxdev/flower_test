"""django-modeltranslation registrations for delivery models."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, translator

from delivery.models import City, Country, DeliverySlot, DeliveryZone


class CountryTranslation(TranslationOptions):
    fields = ("name",)


class CityTranslation(TranslationOptions):
    fields = ("name",)


class DeliveryZoneTranslation(TranslationOptions):
    fields = ("name",)


class DeliverySlotTranslation(TranslationOptions):
    fields = ("name",)


translator.register(Country, CountryTranslation)
translator.register(City, CityTranslation)
translator.register(DeliveryZone, DeliveryZoneTranslation)
translator.register(DeliverySlot, DeliverySlotTranslation)
