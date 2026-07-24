"""Write operations and business rules for the cart app."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.http import HttpRequest

from cart.exceptions import CartItemNotFoundError
from cart.models import Cart, CartItem
from cart.selectors import get_cart_for_request, get_cart_summary
from catalog.models import Product, ProductVariant
from catalog.selectors import get_variant_price
from core.selectors import get_default_currency
from delivery.models import City
from delivery.selectors import get_delivery_charge
from gifting.services import build_gift_customization_snapshot
from marketing.services import validate_coupon_for_cart
from cart.exceptions import OutOfStockError

def _resolve_unit_price(*, product: Product, variant: Optional[ProductVariant]) -> Decimal:
    """Compute snapshotted unit price from catalog selector."""
    price_data = get_variant_price(
        product_id=product.pk,
        variant_id=variant.pk if variant else None,
    )
    return Decimal(price_data["price"])


@transaction.atomic
def get_or_create_cart(*, request: HttpRequest) -> Cart:
    """
    Return the persistent cart for the request, creating one when missing.

    Authenticated customers receive a profile-linked cart; guests use session_key.
    """
    if not request.session.session_key:
        request.session.create()

    existing = get_cart_for_request(request=request)
    if existing:
        return existing

    currency = get_default_currency()
    if currency is None:
        raise RuntimeError("No default currency configured.")

    if request.user.is_authenticated and hasattr(request.user, "customer_profile"):
        return Cart.objects.create(
            customer_profile=request.user.customer_profile,
            currency=currency,
        )
    return Cart.objects.create(
        session_key=request.session.session_key,
        currency=currency,
    )


@transaction.atomic
def add_to_cart(
    *,
    cart: Cart,
    product: Product,
    variant: Optional[ProductVariant] = None,
    quantity: int = 1,
    gift_selections: Optional[dict[str, Any]] = None,
) -> CartItem:
    """
    Add or increment a cart line, optionally building a gift snapshot first.

    Gift-customized adds ALWAYS create a brand-new line — two personalized
    gifts for the same product/variant (different recipient, message, card,
    etc.) must never collapse into one and silently overwrite each other.
    Only plain (non-gift) adds of the same product/variant merge by quantity,
    matching the conditional unique constraint on CartItem.
    """
    available = variant.stock_quantity if variant else product.stock_quantity
    already_in_cart = CartItem.objects.filter(cart=cart, product=product, variant=variant).values_list(
        "quantity", flat=True
    ).first() or 0
    if available <= 0 or (already_in_cart + quantity) > available:
        raise OutOfStockError(f"Only {available} unit(s) of '{product.name}' available.")

    unit_price = _resolve_unit_price(product=product, variant=variant)

    if gift_selections:
        item = CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=quantity,
            unit_price_at_add=unit_price,
        )
        snapshot = build_gift_customization_snapshot(
            product_instance=product,
            selections=gift_selections,
            line_item_reference=item,
        )
        item.gift_customization_snapshot = snapshot
        item.save(update_fields=["gift_customization_snapshot", "updated_at"])
        return item

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        variant=variant,
        gift_customization_snapshot__isnull=True,
        defaults={
            "quantity": quantity,
            "unit_price_at_add": unit_price,
        },
    )
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity", "updated_at"])
    return item


@transaction.atomic
def remove_cart_item(*, cart: Cart, cart_item_id: int) -> None:
    """Remove a line item from the cart."""
    CartItem.objects.filter(cart=cart, pk=cart_item_id).delete()

@transaction.atomic
def adjust_cart_item_quantity(
    *,
    cart: Cart,
    cart_item_id: int,
    delta: int,
) -> Optional[CartItem]:
    """
    Increment or decrement a cart line's quantity by ``delta``.

    Row-locked (``select_for_update``) so rapid +/- clicks never race each
    other into a lost update. Quantity dropping to zero or below deletes the
    line instead of persisting a non-positive quantity.

    Raises:
        CartItemNotFoundError: When no matching line exists on this cart.
        OutOfStockError: When incrementing would exceed real available stock.
    """
    item = (
        CartItem.objects.select_for_update()
        .select_related("product", "variant")
        .filter(cart=cart, pk=cart_item_id)
        .first()
    )
    if item is None:
        raise CartItemNotFoundError("Cart item not found.")

    new_quantity = item.quantity + delta
    if new_quantity < 1:
        item.delete()
        return None

    if delta > 0:
        available = item.variant.stock_quantity if item.variant else item.product.stock_quantity
        if new_quantity > available:
            raise OutOfStockError(
                f"Only {available} unit(s) of '{item.product.name}' available."
            )

    item.quantity = new_quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item

@transaction.atomic
def apply_coupon(*, cart: Cart, code: str) -> Cart:
    """
    Validate and apply a coupon via the marketing service boundary.

    Raises:
        InvalidCouponError: Propagated from marketing.services.
    """
    summary = get_cart_summary(cart=cart)
    category_ids = [line.product.category_id for line in summary.lines]
    result = validate_coupon_for_cart(
        code=code,
        cart_subtotal=summary.subtotal,
        customer_profile_id=cart.customer_profile_id,
        cart_category_ids=category_ids,
    )
    cart.coupon_code = result["code"]
    cart.coupon_discount = result["discount_amount"]
    cart.save(update_fields=["coupon_code", "coupon_discount", "updated_at"])
    return cart

@transaction.atomic
def remove_coupon(*, cart: Cart) -> Cart:
    """Clear any applied coupon from the cart."""
    cart.coupon_code = ""
    cart.coupon_discount = Decimal("0.00")
    cart.save(update_fields=["coupon_code", "coupon_discount", "updated_at"])
    return cart

@transaction.atomic
def recalculate_delivery_charge(*, cart: Cart, destination_city: City) -> Cart:
    """Persist delivery charge for a destination city via delivery selector."""
    summary = get_cart_summary(cart=cart)
    charge = get_delivery_charge(
        item_count=summary.item_count,
        destination_city=destination_city,
    )
    cart.destination_city = destination_city
    cart.delivery_charge = charge
    cart.save(update_fields=["destination_city", "delivery_charge", "updated_at"])
    return cart

def preview_delivery_charge(*, cart: Cart, destination_city: City) -> Decimal:
    """Quote delivery charge for a city WITHOUT persisting to the cart.
    Read-only counterpart to recalculate_delivery_charge — used for
    instant on-change previews before the customer commits an address."""
    summary = get_cart_summary(cart=cart)
    return get_delivery_charge(item_count=summary.item_count, destination_city=destination_city)

@transaction.atomic
def merge_carts(*, user, old_session_key: str) -> Optional[Cart]:
    """
    Merge a guest session cart into the newly-logged-in customer's cart.

    Must be called with the session key captured *before* django.contrib.auth.login()
    — login() rotates the session key, so after that point the guest cart's
    session_key can no longer be found via request.session.session_key.

    - Non-gift lines merge by summed quantity, capped to available stock (same
      invariant add_to_cart enforces — never silently exceed real stock).
    - Gift-customized lines never merge into an existing line, mirroring
      add_to_cart's "always a new line" rule for personalized items.
    - If the customer has no existing cart yet, the guest cart is reassigned
      wholesale (cheap path — no per-line work needed).
    """
    if not old_session_key or not hasattr(user, "customer_profile"):
        return None

    guest_cart = Cart.objects.select_for_update().filter(session_key=old_session_key).first()
    if guest_cart is None:
        return None

    profile = user.customer_profile
    user_cart = Cart.objects.select_for_update().filter(customer_profile=profile).first()

    if user_cart is None:
        guest_cart.customer_profile = profile
        guest_cart.session_key = None
        guest_cart.save(update_fields=["customer_profile", "session_key", "updated_at"])
        return guest_cart

    guest_items = list(CartItem.objects.filter(cart=guest_cart).select_related("product", "variant"))
    for guest_item in guest_items:
        if guest_item.gift_customization_snapshot_id:
            guest_item.cart = user_cart
            guest_item.save(update_fields=["cart", "updated_at"])
            continue

        existing = CartItem.objects.filter(
            cart=user_cart,
            product=guest_item.product,
            variant=guest_item.variant,
            gift_customization_snapshot__isnull=True,
        ).first()

        target = guest_item.variant if guest_item.variant else guest_item.product
        available = target.stock_quantity

        if existing is None:
            new_quantity = min(guest_item.quantity, available)
            if new_quantity < 1:
                guest_item.delete()
                continue
            guest_item.cart = user_cart
            guest_item.quantity = new_quantity
            guest_item.save(update_fields=["cart", "quantity", "updated_at"])
            continue

        combined_quantity = min(existing.quantity + guest_item.quantity, available)
        if combined_quantity < 1:
            existing.delete()
        else:
            existing.quantity = combined_quantity
            existing.save(update_fields=["quantity", "updated_at"])
        guest_item.delete()

    if guest_cart.destination_city_id and not user_cart.destination_city_id:
        recalculate_delivery_charge(cart=user_cart, destination_city=guest_cart.destination_city)

    guest_cart.delete()
    return user_cart

def toggle_wishlist(*, request: HttpRequest, product_id: int) -> bool:
    """
    Toggle a product in the persistent wishlist (DB-backed, guest or authenticated).

    Returns:
        True if product is now in wishlist, False if removed.
    """
    from accounts.subscription_services import (
        add_to_wishlist,
        get_or_create_wishlist,
        remove_from_wishlist,
    )
    from accounts.models import WishlistItem

    wishlist = get_or_create_wishlist(request=request)
    exists = WishlistItem.objects.filter(wishlist=wishlist, product_id=product_id).exists()
    if exists:
        remove_from_wishlist(wishlist=wishlist, product_id=product_id)
        return False
    add_to_wishlist(wishlist=wishlist, product_id=product_id)
    return True
