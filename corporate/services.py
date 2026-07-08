"""Write operations and business rules for the corporate app."""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Any, Optional, Union

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from accounts.models import CorporateAccount, CorporateApprovalStatus
from accounts.services import ensure_customer_profile_for_user
from cart.models import Cart, CartItem
from checkout.services import create_checkout_session, place_order, update_checkout_session
from core.selectors import get_default_currency
from corporate.exceptions import CorporateOrderError
from corporate.models import (
    CorporateInvoice,
    CorporateOrder,
    CorporateOrderItem,
    CorporateQuoteStatus,
)
from notifications.services import create_notification
from orders.models import Order
from recurring.models import RecurrenceStatus, RecurringSchedule


@transaction.atomic
def request_corporate_quote(
    *,
    corporate_account: CorporateAccount,
    items: list[dict[str, Any]],
    notes: str = "",
    is_recurring: bool = False,
    frequency: Optional[str] = None,
    next_run_date: Optional[Union[date_type, str]] = None,
    created_by: Optional[User] = None,
) -> CorporateOrder:
    """
    Create a corporate order in REQUESTED status and notify admins.

    Each item dict: product_id, variant_id (optional), quantity, unit_price.
    """
    if corporate_account.approval_status != CorporateApprovalStatus.APPROVED:
        raise CorporateOrderError("Corporate account is not approved.")

    corporate_order = CorporateOrder.objects.create(
        corporate_account=corporate_account,
        is_recurring=is_recurring,
        quote_status=CorporateQuoteStatus.REQUESTED,
        notes=notes,
    )
    for row in items:
        CorporateOrderItem.objects.create(
            corporate_order=corporate_order,
            product_id=row["product_id"],
            variant_id=row.get("variant_id"),
            quantity=row["quantity"],
            unit_price=Decimal(str(row["unit_price"])),
        )

    if is_recurring and frequency and next_run_date:
        run_date = (
            date_type.fromisoformat(next_run_date)
            if isinstance(next_run_date, str)
            else next_run_date
        )
        schedule = RecurringSchedule.objects.create(
            content_object=corporate_order,
            frequency=frequency,
            next_run_date=run_date,
            status=RecurrenceStatus.ACTIVE,
            created_by=created_by,
        )
        corporate_order.recurring_schedule = schedule
        corporate_order.save(update_fields=["recurring_schedule", "updated_at"])

    _notify_admins_quote_requested(corporate_order=corporate_order)
    return corporate_order


def _notify_admins_quote_requested(*, corporate_order: CorporateOrder) -> None:
    admins = User.objects.filter(groups__name="SuperAdmin").distinct()
    title = f"Corporate quote requested — {corporate_order.corporate_account.company_name}"
    body = f"Corporate order #{corporate_order.pk} awaits review."
    for admin in admins:
        create_notification(user=admin, title=title, body=body)


@transaction.atomic
def approve_and_convert_to_order(*, corporate_order: CorporateOrder) -> Order:
    """
    Convert an approved corporate order into a retail Order via place_order.

    Reuses checkout.services.place_order — no duplicated order-creation logic.
    """
    if corporate_order.quote_status not in {
        CorporateQuoteStatus.APPROVED,
        CorporateQuoteStatus.ORDERED,
    }:
        raise CorporateOrderError("Corporate order must be approved before conversion.")

    if (
        corporate_order.retail_order_id
        and corporate_order.quote_status == CorporateQuoteStatus.ORDERED
    ):
        return corporate_order.retail_order

    profile = ensure_customer_profile_for_user(user=corporate_order.corporate_account.user)
    currency = get_default_currency()
    if currency is None:
        raise CorporateOrderError("No default currency configured.")

    cart = Cart.objects.create(customer_profile=profile, currency=currency)
    for item in corporate_order.items.select_related("product", "variant"):
        CartItem.objects.create(
            cart=cart,
            product=item.product,
            variant=item.variant,
            quantity=item.quantity,
            unit_price_at_add=item.unit_price,
        )

    session = create_checkout_session(cart=cart, customer_profile=profile)
    if profile.default_address_id:
        update_checkout_session(checkout_session=session, address=profile.default_address)

    idempotency_key = f"corporate-{corporate_order.pk}"
    order = place_order(
        checkout_session_id=session.pk,
        idempotency_key=idempotency_key,
        customer_profile=profile,
    )

    corporate_order.retail_order = order
    corporate_order.quote_status = CorporateQuoteStatus.ORDERED
    corporate_order.save(update_fields=["retail_order", "quote_status", "updated_at"])
    return order


@transaction.atomic
def execute_corporate_order_recurrence(*, schedule: RecurringSchedule) -> Order:
    """Recurrence handler for corporate order templates."""
    corporate_order = schedule.content_object
    if not isinstance(corporate_order, CorporateOrder):
        raise CorporateOrderError("Schedule does not point to a corporate order.")
    idempotency_key = f"recurring-corp-{schedule.pk}-{schedule.next_run_date}"
    profile = ensure_customer_profile_for_user(user=corporate_order.corporate_account.user)
    currency = get_default_currency()
    cart = Cart.objects.create(customer_profile=profile, currency=currency)
    for item in corporate_order.items.select_related("product", "variant"):
        CartItem.objects.create(
            cart=cart,
            product=item.product,
            variant=item.variant,
            quantity=item.quantity,
            unit_price_at_add=item.unit_price,
        )
    session = create_checkout_session(cart=cart, customer_profile=profile)
    if profile.default_address_id:
        update_checkout_session(checkout_session=session, address=profile.default_address)
    return place_order(
        checkout_session_id=session.pk,
        idempotency_key=idempotency_key,
        customer_profile=profile,
    )


@transaction.atomic
def generate_corporate_invoice(
    *,
    corporate_order: CorporateOrder,
    pdf_url: str,
) -> CorporateInvoice:
    """Record a generated invoice PDF for a corporate order."""
    return CorporateInvoice.objects.create(
        corporate_order=corporate_order,
        pdf_url=pdf_url,
        generated_at=timezone.now(),
    )
