"""Payment gateway registry — checkout selects by string key only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from payments.adapters.concrete import (
    ApplePayAdapter,
    CardGatewayAdapter,
    CashOnDeliveryAdapter,
    GiftVoucherAdapter,
    GooglePayAdapter,
    QatarLocalGatewayAdapter,
)
from payments.adapters.paytabs import PayTabsGatewayAdapter

if TYPE_CHECKING:
    from payments.adapters.base import PaymentGatewayAdapter

PAYMENT_GATEWAYS: dict[str, PaymentGatewayAdapter] = {
    CardGatewayAdapter.key: CardGatewayAdapter(),
    QatarLocalGatewayAdapter.key: QatarLocalGatewayAdapter(),
    ApplePayAdapter.key: ApplePayAdapter(),
    GooglePayAdapter.key: GooglePayAdapter(),
    GiftVoucherAdapter.key: GiftVoucherAdapter(),
    CashOnDeliveryAdapter.key: CashOnDeliveryAdapter(),
    PayTabsGatewayAdapter.key: PayTabsGatewayAdapter(),
}

STOREFRONT_BADGE_LABELS: dict[str, str] = {
    "visa": "Visa",
    "mastercard": "Mastercard",
    "amex": "American Express",
    "apple_pay": "Apple Pay",
    "google_pay": "Google Pay",
    "qatar_local": "Qatar Local",
}


def get_payment_adapter(*, gateway_key: str) -> PaymentGatewayAdapter:
    """Look up a registered adapter by key."""
    adapter = PAYMENT_GATEWAYS.get(gateway_key)
    if adapter is None:
        raise KeyError(f"Unknown payment gateway: {gateway_key}")
    return adapter


def register_payment_adapter(*, adapter: PaymentGatewayAdapter) -> None:
    """
    Register an adapter at runtime (used by tests and future plugins).

    Adding a gateway requires only registry registration — zero checkout view edits.
    """
    PAYMENT_GATEWAYS[adapter.key] = adapter


def get_storefront_payment_badges() -> list[dict[str, str]]:
    """Return ordered unique payment badges for PDP / trust UI."""
    badges: list[dict[str, str]] = []
    seen: set[str] = set()
    for adapter in PAYMENT_GATEWAYS.values():
        if not getattr(adapter, "show_on_storefront", False):
            continue
        for badge_key in getattr(adapter, "badge_keys", ()):
            if badge_key in seen:
                continue
            seen.add(badge_key)
            badges.append(
                {
                    "key": badge_key,
                    "label": STOREFRONT_BADGE_LABELS.get(badge_key, badge_key.replace("_", " ").title()),
                }
            )
    return badges
