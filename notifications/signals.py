"""Cross-app signal handlers for the notifications app (side effects only)."""

from __future__ import annotations

from django.dispatch import receiver

from accounts.signals import gift_reminder_due
from notifications.tasks import (
    dispatch_gift_reminder_notification,
    dispatch_order_status_notification,
)
from orders.signals import order_status_changed


@receiver(order_status_changed)
def send_order_status_notification(
    sender,
    *,
    order,
    old_status: str,
    new_status: str,
    **kwargs,
) -> None:
    """
    Listen for order status changes and dispatch async notifications.

    Orders app never imports notifications — this receiver keeps the boundary.
    """
    dispatch_order_status_notification.delay(
        order_id=order.pk,
        old_status=old_status,
        new_status=new_status,
    )


@receiver(gift_reminder_due)
def send_gift_reminder_notification(
    sender,
    *,
    reminder,
    customer_profile,
    **kwargs,
) -> None:
    """Listen for due gift reminders and dispatch async notifications."""
    dispatch_gift_reminder_notification.delay(reminder_id=reminder.pk)
