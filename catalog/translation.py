"""django-modeltranslation registrations for catalog models."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, translator

from catalog.models import (
    Brand,
    Category,
    Occasion,
    Product,
    ProductImage,
    ProductVariant,
    Recipient,
)


class CategoryTranslation(TranslationOptions):
    fields = ("name", "meta_title", "meta_description")


class OccasionTranslation(TranslationOptions):
    fields = ("name",)


class BrandTranslation(TranslationOptions):
    fields = ("name",)


class RecipientTranslation(TranslationOptions):
    fields = ("name",)


class ProductTranslation(TranslationOptions):
    fields = ("name", "description", "color", "meta_title", "meta_description")


class ProductVariantTranslation(TranslationOptions):
    fields = ("name",)


class ProductImageTranslation(TranslationOptions):
    fields = ("alt_text",)


translator.register(Category, CategoryTranslation)
translator.register(Occasion, OccasionTranslation)
translator.register(Brand, BrandTranslation)
translator.register(Recipient, RecipientTranslation)
translator.register(Product, ProductTranslation)
translator.register(ProductVariant, ProductVariantTranslation)
translator.register(ProductImage, ProductImageTranslation)
