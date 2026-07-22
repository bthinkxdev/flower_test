"""HTTP views for the catalog app; thin request parsing delegating to selectors/services."""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST
from cart.selectors import get_cart_for_request, is_product_in_cart

from catalog.forms import ReviewForm
from catalog.models import ModerationStatus, Review
from catalog.selectors import (
    get_category_by_slug,
    get_plp_filter_options,
    get_plp_products,
    get_product_detail,
    get_search_suggestions,
    get_variant_price,
    record_product_view,
)
from catalog.services import submit_review
from orders.models import OrderItem, OrderStatus
from core.seo import build_plp_canonical_url, build_product_json_ld, resolve_meta_title, seo_context
from delivery.selectors import (
    get_active_cities,
    get_city_by_slug,
    get_earliest_delivery_estimate,
)


def _parse_plp_filters(request: HttpRequest) -> dict:
    """Parse shareable PLP filter query params into a selector filter dict."""
    filters: dict = {}
    if category_id := request.GET.get("category"):
        filters["category_id"] = int(category_id)
    if occasion_id := request.GET.get("occasion"):
        filters["occasion_id"] = int(occasion_id)
    if brand_id := request.GET.get("brand"):
        filters["brand_id"] = int(brand_id)
    if recipient_id := request.GET.get("recipient"):
        filters["recipient_id"] = int(recipient_id)
    if color := request.GET.get("color"):
        filters["color"] = color
    if request.GET.get("same_day") == "1":
        filters["same_day"] = True
    if request.GET.get("bestseller") == "1":
        filters["bestseller"] = True
    if request.GET.get("new_arrival") == "1":
        filters["new_arrival"] = True
    if request.GET.get("in_stock") == "1":
        filters["in_stock"] = True
    if min_price := request.GET.get("min_price"):
        filters["min_price"] = min_price
    if max_price := request.GET.get("max_price"):
        filters["max_price"] = max_price
    return filters


@require_GET
def plp_view(request: HttpRequest, category_slug: str | None = None) -> HttpResponse:
    """Product listing page with HTMX partial support for the product grid."""
    filters = _parse_plp_filters(request)
    category = None
    if category_slug:
        category = get_category_by_slug(slug=category_slug)
        if category is None:
            raise Http404("Category not found")
        if "category_id" not in filters and "category" not in request.GET:
            filters["category_id"] = category.pk

    sort = request.GET.get("sort", "newest")
    page = int(request.GET.get("page", 1))
    plp_data = get_plp_products(filters=filters, sort=sort, page=page)
    filter_options = get_plp_filter_options()

    active_category = category
    selected_category_id = filters.get("category_id")
    if selected_category_id and (category is None or selected_category_id != category.pk):
        active_category = next(
            (c for c in filter_options["categories"] if c.pk == selected_category_id),
            category,
        )
    elif not selected_category_id:
        active_category = None

    title = (
        resolve_meta_title(obj=active_category, fallback="Shop All Flowers & Gifts")
        if active_category
        else "Shop All Flowers & Gifts"
    )
    description = (
        f"Browse {active_category.name} flowers and gifts with same-day delivery in Qatar."
        if active_category
        else "Browse premium flowers and gifts with same-day delivery across Qatar."
    )

    context = seo_context(
        request=request,
        obj=active_category,
        title=f"{title} | Floward",
        description=description,
        canonical_url=build_plp_canonical_url(request=request, category_slug=category_slug),
    )
    context.update(
        {
            "plp": plp_data,
            "filters": filters,
            "sort": sort,
            "categories": filter_options["categories"],
            "occasions": filter_options["occasions"],
            "brands": filter_options["brands"],
            "recipients": filter_options["recipients"],
            "view_mode": request.COOKIES.get("plp_view", "grid"),
            "active_category": active_category,
        }
    )

    if request.headers.get("HX-Request"):
        return render(request, "catalog/partials/product_grid.html", context)
    return render(request, "catalog/plp.html", context)


