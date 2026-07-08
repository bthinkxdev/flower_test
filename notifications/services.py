"""Write operations and business rules for the notifications app."""

from __future__ import annotations

import logging

from django.contrib.auth.models import User

from notifications.models import Notification

logger = logging.getLogger(__name__)


def send_sms(*, phone: str, message: str) -> None:
    """Dispatch an SMS — provider-agnostic stub that logs the payload."""
    logger.info("SMS to %s: %s", phone, message)


def send_email(*, email: str, subject: str, message: str) -> None:
    """Dispatch an email — provider-agnostic stub that logs the payload."""
    logger.info("Email to %s [%s]: %s", email, subject, message)


def send_whatsapp(*, phone: str, message: str) -> None:
    """Dispatch a WhatsApp message — provider-agnostic stub that logs the payload."""
    logger.info("WhatsApp to %s: %s", phone, message)


def create_notification(*, user: User, title: str, body: str = "") -> Notification:
    """
    Persist an in-app notification for a user.

    Params:
        user: Recipient Django User.
        title: Notification headline.
        body: Optional full message body.
    Returns:
        Created Notification instance.
    """
    return Notification.objects.create(user=user, title=title, body=body)
