"""Read-only query functions for the cart app; views must not call the ORM directly."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from django.db.models import Sum
from django.http import HttpRequest

from cart.models import Cart, CartItem
from delivery.selectors import get_delivery_charge
from gifting.selectors import get_gift_customization_snapshot

_CART_CACHE_ATTR = "_floward_resolved_cart"


def get_cart_for_request(*, request: HttpRequest) -> Optional[Cart]:
    """
    Resolve the persistent cart for the current request (guest or authenticated).

    Query guarantee: at most 1 SELECT on cart_cart per request (request-scoped cache).
    """
    if hasattr(request, _CART_CACHE_ATTR):
        return getattr(request, _CART_CACHE_ATTR)

    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key

    cart = None
    if request.user.is_authenticated and hasattr(request.user, "customer_profile"):
        cart = (
            Cart.objects.filter(customer_profile=request.user.customer_profile)
            .select_related("currency", "destination_city")
            .first()
        )

    if cart is None:
        cart = (
            Cart.objects.filter(session_key=session_key)
            .select_related("currency", "destination_city")
            .first()
        )

    setattr(request, _CART_CACHE_ATTR, cart)
    return cart


@dataclass
class CartSummaryLine:
    """Hydrated cart line for templates and checkout."""

    item: CartItem
    product: Any
    variant: Any
    quantity: int
    unit_price_at_add: Decimal
    gift_snapshot: Any
    line_subtotal: Decimal
    gift_customization_delta: Decimal


@dataclass
class CartSummary:
    """Computed cart totals — single selector call, no N+1."""

    cart: Cart
    lines: list[CartSummaryLine] = field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    coupon_code: str = ""
    coupon_discount: Decimal = Decimal("0.00")
    delivery_charge: Decimal = Decimal("0.00")
    grand_total: Decimal = Decimal("0.00")
    item_count: int = 0


def get_cart_by_id(*, cart_id: int) -> Optional[Cart]:
    """
    Return a cart by primary key.

    Query guarantee: exactly 1 SELECT on cart_cart.
    """
    return Cart.objects.filter(pk=cart_id).select_related("currency", "destination_city").first()


def get_cart_item_count(*, cart: Cart | None) -> int:
    """
    Return total item quantity for a cart without hydrating line items.

    Query guarantee: exactly 1 aggregate SELECT on cart_cartitem (0 rows → 0).
    """
    if cart is None:
        return 0
    total = CartItem.objects.filter(cart=cart).aggregate(total=Sum("quantity"))["total"]
    return int(total or 0)


def get_cart_count(*, request: HttpRequest) -> int:
    """
    Return total item quantity in the persistent cart.

    Query guarantee: 0–1 SELECT (cart lookup) + 0–1 aggregate on cart items.
    """
    cart = get_cart_for_request(request=request)
    return get_cart_item_count(cart=cart)


def get_wishlist_count(*, request: HttpRequest) -> int:
    """Return wishlist item count from session."""
    return len(request.session.get("wishlist_ids", []))


def get_cart_summary(*, cart: Cart) -> CartSummary:
    """
    Return a fully computed cart summary for drawer, checkout, and payment.

    Query guarantee:
      1) cart items SELECT with select_related(product, variant, category, brand)
      2) one gifting.get_gift_customization_snapshot call per customized line
         (each is a constant 1 SELECT + prefetches inside gifting — no cart ORM
         into gifting tables)

    Cross-app boundary: gift snapshot hydration is delegated exclusively to
    ``gifting.selectors.get_gift_customization_snapshot``.
    """
    items = list(
        CartItem.objects.filter(cart=cart)
        .select_related(
            "product",
            "product__category",
            "product__brand",
            "variant",
        )
        .order_by("id")
    )

    lines: list[CartSummaryLine] = []
    subtotal = Decimal("0.00")
    item_count = 0

    for item in items:
        gift_snapshot = get_gift_customization_snapshot(line_item_reference=item)
        gift_delta = Decimal("0.00")
        if gift_snapshot and gift_snapshot.snapshot_json:
            gift_delta = Decimal(
                gift_snapshot.snapshot_json.get("pricing", {}).get("total_delta", "0.00")
            )
        line_base = item.unit_price_at_add * item.quantity
        line_subtotal = line_base + gift_delta * item.quantity
        subtotal += line_subtotal
        item_count += item.quantity
        lines.append(
            CartSummaryLine(
                item=item,
                product=item.product,
                variant=item.variant,
                quantity=item.quantity,
                unit_price_at_add=item.unit_price_at_add,
                gift_snapshot=gift_snapshot,
                line_subtotal=line_subtotal,
                gift_customization_delta=gift_delta,
            )
        )

    delivery_charge = cart.delivery_charge
    if cart.destination_city_id and delivery_charge == Decimal("0.00"):
        delivery_charge = get_delivery_charge(
            item_count=item_count,
            destination_city=cart.destination_city,
        )

    coupon_discount = cart.coupon_discount or Decimal("0.00")
    grand_total = max(subtotal - coupon_discount + delivery_charge, Decimal("0.00"))

    return CartSummary(
        cart=cart,
        lines=lines,
        subtotal=subtotal,
        coupon_code=cart.coupon_code,
        coupon_discount=coupon_discount,
        delivery_charge=delivery_charge,
        grand_total=grand_total,
        item_count=item_count,
    )
