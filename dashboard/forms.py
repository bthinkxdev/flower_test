"""ModelForms used by the admin dashboard CRUD screens."""

from __future__ import annotations

from django import forms
from django.utils.text import slugify

from accounts.models import CorporateAccount, CustomerProfile
from catalog.models import (
    Brand,
    Category,
    Occasion,
    Product,
    ProductImage,
    ProductVariant,
    Recipient,
    Review,
)
from cms.models import BlogPost, FAQItem, HeroSlide, HomepageSection, Page, PolicyDocument
from core.models import SiteSettings
from delivery.models import City, DeliverySlot
from marketing.models import Coupon, FlashSale, GiftCard, NewsletterSubscriber
from gifting.models import (
    GiftWrapOption,
    GreetingCardDesign,
    RibbonOption,
    GiftPhotoUploadOption,
    GiftAddonEligibility,
    GiftCardEligibility,
    GiftWrapEligibility,
    RibbonEligibility,
    GiftPhotoUploadEligibility,
    GiftCustomizationConfig,
)
from django.contrib.contenttypes.forms import generic_inlineformset_factory

_DATE = forms.DateInput(attrs={"type": "date"})
_DATETIME = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
_TIME = forms.TimeInput(attrs={"type": "time"})


class SlugAutoMixin(forms.ModelForm):
    """Auto-populate an empty ``slug`` from ``name``/``title`` on save."""

    def clean(self):
        cleaned = super().clean()
        if "slug" in self.fields and not cleaned.get("slug"):
            source = cleaned.get("name") or cleaned.get("title")
            if source:
                cleaned["slug"] = slugify(source)
        return cleaned


