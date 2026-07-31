"""Catalog management views: products, categories, occasions, brands, recipients, reviews."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from catalog.models import Brand, Category, Occasion, Product, ProductVariant, Recipient, Review
from core.models import Currency
from dashboard import forms
from dashboard.access import dashboard_required
from dashboard.views.base import (
    DashboardCreateView,
    DashboardDeleteView,
    DashboardListView,
    DashboardUpdateView,
)
from django.contrib.contenttypes.models import ContentType
from gifting.models import (
    GiftCustomizationConfig, GiftCardEligibility, GiftWrapEligibility,
    RibbonEligibility, GiftPhotoUploadEligibility,
) 
class ProductListView(DashboardListView):
    model = Product
    template_name = "dashboard/catalog/product_list.html"
    nav_section = "products"
    url_basename = "product"
    singular_name = "Product"
    plural_name = "Products"
    search_fields = ["name", "sku"]
    select_related = ["category", "brand"]
    prefetch_related = ["images"]
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get("status", "")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        elif status == "low":
            qs = qs.filter(stock_quantity__lte=F("low_stock_threshold"))
        elif status == "out":
            qs = qs.filter(stock_quantity=0)
        category = self.request.GET.get("category", "")
        if category.isdigit():
            qs = qs.filter(category_id=int(category))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        default_currency = Currency.objects.filter(is_default=True).first()
        context["currency_symbol"] = default_currency.symbol if default_currency else ""
        context["categories"] = Category.objects.order_by("name")
        context["status_filter"] = self.request.GET.get("status", "")
        context["category_filter"] = self.request.GET.get("category", "")
        return context


class ProductDeleteView(DashboardDeleteView):
    model = Product
    nav_section = "products"
    url_basename = "product"
    singular_name = "Product"


def _get_or_build_gift_config(product):
    """Return the GiftCustomizationConfig for a product, unsaved if new."""
    content_type = ContentType.objects.get_for_model(Product)
    config = None
    if product is not None and product.pk:
        config = GiftCustomizationConfig.objects.filter(
            content_type=content_type, object_id=product.pk
        ).first()
    if config is None:
        config = GiftCustomizationConfig(content_type=content_type, object_id=None)
    return config

_ELIGIBILITY_SPECS = [
    ("addons", "GiftAddonEligibilityFormSet"),
    ("cards", "GiftCardEligibilityFormSet"),
    ("wraps", "GiftWrapEligibilityFormSet"),
    ("ribbons", "GiftRibbonEligibilityFormSet"),
    ("photos", "GiftPhotoEligibilityFormSet"),
]


def _build_eligibility_formsets(product, *, data=None):
    formsets = {}
    for prefix, formset_name in _ELIGIBILITY_SPECS:
        formset_cls = getattr(forms, formset_name)
        formsets[prefix] = formset_cls(data, instance=product, prefix=prefix)
    return formsets

def _render_product_form(request, product, mode):
    gift_config = _get_or_build_gift_config(product)

    if request.method == "POST":
        form = forms.ProductForm(request.POST, request.FILES, instance=product)
        variants = forms.ProductVariantFormSet(request.POST, instance=product, prefix="variants")
        images = forms.ProductImageFormSet(
            request.POST, request.FILES, instance=product, prefix="images"
        )
        gift_config_form = forms.GiftCustomizationConfigForm(
            request.POST, instance=gift_config, prefix="giftconfig"
        )
        eligibility = _build_eligibility_formsets(product, data=request.POST)
        addon_eligibility = eligibility["addons"]  

        valid = form.is_valid() and variants.is_valid() and images.is_valid()
        wants_gift = form.data.get("supports_gift_customization") or (
            form.instance.pk and form.cleaned_data.get("supports_gift_customization")
            if form.is_valid() else False
        )
        if wants_gift:
            valid = valid and gift_config_form.is_valid()
            for fs in eligibility.values():
                if fs is not None:
                    valid = valid and fs.is_valid()

        if valid:
            product = form.save()
            variants.instance = product
            variants.save()
            images.instance = product
            images.save()

            if product.supports_gift_customization:
                gift_config_form.instance.content_type = ContentType.objects.get_for_model(
                    Product
                )
                gift_config_form.instance.object_id = product.pk
                gift_config_form.save()

                for prefix, formset_name in _ELIGIBILITY_SPECS:
                    fs = eligibility[prefix]
                    if fs is None:
                        fs = getattr(forms, formset_name)(
                            request.POST, instance=product, prefix=prefix
                        )
                        if fs.is_valid():
                            fs.save()
                    else:
                        fs.instance = product
                        fs.save()
            else:
                # Customization turned off — remove the config so the builder
                # route 404s cleanly instead of leaving an orphaned config row.
                GiftCustomizationConfig.objects.filter(
                    content_type=ContentType.objects.get_for_model(Product),
                    object_id=product.pk,
                ).delete()

            messages.success(request, f"Product {'created' if mode == 'create' else 'updated'}.")
            return redirect("dashboard:product-list")
    else:
        form = forms.ProductForm(instance=product)
        variants = forms.ProductVariantFormSet(instance=product, prefix="variants")
        images = forms.ProductImageFormSet(instance=product, prefix="images")
        gift_config_form = forms.GiftCustomizationConfigForm(
            instance=gift_config, prefix="giftconfig"
        )
        eligibility = _build_eligibility_formsets(product)
        addon_eligibility = eligibility["addons"]

    variants_empty_form = variants.empty_form
    images_empty_form = images.empty_form

    for f in [form, *variants.forms, variants_empty_form, *images.forms, images_empty_form,
              gift_config_form]:
        _style(f)

    eligibility_empty_forms = {}
    for name, fs in eligibility.items():
        if fs is not None:
            eligibility_empty_forms[name] = fs.empty_form
            for f in [*fs.forms, eligibility_empty_forms[name]]:
                _style(f)

    context = {
        "nav_section": "products",
        "page_title": f"{'Add' if mode == 'create' else 'Edit'} Product",
        "form": form,
        "variants": variants,
        "images": images,
        "gift_config_form": gift_config_form,
        "addon_eligibility": addon_eligibility,
        "form_mode": mode,
        "product": product,
        "cancel_url": reverse("dashboard:product-list"),
        "existing_variant_types": sorted(set(v.title() for v in ProductVariant.objects.values_list("variant_type", flat=True) if v)),
    }
    context.update({
        "card_eligibility": eligibility["cards"],
        "wrap_eligibility": eligibility["wraps"],
        "ribbon_eligibility": eligibility["ribbons"],
        "photo_eligibility": eligibility["photos"],
        "variants_empty_form": variants_empty_form,
        "images_empty_form": images_empty_form,
        "addon_empty_form": eligibility_empty_forms.get("addons"),
        "card_empty_form": eligibility_empty_forms.get("cards"),
        "wrap_empty_form": eligibility_empty_forms.get("wraps"),
        "ribbon_empty_form": eligibility_empty_forms.get("ribbons"),
        "photo_empty_form": eligibility_empty_forms.get("photos"),
    })
    return render(request, "dashboard/catalog/product_form.html", context)


def _style(form):
    """Apply Bootstrap classes to a form's widgets (shared with generic mixin)."""
    for field in form.fields.values():
        widget = field.widget
        css = widget.attrs.get("class", "")
        name = widget.__class__.__name__.lower()
        if "checkbox" in name:
            widget.attrs["class"] = (css + " form-check-input").strip()
        elif "select" in name:
            widget.attrs["class"] = (css + " form-select").strip()
        elif "file" in name:
            widget.attrs["class"] = (css + " form-control").strip()
        else:
            widget.attrs["class"] = (css + " form-control").strip()


