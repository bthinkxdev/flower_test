"""
Reconcile PayTabs transactions left PENDING by a missed or delayed IPN callback.

"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from payments.adapters.paytabs import PayTabsGatewayAdapter
from payments.exceptions import PaymentGatewayError
from payments.models import PaymentStatus, PaymentTransaction
from payments.services import confirm_payment_failed, confirm_payment_success

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reconcile PayTabs PaymentTransactions stuck PENDING via PayTabs' Query Transaction API."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--older-than-minutes",
            type=int,
            default=10,
            help="Only reconcile PENDING transactions created at least this long ago.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Maximum number of transactions to check in one run.",
        )

    def handle(self, *args, older_than_minutes: int, limit: int, **options) -> None:
        cutoff = timezone.now() - timedelta(minutes=older_than_minutes)
        stale_pending = PaymentTransaction.objects.filter(
            gateway_key=PayTabsGatewayAdapter.key,
            status=PaymentStatus.PENDING,
            created_at__lte=cutoff,
        ).order_by("created_at")[:limit]

        adapter = PayTabsGatewayAdapter()
        resolved = 0
        still_pending = 0
        errors = 0

        for payment_tx in stale_pending:
            try:
                capture = adapter.capture(intent_id=payment_tx.external_intent_id)
            except PaymentGatewayError:
                logger.exception(
                    "reconcile_paytabs_charges.gateway_error",
                    extra={"payment_transaction_id": payment_tx.pk},
                )
                errors += 1
                continue

            raw_status = capture.metadata.get("raw_status", "")
            if capture.success:
                payment_tx.external_transaction_id = capture.transaction_id
                payment_tx.save(update_fields=["external_transaction_id", "updated_at"])
                confirm_payment_success(payment_transaction=payment_tx)
                resolved += 1
            elif raw_status in {"H", "P"}:
                still_pending += 1
            else:
                confirm_payment_failed(payment_transaction=payment_tx)
                resolved += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciled {resolved}, still pending {still_pending}, "
                f"errors {errors} (checked {len(stale_pending)})."
            )
        )
