"""
Tap Payments (tap.company) gateway adapter.

"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from payments.adapters.base import PaymentCaptureResult, PaymentGatewayAdapter, PaymentIntentResult
from payments.exceptions import PaymentGatewayError, PaymentGatewayRejected, WebhookVerificationError

logger = logging.getLogger(__name__)

# Currencies Tap expects with 3 decimal places instead of the usual 2.
_THREE_DECIMAL_CURRENCIES = {"BHD", "KWD", "OMR"}

# Charge statuses Tap can return. Anything not in _SUCCESS_STATUSES or
# _PENDING_STATUSES is treated as a final failure.
_SUCCESS_STATUSES = {"CAPTURED"}
_PENDING_STATUSES = {"INITIATED", "IN_PROGRESS"}

_REQUEST_TIMEOUT = (5, 15)  # (connect, read) seconds


def _session() -> requests.Session:
    
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.5,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _format_amount(amount: Decimal, currency: str) -> float:

    places = Decimal("0.001") if currency.upper() in _THREE_DECIMAL_CURRENCIES else Decimal("0.01")
    quantized = amount.quantize(places, rounding=ROUND_HALF_UP)
    return float(quantized)


class TapGatewayAdapter(PaymentGatewayAdapter):

    key = "tap"
    display_name = "Tap Payments"
    is_async = True

    # -- config -----------------------------------------------------------

    @property
    def _secret_key(self) -> str:
        key = getattr(settings, "TAP_SECRET_KEY", "")
        if not key:
            raise PaymentGatewayError("TAP_SECRET_KEY is not configured.")
        return key

    @property
    def _base_url(self) -> str:
        return getattr(settings, "TAP_API_BASE_URL", "https://api.tap.company/v2")

    @property
    def _default_source_id(self) -> str:
        # "src_all" lets Tap's hosted page offer every method enabled on the
        # merchant account. Pin to "src_card" etc. to restrict to one rail.
        return getattr(settings, "TAP_DEFAULT_SOURCE_ID", "src_all")

    @property
    def _webhook_post_url(self) -> str:
        url = getattr(settings, "TAP_WEBHOOK_URL", "")
        if not url:
            raise PaymentGatewayError(
                "TAP_WEBHOOK_URL is not configured — Tap needs a publicly "
                "reachable HTTPS URL, it cannot call a localhost callback."
            )
        return url

    @property
    def _default_redirect_url(self) -> str:
        return getattr(settings, "TAP_DEFAULT_REDIRECT_URL", "")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/json",
        }

    # -- PaymentGatewayAdapter interface -----------------------------------

    def create_payment_intent(
        self,
        *,
        amount: Decimal,
        currency: str,
        metadata: dict[str, Any],
    ) -> PaymentIntentResult:
        
        order_number = str(metadata.get("order_number", ""))
        transaction_reference = f"{order_number or 'order'}-{uuid.uuid4().hex[:8]}"

        payload: dict[str, Any] = {
            "amount": _format_amount(amount, currency),
            "currency": currency.upper(),
            "customer_initiated": True,
            "threeDSecure": True,
            "save_card": False,
            "description": f"Order {order_number}".strip(),
            "metadata": {k: str(v) for k, v in metadata.items()},
            "reference": {
                "transaction": transaction_reference,
                "order": order_number,
            },
            "receipt": {"email": True, "sms": True},
            "customer": self._build_customer(metadata),
            "source": {"id": metadata.get("source_id", self._default_source_id)},
            "post": {"url": self._webhook_post_url},
            "redirect": {"url": metadata.get("merchant_return_url") or self._default_redirect_url},
        }

        data = self._post("/charges/", payload)

        charge_id = data.get("id", "")
        if not charge_id:
            raise PaymentGatewayError(f"Tap charge response missing id: {data!r}")

        transaction_url = (data.get("transaction") or {}).get("url", "")
        status = data.get("status", "")

        logger.info(
            "tap.charge.created",
            extra={"charge_id": charge_id, "order_number": order_number, "status": status},
        )

        return PaymentIntentResult(
            intent_id=charge_id,
            client_secret="",
            metadata={
                "redirect_url": transaction_url,
                "tap_status": status,
                "transaction_reference": transaction_reference,
            },
            requires_webhook=True,
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> dict[str, Any]:
        
        import json

        try:
            event = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError) as exc:
            raise WebhookVerificationError("Tap webhook payload is not valid JSON.") from exc

        posted_hash = event.get("hashstring") or signature
        if not posted_hash:
            raise WebhookVerificationError("Tap webhook payload has no hashstring to verify.")

        expected_hash = self._compute_webhook_hash(event)
        if not hmac.compare_digest(expected_hash, posted_hash):
            raise WebhookVerificationError("Tap webhook hashstring mismatch.")

        charge_id = event.get("id", "")
        status = str(event.get("status", "")).upper()

        if status in _SUCCESS_STATUSES:
            normalized_status = "success"
        elif status in _PENDING_STATUSES:
            normalized_status = "pending"
        else:
            normalized_status = "failed"

        logger.info("tap.webhook.verified", extra={"charge_id": charge_id, "status": status})

        return {
            "intent_id": charge_id,
            "transaction_id": charge_id,  # Tap has no separate settlement id
            "status": normalized_status,
            "raw_status": status,
        }

    def capture(self, *, intent_id: str) -> PaymentCaptureResult:
        
        data = self._get(f"/charges/{intent_id}")
        status = str(data.get("status", "")).upper()
        success = status in _SUCCESS_STATUSES
        return PaymentCaptureResult(
            success=success,
            transaction_id=intent_id,
            metadata={"gateway": self.key, "raw_status": status},
        )

    def refund(self, *, transaction_id: str, amount: Decimal) -> PaymentCaptureResult:
        """Full or partial refund of a captured Tap charge."""
        data = self._get(f"/charges/{transaction_id}")
        currency = data.get("currency", "")

        payload = {
            "charge_id": transaction_id,
            "amount": _format_amount(amount, currency),
            "currency": currency,
            "reason": "requested_by_customer",
        }
        result = self._post("/refunds/", payload)

        refund_status = str(result.get("status", "")).upper()
        success = refund_status in {"PENDING", "REFUNDED", "CAPTURED"}
        return PaymentCaptureResult(
            success=success,
            transaction_id=result.get("id", transaction_id),
            metadata={"gateway": self.key, "raw_status": refund_status},
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _build_customer(metadata: dict[str, Any]) -> dict[str, Any]:
        customer: dict[str, Any] = {
            "first_name": metadata.get("customer_first_name", "Guest"),
            "last_name": metadata.get("customer_last_name", "Customer"),
        }
        email = metadata.get("customer_email")
        if email:
            customer["email"] = email
        phone_number = metadata.get("customer_phone_number")
        if phone_number:
            customer["phone"] = {
                "country_code": metadata.get("customer_phone_country_code", ""),
                "number": phone_number,
            }
        return customer

    def _compute_webhook_hash(self, event: dict[str, Any]) -> str:
        
        reference = event.get("reference") or {}
        transaction = event.get("transaction") or {}

        to_be_hashed = (
            f"x_id{event.get('id', '')}"
            f"x_amount{event.get('amount', '')}"
            f"x_currency{event.get('currency', '')}"
            f"x_gateway_reference{reference.get('gateway', '')}"
            f"x_payment_reference{reference.get('payment', '')}"
            f"x_status{event.get('status', '')}"
            f"x_created{transaction.get('created', '')}"
        )
        return hmac.new(
            self._secret_key.encode(),
            to_be_hashed.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json=payload)

    def _get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            response = _session().request(
                method,
                url,
                headers=self._headers(),
                timeout=_REQUEST_TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as exc:
            logger.error("tap.request.network_error", extra={"path": path, "error": str(exc)})
            raise PaymentGatewayError(f"Network error calling Tap ({path}): {exc}") from exc

        if response.status_code >= 500:
            logger.error(
                "tap.request.server_error",
                extra={"path": path, "status_code": response.status_code},
            )
            raise PaymentGatewayError(
                f"Tap returned a server error ({response.status_code}) for {path}."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise PaymentGatewayError(f"Tap response for {path} was not JSON.") from exc

        if response.status_code >= 400:
            error_detail = data.get("errors") or data.get("message") or data
            logger.warning(
                "tap.request.rejected",
                extra={"path": path, "status_code": response.status_code, "detail": error_detail},
            )
            raise PaymentGatewayRejected(
                f"Tap rejected the request ({response.status_code}) for {path}: {error_detail}"
            )

        return data