"""Write operations and business rules for the orders app."""

from __future__ import annotations

import uuid
from typing import Optional

from django.contrib.auth.models import User
from django.db import transaction

from orders.exceptions import InvalidOrderStatusTransitionError
from orders.models import Order, OrderStatus, OrderStatusHistory
from orders.signals import order_status_changed

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.RECEIVED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.PACKAGING, OrderStatus.CANCELLED},
    OrderStatus.PACKAGING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
}


def merge_past_guest_orders(*, user) -> None:
    """
    Merge past unassigned guest orders that match the newly-logged-in user's email,
    and auto-fill missing profile details from the most recent guest order.
    """
    if not hasattr(user, "customer_profile") or not user.email:
        return
    
    #auto-fill missing user details from the most recent guest order
    all_guest_orders = Order.objects.filter(
        delivery_address_snapshot__guest_email=user.email
    )
    
    most_recent_order = all_guest_orders.order_by("-created_at").first()
    if most_recent_order:
        snapshot = most_recent_order.delivery_address_snapshot
        guest_name = snapshot.get("guest_name", "").strip()
        guest_phone = snapshot.get("guest_phone", "").strip()

        needs_user_save = False
        needs_profile_save = False

        if guest_name and not (user.first_name or user.last_name):
            parts = guest_name.split(" ", 1)
            user.first_name = parts[0][:150]
            if len(parts) > 1:
                user.last_name = parts[1][:150]
            needs_user_save = True
        
        if guest_phone and not user.customer_profile.phone:
            user.customer_profile.phone = guest_phone[:20]
            needs_profile_save = True

        if needs_user_save:
            user.save(update_fields=["first_name", "last_name"])
        if needs_profile_save:
            user.customer_profile.save(update_fields=["phone"])

    Order.objects.filter(
        customer_profile__isnull=True,
        delivery_address_snapshot__guest_email=user.email
    ).update(customer_profile=user.customer_profile)



def generate_order_number() -> str:
    """Return a unique human-readable order number."""
    return f"FLW-{uuid.uuid4().hex[:12].upper()}"


@transaction.atomic
def transition_order_status(
    *,
    order: Order,
    new_status: str,
    actor: Optional[User] = None,
    note: str = "",
    force: bool = False,
) -> Order:
    """
    Validate and apply an order status transition.

    Writes ``OrderStatusHistory`` atomically and emits ``order_status_changed``.
    Notifications listen to the signal — this service never calls them directly.
    """
    old_status = order.order_status
    if new_status == old_status:
        return order

    allowed = ALLOWED_STATUS_TRANSITIONS.get(old_status, set())
    if new_status not in allowed and not force:
        raise InvalidOrderStatusTransitionError(
            f"Cannot transition order from {old_status} to {new_status}."
        )

    order.order_status = new_status
    order.save(update_fields=["order_status", "updated_at"])

    OrderStatusHistory.objects.create(
        order=order,
        from_status=old_status,
        to_status=new_status,
        changed_by=actor,
        note=note,
    )

    order_status_changed.send(
        sender=Order,
        order=order,
        old_status=old_status,
        new_status=new_status,
    )
    return order
