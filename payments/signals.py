"""Cross-app signal handlers for the payments app (side effects only)."""

from __future__ import annotations

from django.dispatch import receiver

from orders.models import OrderStatus
from orders.signals import order_status_changed
from payments.adapters.concrete import CashOnDeliveryAdapter
from payments.models import PaymentStatus, PaymentTransaction
from payments.services import confirm_payment_failed, confirm_payment_success


@receiver(order_status_changed)
def sync_cod_payment_with_order_status(
    sender,
    *,
    order,
    old_status: str,
    new_status: str,
    **kwargs,
) -> None:
    """
    Keep a COD PaymentTransaction in sync with the order lifecycle.

    COD has no webhook, so the order status itself is the only real-world
    signal about the money:
      - DELIVERED  -> cash was collected on handover  -> SUCCESS
      - CANCELLED  -> order never fulfilled, no cash collected -> FAILED

    Only touches transactions still PENDING, so an already-resolved COD
    transaction (e.g. SUCCESS after delivery) is never re-processed if a
    later, unrelated transition fires this same signal again.
    """
    if new_status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        return

    payment_tx = PaymentTransaction.objects.filter(
        order=order,
        gateway_key=CashOnDeliveryAdapter.key,
        status=PaymentStatus.PENDING,
    ).first()
    if payment_tx is None:
        return

    if new_status == OrderStatus.DELIVERED:
        confirm_payment_success(payment_transaction=payment_tx)
    else:
        confirm_payment_failed(payment_transaction=payment_tx)