@require_GET
def pdp_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Product detail page with gallery, variants, reviews, and delivery estimate."""
    product = get_product_detail(slug=slug)
    if product is None:
        raise Http404("Product not found")

    viewer_key = str(request.session.session_key or request.user.pk or "anon")
    record_product_view(viewer_key=viewer_key, product_id=product.pk)

    city_slug = request.GET.get("city", "doha")
    destination_city = get_city_by_slug(slug=city_slug)
    delivery_estimate = None
    if destination_city:
        delivery_estimate = get_earliest_delivery_estimate(
            product=product,
            destination_city=destination_city,
        )

    price_data = get_variant_price(product_id=product.pk)
    cart = get_cart_for_request(request=request)
    in_cart = is_product_in_cart(cart=cart, product_id=product.pk)
    reviews = getattr(product, "approved_reviews", [])
    review_count = len(reviews)
    average_rating = None
    if review_count:
        average_rating = sum(r.rating for r in reviews) / review_count

    can_review = False
    user_review = None
    if request.user.is_authenticated:
        customer_profile = getattr(request.user, "customer_profile", None)
        if customer_profile is not None:
            user_review = Review.objects.filter(
                product=product, customer=customer_profile
            ).first()
            has_purchased = (
                OrderItem.objects.filter(
                    product=product,
                    order__customer_profile=customer_profile,
                )
                .exclude(order__order_status__in=[OrderStatus.CANCELLED, OrderStatus.REFUNDED])
                .exists()
            )
            can_review = has_purchased and user_review is None

    context = seo_context(
        request=request,
        obj=product,
        title=f"{product.name} | Story of Flowers",
        description=f"{product.name} — premium flowers and gifts delivered in Qatar.",
    )
    context.update(
        {
            "product": product,
            "price_data": price_data,
            "delivery_estimate": delivery_estimate,
            "cities": get_active_cities(),
            "in_cart": in_cart,
            "product_json_ld": json.dumps(
                build_product_json_ld(
                    product=product,
                    price=price_data["price"],
                    request=request,
                    average_rating=average_rating,
                    review_count=review_count,
                )
            ),
            "review_form": ReviewForm(),
            "can_review": can_review,
            "user_review": user_review,
        }
    )
    return render(request, "catalog/pdp.html", context)

@login_required
@require_POST
def review_create_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Submit a review — only allowed for customers who purchased the product."""
    product = get_product_detail(slug=slug)
    if product is None:
        raise Http404("Product not found")

    customer_profile = getattr(request.user, "customer_profile", None)
    if customer_profile is None:
        messages.error(request, "Only customer accounts can write reviews.")
        return redirect("catalog:pdp", slug=slug)

    has_purchased = (
        OrderItem.objects.filter(product=product, order__customer_profile=customer_profile)
        .exclude(order__order_status__in=[OrderStatus.CANCELLED, OrderStatus.REFUNDED])
        .exists()
    )
    if not has_purchased:
        messages.error(request, "You can review a product only after purchasing it.")
        return redirect("catalog:pdp", slug=slug)

    if Review.objects.filter(product=product, customer=customer_profile).exists():
        messages.error(request, "You've already reviewed this product.")
        return redirect("catalog:pdp", slug=slug)

    form = ReviewForm(request.POST)
    if form.is_valid():
        submit_review(
            product=product,
            customer=customer_profile,
            rating=int(form.cleaned_data["rating"]),
            title=form.cleaned_data["title"],
            body=form.cleaned_data["body"],
            is_verified_purchase=True,
        )
        messages.success(request, "Thanks! Your review is submitted and pending moderation.")
    else:
        messages.error(request, "Please fix the errors and try again.")
    return redirect("catalog:pdp", slug=slug)


@require_GET
def search_suggestions_view(request: HttpRequest) -> HttpResponse:
    """HTMX live search suggestions partial."""
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return render(
            request,
            "catalog/partials/search_suggestions.html",
            {"products": [], "query": ""},
        )
    products = get_search_suggestions(query=query)
    return render(
        request,
        "catalog/partials/search_suggestions.html",
        {"products": products, "query": query},
    )


@require_GET
def variant_price_view(request: HttpRequest, product_id: int) -> JsonResponse:
    """JSON endpoint for variant price updates on PDP."""
    variant_id = request.GET.get("variant_id")
    parsed_variant = int(variant_id) if variant_id else None
    data = get_variant_price(product_id=product_id, variant_id=parsed_variant)
    return JsonResponse(data)


@require_GET
def delivery_estimate_view(request: HttpRequest, product_id: int) -> JsonResponse:
    """JSON endpoint for delivery estimate widget on PDP."""
    from catalog.selectors import get_products_by_ids

    products = get_products_by_ids(product_ids=[product_id])
    if not products:
        raise Http404("Product not found")
    product = products[0]
    city_slug = request.GET.get("city", "doha")
    city = get_city_by_slug(slug=city_slug)
    if city is None:
        raise Http404("City not found")
    estimate = get_earliest_delivery_estimate(product=product, destination_city=city)
    return JsonResponse(estimate)