class ProductForm(SlugAutoMixin):
    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "sku",
            "category",
            "primary_occasion",
            "brand",
            "recipients",
            "base_price",
            "color",
            "stock_quantity",
            "low_stock_threshold",
            "is_active",
            "is_same_day_eligible",
            "is_bestseller",
            "is_new_arrival",
            "supports_gift_customization",
            "meta_title",
            "meta_description",
            "og_image",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class CategoryForm(SlugAutoMixin):
    class Meta:
        model = Category
        fields = [
            "name",
            "slug",
            "parent",
            "display_order",
            "is_active",
            "meta_title",
            "meta_description",
            "og_image",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class OccasionForm(SlugAutoMixin):
    class Meta:
        model = Occasion
        fields = ["name", "slug", "icon", "is_seasonal", "active_from", "active_to"]
        widgets = {"active_from": _DATE, "active_to": _DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class BrandForm(SlugAutoMixin):
    class Meta:
        model = Brand
        fields = ["name", "slug", "logo", "is_featured"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class RecipientForm(SlugAutoMixin):
    class Meta:
        model = Recipient
        fields = ["name", "slug", "icon", "display_order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["moderation_status"]


ProductVariantFormSet = forms.inlineformset_factory(
    Product,
    ProductVariant,
    fields=["variant_type", "name", "price_delta", "sku_suffix", "stock_quantity"],
    extra=1,
    can_delete=True,
)
ProductImageFormSet = forms.inlineformset_factory(
    Product,
    ProductImage,
    fields=["image", "alt_text", "display_order", "is_primary"],
    extra=1,
    can_delete=True,
)


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = [
            "phone",
            "phone_verified",
            "preferred_language",
            "preferred_currency",
            "notify_via_email",
            "notify_via_sms",
            "notify_via_whatsapp",
        ]


class CorporateAccountForm(forms.ModelForm):
    class Meta:
        model = CorporateAccount
        fields = ["company_name", "trade_license_number", "approval_status"]


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code",
            "discount_type",
            "discount_value",
            "min_order_value",
            "max_uses",
            "max_uses_per_customer",
            "valid_from",
            "valid_until",
            "applicable_categories",
            "is_active",
        ]
        widgets = {"valid_from": _DATETIME, "valid_until": _DATETIME}


class GiftCardForm(forms.ModelForm):
    class Meta:
        model = GiftCard
        fields = ["code", "initial_balance", "balance", "is_active"]


class FlashSaleForm(forms.ModelForm):
    class Meta:
        model = FlashSale
        fields = ["name", "products", "discount_percentage", "starts_at", "ends_at", "is_active"]
        widgets = {"starts_at": _DATETIME, "ends_at": _DATETIME}


class NewsletterSubscriberForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ["email", "is_active"]

class GreetingCardDesignForm(SlugAutoMixin):
    class Meta:
        model = GreetingCardDesign
        fields = ["name", "occasion", "image", "is_active"]


class GiftWrapOptionForm(forms.ModelForm):
    class Meta:
        model = GiftWrapOption
        fields = ["name", "price_delta", "is_active"]


class RibbonOptionForm(forms.ModelForm):
    class Meta:
        model = RibbonOption
        fields = ["name", "price_delta", "is_active"]


class GiftPhotoUploadOptionForm(forms.ModelForm):
    class Meta:
        model = GiftPhotoUploadOption
        fields = ["name", "price_delta", "is_active"]

class GiftCustomizationConfigForm(forms.ModelForm):
    class Meta:
        model = GiftCustomizationConfig
        fields = [
            "allows_personal_message",
            "allows_greeting_card",
            "allows_gift_wrap",
            "allows_ribbon",
            "allows_addons",
            "allows_anonymous",
            "allows_gift_receipt",
            "allows_midnight_delivery",
            "allows_photo_upload",
        ]


GiftAddonEligibilityFormSet = generic_inlineformset_factory(
    GiftAddonEligibility,
    fields=["addon_product"],
    extra=1,
    can_delete=True,
)
GiftAddonEligibilityFormSet = generic_inlineformset_factory(
    GiftAddonEligibility,
    fields=["addon_product"],
    extra=1,
    can_delete=True,
)
GiftCardEligibilityFormSet = generic_inlineformset_factory(
    GiftCardEligibility,
    fields=["greeting_card"],
    extra=1,
    can_delete=True,
)
GiftWrapEligibilityFormSet = generic_inlineformset_factory(
    GiftWrapEligibility,
    fields=["gift_wrap"],
    extra=1,
    can_delete=True,
)
GiftRibbonEligibilityFormSet = generic_inlineformset_factory(
    RibbonEligibility,
    fields=["ribbon"],
    extra=1,
    can_delete=True,
)
GiftPhotoEligibilityFormSet = generic_inlineformset_factory(
    GiftPhotoUploadEligibility,
    fields=["photo_upload"],
    extra=1,
    can_delete=True,
)
class HomepageSectionForm(forms.ModelForm):
    class Meta:
        model = HomepageSection
        fields = ["section_type", "title", "display_order", "is_active", "config"]


class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = ["title", "image", "video", "poster", "display_order", "is_active"]


class BlogPostForm(SlugAutoMixin):
    class Meta:
        model = BlogPost
        fields = [
            "title",
            "slug",
            "excerpt",
            "body",
            "is_published",
            "publish_at",
            "meta_title",
            "meta_description",
            "og_image",
        ]
        widgets = {"publish_at": _DATETIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class PageForm(SlugAutoMixin):
    class Meta:
        model = Page
        fields = [
            "title",
            "slug",
            "body",
            "is_published",
            "publish_at",
            "meta_title",
            "meta_description",
            "og_image",
        ]
        widgets = {"publish_at": _DATETIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class FAQItemForm(forms.ModelForm):
    class Meta:
        model = FAQItem
        fields = ["question", "answer", "display_order", "is_published", "publish_at"]
        widgets = {"publish_at": _DATETIME}


class PolicyDocumentForm(SlugAutoMixin):
    class Meta:
        model = PolicyDocument
        fields = [
            "title",
            "slug",
            "policy_type",
            "body",
            "is_published",
            "publish_at",
            "meta_title",
            "meta_description",
            "og_image",
        ]
        widgets = {"publish_at": _DATETIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class CityForm(SlugAutoMixin):
    class Meta:
        model = City
        fields = [
            "country",
            "name",
            "slug",
            "delivery_charge_base",
            "same_day_cutoff_hour",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class DeliverySlotForm(forms.ModelForm):
    class Meta:
        model = DeliverySlot
        fields = [
            "name",
            "start_time",
            "end_time",
            "slot_type",
            "max_capacity_per_day",
            "is_active",
        ]
        widgets = {"start_time": _TIME, "end_time": _TIME}


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "site_name",
            "logo_url",
            "primary_color",
            "secondary_color",
            "font_family",
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "whatsapp_number",
            "default_currency",
            "default_language",
            "tax_rate_percent",
            "default_shipping_charge",
        ]


class OrderStatusForm(forms.Form):
    """Free-standing form for applying an order status transition."""

    new_status = forms.ChoiceField(choices=[])
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, allowed_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_status"].choices = allowed_choices or []