@dashboard_required
@require_http_methods(["GET", "POST"])
def product_create(request):
    return _render_product_form(request, None, "create")


@dashboard_required
@require_http_methods(["GET", "POST"])
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return _render_product_form(request, product, "edit")


class CategoryListView(DashboardListView):
    model = Category
    nav_section = "categories"
    url_basename = "category"
    singular_name = "Category"
    plural_name = "Categories"
    search_fields = ["name", "slug"]
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Slug", "name": "slug"},
        {"label": "Parent", "name": "parent.name"},
        {"label": "Order", "name": "display_order"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class CategoryCreateView(DashboardCreateView):
    model = Category
    form_class = forms.CategoryForm
    nav_section = "categories"
    url_basename = "category"
    singular_name = "Category"


class CategoryUpdateView(DashboardUpdateView):
    model = Category
    form_class = forms.CategoryForm
    nav_section = "categories"
    url_basename = "category"
    singular_name = "Category"


class CategoryDeleteView(DashboardDeleteView):
    model = Category
    nav_section = "categories"
    url_basename = "category"
    singular_name = "Category"


class OccasionListView(DashboardListView):
    model = Occasion
    nav_section = "occasions"
    url_basename = "occasion"
    singular_name = "Occasion"
    plural_name = "Occasions"
    search_fields = ["name", "slug"]
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Slug", "name": "slug"},
        {"label": "Seasonal", "name": "is_seasonal", "type": "bool"},
        {"label": "Active from", "name": "active_from"},
        {"label": "Active to", "name": "active_to"},
    ]


