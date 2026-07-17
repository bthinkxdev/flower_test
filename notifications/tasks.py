"""Celery tasks for the notifications app."""

from __future__ import annotations

from celery import shared_task

from notifications.services import create_notification, send_email, send_sms, send_whatsapp

import logging
logger = logging.getLogger(__name__)


@shared_task(name="notifications.tasks.dispatch_sms")
def dispatch_sms(*, phone: str, message: str) -> None:
    """Async Celery wrapper around the send_sms service function."""
    send_sms(phone=phone, message=message)


@shared_task(name="notifications.tasks.dispatch_order_status_notification")
def dispatch_order_status_notification(
    *,
    order_id: int,
    old_status: str,
    new_status: str,
) -> None:
    """
    Send order status updates on the customer's preferred channels.

    Chooses email, SMS, and/or WhatsApp based on CustomerProfile preferences.
    """
    from orders.models import Order

    order = (
        Order.objects.select_related("customer_profile", "customer_profile__user")
        .filter(pk=order_id)
        .first()
    )
    if order is None or order.customer_profile is None:
        return

    profile = order.customer_profile
    user = profile.user
    title = f"Order {order.order_number} update"
    body = f"Your order status changed from {old_status} to {new_status}."

    create_notification(user=user, title=title, body=body)

    if profile.notify_via_email and user.email:
        send_email(email=user.email, subject=title, message=body)

    if profile.phone:
        if profile.notify_via_sms:
            send_sms(phone=profile.phone, message=body)
        if profile.notify_via_whatsapp:
            send_whatsapp(phone=profile.phone, message=body)


@shared_task(name="notifications.tasks.dispatch_gift_reminder_notification")
def dispatch_gift_reminder_notification(*, reminder_id: int) -> None:
    """Send gift reminder notifications on preferred channels."""
    from accounts.models import GiftReminder

    reminder = (
        GiftReminder.objects.select_related("customer_profile", "customer_profile__user")
        .filter(pk=reminder_id)
        .first()
    )
    if reminder is None:
        return

    profile = reminder.customer_profile
    user = profile.user
    title = f"Gift reminder: {reminder.recipient_name}"
    body = (
        f"{reminder.get_occasion_type_display()} for {reminder.recipient_name} "
        f"on {reminder.reminder_date}. {reminder.notes}".strip()
    )

    create_notification(user=user, title=title, body=body)
    if profile.notify_via_email and user.email:
        send_email(email=user.email, subject=title, message=body)
    if profile.phone:
        if profile.notify_via_sms:
            send_sms(phone=profile.phone, message=body)
        if profile.notify_via_whatsapp:
            send_whatsapp(phone=profile.phone, message=body)


@shared_task(name="notifications.tasks.dispatch_email")
def dispatch_email(*, email: str, subject: str, message: str) -> None:
    try:
        send_email(email=email, subject=subject, message=message)
    except Exception:
        logger.exception("Failed to send email to %s", email)