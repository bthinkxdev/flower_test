"""Payment gateway registry — checkout selects by string key only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from payments.adapters.concrete import CashOnDeliveryAdapter, FawranAdapter

# Other adapters (card, apple_pay, google_pay, gift_voucher, qatar_local,
# paytabs) still live in payments/adapters/ but are intentionally left out
# of checkout — currently only Fawran and Cash on Delivery are offered.
# Re-register them here to bring one back.

if TYPE_CHECKING:
    from payments.adapters.base import PaymentGatewayAdapter

PAYMENT_GATEWAYS: dict[str, PaymentGatewayAdapter] = {
    FawranAdapter.key: FawranAdapter(),
    CashOnDeliveryAdapter.key: CashOnDeliveryAdapter(),
}

STOREFRONT_BADGE_LABELS: dict[str, str] = {
    "visa": "Visa",
    "mastercard": "Mastercard",
    "amex": "American Express",
    "apple_pay": "Apple Pay",
    "google_pay": "Google Pay",
    "qatar_local": "Qatar Local",
    "fawran": "Fawran",
    "cod": "Cash on Delivery",
    "naps_qpay": "NAPS / QPAY",
    "qr_payments": "QR Payments",
    "cb_paylink": "CB PayLink",
    "qmp": "QMP",
    "cb_vpos": "CB VPOS",
}

# Trust badges shown on the PDP "Ways to pay" strip only — these Qatar payment
# network/switch brands aren't selectable checkout gateways (no adapter backs
# them), so they can't come from PAYMENT_GATEWAYS like the rest of the badges.
STOREFRONT_ONLY_BADGE_KEYS: tuple[str, ...] = (
    "visa",
    "mastercard",
    "apple_pay",
    "google_pay",
    "naps_qpay",
    "qr_payments",
    "cb_paylink",
    "qmp",
    "cb_vpos",
)


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

    def _add(badge_key: str) -> None:
        if badge_key in seen:
            return
        seen.add(badge_key)
        badges.append(
            {
                "key": badge_key,
                "label": STOREFRONT_BADGE_LABELS.get(badge_key, badge_key.replace("_", " ").title()),
            }
        )

    for adapter in PAYMENT_GATEWAYS.values():
        if not getattr(adapter, "show_on_storefront", False):
            continue
        for badge_key in getattr(adapter, "badge_keys", ()):
            _add(badge_key)

    for badge_key in STOREFRONT_ONLY_BADGE_KEYS:
        _add(badge_key)

    return badges