class OccasionCreateView(DashboardCreateView):
    model = Occasion
    form_class = forms.OccasionForm
    nav_section = "occasions"
    url_basename = "occasion"
    singular_name = "Occasion"


class OccasionUpdateView(DashboardUpdateView):
    model = Occasion
    form_class = forms.OccasionForm
    nav_section = "occasions"
    url_basename = "occasion"
    singular_name = "Occasion"


class OccasionDeleteView(DashboardDeleteView):
    model = Occasion
    nav_section = "occasions"
    url_basename = "occasion"
    singular_name = "Occasion"


class BrandListView(DashboardListView):
    model = Brand
    nav_section = "brands"
    url_basename = "brand"
    singular_name = "Brand"
    plural_name = "Brands"
    search_fields = ["name", "slug"]
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Slug", "name": "slug"},
        {"label": "Featured", "name": "is_featured", "type": "bool"},
    ]


class BrandCreateView(DashboardCreateView):
    model = Brand
    form_class = forms.BrandForm
    nav_section = "brands"
    url_basename = "brand"
    singular_name = "Brand"


class BrandUpdateView(DashboardUpdateView):
    model = Brand
    form_class = forms.BrandForm
    nav_section = "brands"
    url_basename = "brand"
    singular_name = "Brand"


class BrandDeleteView(DashboardDeleteView):
    model = Brand
    nav_section = "brands"
    url_basename = "brand"
    singular_name = "Brand"


class RecipientListView(DashboardListView):
    model = Recipient
    nav_section = "recipients"
    url_basename = "recipient"
    singular_name = "Recipient"
    plural_name = "Recipients"
    search_fields = ["name", "slug"]
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Slug", "name": "slug"},
        {"label": "Order", "name": "display_order"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class RecipientCreateView(DashboardCreateView):
    model = Recipient
    form_class = forms.RecipientForm
    nav_section = "recipients"
    url_basename = "recipient"
    singular_name = "Recipient"


class RecipientUpdateView(DashboardUpdateView):
    model = Recipient
    form_class = forms.RecipientForm
    nav_section = "recipients"
    url_basename = "recipient"
    singular_name = "Recipient"


class RecipientDeleteView(DashboardDeleteView):
    model = Recipient
    nav_section = "recipients"
    url_basename = "recipient"
    singular_name = "Recipient"


class ReviewListView(DashboardListView):
    model = Review
    nav_section = "reviews"
    url_basename = "review"
    singular_name = "Review"
    plural_name = "Reviews"
    select_related = ["product", "customer__user"]
    can_create = False
    columns = [
        {"label": "Product", "name": "product.name"},
        {"label": "Rating", "name": "rating"},
        {"label": "Title", "name": "title"},
        {"label": "Status", "name": "get_moderation_status_display", "type": "badge"},
        {"label": "Submitted", "name": "created_at", "type": "datetime"},
    ]


class ReviewUpdateView(DashboardUpdateView):
    model = Review
    form_class = forms.ReviewForm
    nav_section = "reviews"
    url_basename = "review"
    singular_name = "Review"

    def form_valid(self, form):
        from catalog.models import ModerationStatus
        
        status = form.cleaned_data.get("moderation_status")
        if status in {ModerationStatus.APPROVED, ModerationStatus.REJECTED}:
            form.instance.moderated_by = self.request.user

        response = super().form_valid(form)

        review = form.instance
        if status == ModerationStatus.APPROVED:
            from notifications.models import Notification
            Notification.objects.filter(
                title="Review pending moderation",
                body=f'Review "{review.title}" on {review.product.name} awaits approval.'
            ).delete()

        return response


class ReviewDeleteView(DashboardDeleteView):
    model = Review
    nav_section = "reviews"
    url_basename = "review"
    singular_name = "Review"

    def form_valid(self, form):
        #clear notification 
        original_review = self.get_object()
        from notifications.models import Notification
        body_text = f'Review "{original_review.title}" on {original_review.product.name} awaits approval.'
        Notification.objects.filter(
            title="Review pending moderation", 
            body=body_text,
            is_read=False
        ).update(is_read=True)
        
        return super().form_valid(form)
