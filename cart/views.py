"""HTTP views for the cart app."""

from __future__ import annotations

import json

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from cart.selectors import get_cart_count, get_cart_for_request, get_cart_summary
from cart.services import add_to_cart, get_or_create_cart, remove_cart_item, toggle_wishlist
from catalog.selectors import get_product_for_cart_add


def _cart_drawer_response(request: HttpRequest, *, hx_triggers: dict | None = None) -> HttpResponse:
    """Render cart drawer partial; optionally attach HTMX trigger headers."""
    cart = get_cart_for_request(request=request)
    summary = get_cart_summary(cart=cart) if cart else None
    response = render(
        request,
        "cart/partials/drawer.html",
        {
            "summary": summary,
            "cart_count": summary.item_count if summary else 0,
        },
    )
    if hx_triggers:
        response["HX-Trigger"] = json.dumps(hx_triggers)
    return response


@require_GET
def cart_drawer_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial for the cart drawer."""
    return _cart_drawer_response(request)


@require_GET
def cart_count_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial for the header cart badge — lightweight COUNT only."""
    return render(
        request,
        "cart/partials/count_badge.html",
        {"count": get_cart_count(request=request)},
    )


@require_POST
def cart_add_view(request: HttpRequest) -> HttpResponse:
    """Add product to persistent cart and return drawer partial."""
    product_id = int(request.POST.get("product_id", 0))
    quantity = int(request.POST.get("quantity", 1))
    variant_id_raw = request.POST.get("variant_id")
    variant_id = int(variant_id_raw) if variant_id_raw else None

    product, variant = get_product_for_cart_add(product_id=product_id, variant_id=variant_id)
    if product is None:
        raise Http404("Product not found.")

    gift_selections = None
    if raw := request.POST.get("gift_selections"):
        gift_selections = json.loads(raw)

    cart = get_or_create_cart(request=request)
    add_to_cart(
        cart=cart,
        product=product,
        variant=variant,
        quantity=quantity,
        gift_selections=gift_selections,
    )
    return _cart_drawer_response(
        request,
        hx_triggers={"cartItemAdded": None},
    )


@require_POST
def cart_remove_view(request: HttpRequest) -> HttpResponse:
    """Remove a cart line and return drawer partial."""
    cart = get_cart_for_request(request=request)
    if cart:
        remove_cart_item(cart=cart, cart_item_id=int(request.POST.get("cart_item_id", 0)))
    return _cart_drawer_response(request, hx_triggers={"cartUpdated": None})


@require_POST
def wishlist_toggle_view(request: HttpRequest) -> HttpResponse:
    """Toggle wishlist item; redirect back."""
    product_id = int(request.POST.get("product_id", 0))
    toggle_wishlist(request=request, product_id=product_id)
    return redirect(request.META.get("HTTP_REFERER", "/"))
