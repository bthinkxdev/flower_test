"""Celery tasks for the accounts app."""

from __future__ import annotations

from celery import shared_task

from accounts.services import notify_admins_corporate_pending
from accounts.subscription_services import send_due_gift_reminders
from notifications.tasks import dispatch_email


@shared_task(name="accounts.tasks.send_otp_sms")
def send_otp_sms(*, phone: str, otp_code: str) -> None:
    """Dispatch OTP SMS via the notifications app's send_sms service."""
    from notifications.tasks import dispatch_sms

    dispatch_sms.delay(phone=phone, message=f"Your Story of Flowers verification code is: {otp_code}")


@shared_task(name="accounts.tasks.notify_corporate_registration")
def notify_corporate_registration(*, corporate_account_id: int) -> None:
    """Notify SuperAdmin users about a new pending corporate registration."""
    notify_admins_corporate_pending(corporate_account_id=corporate_account_id)


@shared_task(name="accounts.tasks.send_due_gift_reminders")
def send_due_gift_reminders_task() -> int:
    """Daily beat task for gift calendar reminders."""
    return send_due_gift_reminders()

@shared_task(name="accounts.tasks.send_otp_email")
def send_otp_email(*, email: str, otp_code: str) -> None:
    dispatch_email.delay(
        email=email,
        subject="Your Story of Flowers verification code",
        message=f"Your Story of Flowers login code is: {otp_code}. It expires shortly — do not share it.",
    )
