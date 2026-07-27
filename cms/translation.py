"""django-modeltranslation registrations for CMS models."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, translator

from cms.models import (
    BlogPost,
    FAQItem,
    HeroSlide,
    HomepageSection,
    Page,
    PolicyDocument,
)


class HomepageSectionTranslation(TranslationOptions):
    fields = ("title", "config")


class HeroSlideTranslation(TranslationOptions):
    fields = ("title",)


class BlogPostTranslation(TranslationOptions):
    fields = ("title", "body", "excerpt", "meta_title", "meta_description")


class PageTranslation(TranslationOptions):
    fields = ("title", "body", "meta_title", "meta_description")


class FAQItemTranslation(TranslationOptions):
    fields = ("question", "answer")


class PolicyDocumentTranslation(TranslationOptions):
    fields = ("title", "body", "meta_title", "meta_description")


translator.register(HomepageSection, HomepageSectionTranslation)
translator.register(HeroSlide, HeroSlideTranslation)
translator.register(BlogPost, BlogPostTranslation)
translator.register(Page, PageTranslation)
translator.register(FAQItem, FAQItemTranslation)
translator.register(PolicyDocument, PolicyDocumentTranslation)
