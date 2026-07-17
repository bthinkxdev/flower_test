"""HTTP views for the cart app."""

from __future__ import annotations

import json

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from cart.exceptions import CartItemNotFoundError
from cart.forms import CartCouponForm, CartQuantityForm
from cart.selectors import get_cart_count, get_cart_for_request, get_cart_summary
from cart.services import (
    add_to_cart,
    adjust_cart_item_quantity,
    apply_coupon,
    get_or_create_cart,
    remove_coupon,
    remove_cart_item,
    toggle_wishlist,
)
from catalog.selectors import get_product_for_cart_add
from marketing.exceptions import InvalidCouponError
from cart.exceptions import OutOfStockError

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


def _cart_page_response(
    request: HttpRequest, *, error: str | None = None, hx_triggers: dict | None = None
) -> HttpResponse:
    """Render the standalone cart page's swappable body; optionally attach HTMX triggers."""
    cart = get_cart_for_request(request=request)
    summary = get_cart_summary(cart=cart) if cart else None
    response = render(
        request,
        "cart/partials/page_body.html",
        {
            "summary": summary,
            "cart_count": summary.item_count if summary else 0,
            "error": error,
        },
    )
    if hx_triggers:
        response["HX-Trigger"] = json.dumps(hx_triggers)
    return response


@require_GET
def cart_page_view(request: HttpRequest) -> HttpResponse:
    """Standalone cart page — full item list, coupon box, and order summary."""
    cart = get_or_create_cart(request=request)
    summary = get_cart_summary(cart=cart)
    return render(
        request,
        "cart/cart_page.html",
        {
            "summary": summary,
            "cart_count": summary.item_count,
        },
    )


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
    try:
        add_to_cart(
            cart=cart,
            product=product,
            variant=variant,
            quantity=quantity,
            gift_selections=gift_selections,
        )
    except OutOfStockError as exc:
        summary = get_cart_summary(cart=cart)
        return render(
            request,
            "cart/partials/drawer.html",
            {"summary": summary, "cart_count": summary.item_count, "stock_error": str(exc)},
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
def cart_page_remove_view(request: HttpRequest) -> HttpResponse:
    """Remove a cart line from the standalone cart page and return its body partial."""
    cart = get_cart_for_request(request=request)
    if cart:
        remove_cart_item(cart=cart, cart_item_id=int(request.POST.get("cart_item_id", 0)))
    return _cart_page_response(request, hx_triggers={"cartUpdated": None})


@require_POST
def cart_quantity_view(request: HttpRequest) -> HttpResponse:
    """Increment/decrement a cart line's quantity (+1/-1); deletes at zero."""
    form = CartQuantityForm(request.POST)
    if not form.is_valid():
        return _cart_page_response(request, error=_("Could not update quantity."))

    cart = get_cart_for_request(request=request)
    if cart is None:
        raise Http404("Cart not found.")

    try:
        adjust_cart_item_quantity(
            cart=cart,
            cart_item_id=form.cleaned_data["cart_item_id"],
            delta=form.cleaned_data["delta"],
        )
    except CartItemNotFoundError:
        return _cart_page_response(request, error=_("That item is no longer in your cart."))

    return _cart_page_response(request, hx_triggers={"cartUpdated": None})


@require_POST
def cart_coupon_apply_view(request: HttpRequest) -> HttpResponse:
    """Validate and apply a coupon code to the cart."""
    form = CartCouponForm(request.POST)
    if not form.is_valid():
        return _cart_page_response(request, error=_("Enter a coupon code."))

    cart = get_cart_for_request(request=request)
    if cart is None:
        raise Http404("Cart not found.")

    try:
        apply_coupon(cart=cart, code=form.cleaned_data["code"])
    except InvalidCouponError as exc:
        return _cart_page_response(request, error=str(exc))

    return _cart_page_response(request, hx_triggers={"cartUpdated": None})


@require_POST
def cart_coupon_remove_view(request: HttpRequest) -> HttpResponse:
    """Remove any applied coupon from the cart."""
    cart = get_cart_for_request(request=request)
    if cart:
        remove_coupon(cart=cart)
    return _cart_page_response(request, hx_triggers={"cartUpdated": None})


@require_POST
def wishlist_toggle_view(request: HttpRequest) -> HttpResponse:
    """Toggle wishlist item; redirect back."""
    product_id = int(request.POST.get("product_id", 0))
    toggle_wishlist(request=request, product_id=product_id)
    return redirect(request.META.get("HTTP_REFERER", "/"))
