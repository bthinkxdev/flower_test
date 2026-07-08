"""Structured admin forms per homepage section type — one entry per type."""

from __future__ import annotations

from django import forms

from cms.models import HomepageSectionType


class BaseSectionConfigForm(forms.Form):
    """Base for section config fields that serialize into HomepageSection.config."""

    def to_config(self) -> dict:
        return self.cleaned_data


class HeroSliderConfigForm(BaseSectionConfigForm):
    headline = forms.CharField(max_length=200, required=False)
    cta_text = forms.CharField(max_length=80, required=False)


class ShopByOccasionConfigForm(BaseSectionConfigForm):
    occasion_ids = forms.CharField(
        help_text="Comma-separated occasion IDs",
        required=False,
    )

    def to_config(self) -> dict:
        raw = self.cleaned_data.get("occasion_ids", "")
        ids = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        return {"occasion_ids": ids}


class ProductCollectionConfigForm(BaseSectionConfigForm):
    product_ids = forms.CharField(
        help_text="Comma-separated product IDs",
        required=False,
    )
    collection_key = forms.CharField(max_length=80, required=False)
    brand_id = forms.IntegerField(
        required=False,
        min_value=1,
        help_text="Optional: limit this collection to a single brand (Brand Campaign).",
    )

    def to_config(self) -> dict:
        raw = self.cleaned_data.get("product_ids", "")
        ids = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        config: dict = {"product_ids": ids}
        if self.cleaned_data.get("collection_key"):
            config["collection_key"] = self.cleaned_data["collection_key"]
        if self.cleaned_data.get("brand_id"):
            config["brand_id"] = self.cleaned_data["brand_id"]
        return config


class MarketingFeaturesConfigForm(BaseSectionConfigForm):
    cards = forms.CharField(
        widget=forms.Textarea,
        required=False,
        help_text="One card per line: Title | URL | Image URL",
    )

    def to_config(self) -> dict:
        cards = []
        for line in self.cleaned_data.get("cards", "").splitlines():
            parts = [p.strip() for p in line.split("|")]
            if not parts or not parts[0]:
                continue
            cards.append(
                {
                    "title": parts[0],
                    "url": parts[1] if len(parts) > 1 else "",
                    "image": parts[2] if len(parts) > 2 else "",
                }
            )
        return {"cards": cards}


class BannerConfigForm(BaseSectionConfigForm):
    image_url = forms.URLField(required=False)
    link_url = forms.URLField(required=False)
    subtitle = forms.CharField(max_length=200, required=False)


class InstagramConfigForm(BaseSectionConfigForm):
    instagram_handle = forms.CharField(max_length=80, required=False)
    post_urls = forms.CharField(
        widget=forms.Textarea,
        required=False,
        help_text="One image URL per line",
    )

    def to_config(self) -> dict:
        raw = self.cleaned_data.get("post_urls", "")
        urls = [line.strip() for line in raw.splitlines() if line.strip()]
        return {
            "instagram_handle": self.cleaned_data.get("instagram_handle", ""),
            "post_urls": urls,
        }


class EmptyConfigForm(BaseSectionConfigForm):
    """Sections that need no extra config."""


SECTION_CONFIG_FORMS: dict[str, type[BaseSectionConfigForm]] = {
    HomepageSectionType.HERO_SLIDER: HeroSliderConfigForm,
    HomepageSectionType.SHOP_BY_OCCASION: EmptyConfigForm,
    HomepageSectionType.SHOP_BY_RECIPIENT: EmptyConfigForm,
    HomepageSectionType.SHOP_BY_CATEGORY: ShopByOccasionConfigForm,
    HomepageSectionType.PREMIUM_COLLECTION: ProductCollectionConfigForm,
    HomepageSectionType.SEASONAL_COLLECTION: ProductCollectionConfigForm,
    HomepageSectionType.LUXURY_COLLECTION: ProductCollectionConfigForm,
    HomepageSectionType.SAME_DAY_DELIVERY: EmptyConfigForm,
    HomepageSectionType.TRENDING: EmptyConfigForm,
    HomepageSectionType.BEST_SELLERS: EmptyConfigForm,
    HomepageSectionType.FEATURED_BRANDS: EmptyConfigForm,
    HomepageSectionType.CORPORATE_GIFTS_BANNER: BannerConfigForm,
    HomepageSectionType.SUBSCRIPTION_BANNER: BannerConfigForm,
    HomepageSectionType.MARKETING_FEATURES: MarketingFeaturesConfigForm,
    HomepageSectionType.REVIEWS: EmptyConfigForm,
    HomepageSectionType.INSTAGRAM_GALLERY: InstagramConfigForm,
    HomepageSectionType.NEWSLETTER: EmptyConfigForm,
}


def get_section_config_form(
    *, section_type: str, initial: dict | None = None
) -> BaseSectionConfigForm:
    """Return the structured config form for a section type."""
    form_class = SECTION_CONFIG_FORMS.get(section_type, EmptyConfigForm)
    initial_data = _flatten_config_for_form(section_type=section_type, config=initial or {})
    return form_class(initial=initial_data)


def _flatten_config_for_form(*, section_type: str, config: dict) -> dict:
    """Map stored JSON config to form initial values."""
    if section_type == HomepageSectionType.SHOP_BY_CATEGORY:
        ids = config.get("occasion_ids", [])
        return {"occasion_ids": ",".join(str(i) for i in ids)}
    if section_type in {
        HomepageSectionType.PREMIUM_COLLECTION,
        HomepageSectionType.SEASONAL_COLLECTION,
        HomepageSectionType.LUXURY_COLLECTION,
    }:
        ids = config.get("product_ids", [])
        return {
            "product_ids": ",".join(str(i) for i in ids),
            "collection_key": config.get("collection_key", ""),
            "brand_id": config.get("brand_id"),
        }
    if section_type == HomepageSectionType.MARKETING_FEATURES:
        lines = [
            " | ".join(
                part
                for part in (card.get("title", ""), card.get("url", ""), card.get("image", ""))
                if part
            )
            for card in config.get("cards", [])
        ]
        return {"cards": "\n".join(lines)}
    if section_type == HomepageSectionType.INSTAGRAM_GALLERY:
        return {
            "instagram_handle": config.get("instagram_handle", ""),
            "post_urls": "\n".join(config.get("post_urls", [])),
        }
    if section_type == HomepageSectionType.HERO_SLIDER:
        slides = config.get("slides", [])
        first = slides[0] if slides else {}
        return {
            "headline": first.get("headline", ""),
            "cta_text": first.get("cta_text", ""),
        }
    return {k: v for k, v in config.items() if isinstance(v, (str, int, float, bool))}


def config_from_form(*, section_type: str, form: BaseSectionConfigForm) -> dict:
    """Serialize a validated config form back to JSON storage."""
    if not form.is_valid():
        return {}
    data = form.to_config()
    if section_type == HomepageSectionType.HERO_SLIDER:
        return {
            "slides": [
                {
                    "headline": data.get("headline", ""),
                    "cta_text": data.get("cta_text", ""),
                }
            ]
        }
    return data
