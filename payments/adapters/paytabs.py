"""
PayTabs (paytabs.com) gateway adapter — Hosted Payment Page integration.


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

# Currencies PayTabs (like most card networks) expects with 3 decimal
# places instead of the usual 2.
_THREE_DECIMAL_CURRENCIES = {"BHD", "KWD", "OMR"}

# PayTabs `payment_result.response_status` values.
# A = Authorised (success). H/P = still being processed. Everything else
# (D=Declined, E=Error, X=Expired, C=Cancelled, V=Voided...) is a final failure.
_SUCCESS_STATUSES = {"A"}
_PENDING_STATUSES = {"H", "P"}

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


class PayTabsGatewayAdapter(PaymentGatewayAdapter):

    key = "paytabs"
    display_name = "PayTabs"
    is_async = True

    # -- config -----------------------------------------------------------

    @property
    def _server_key(self) -> str:
        key = getattr(settings, "PAYTABS_SERVER_KEY", "")
        if not key:
            raise PaymentGatewayError("PAYTABS_SERVER_KEY is not configured.")
        return key

    @property
    def _profile_id(self) -> int:
        profile_id = getattr(settings, "PAYTABS_PROFILE_ID", "")
        if not profile_id:
            raise PaymentGatewayError("PAYTABS_PROFILE_ID is not configured.")
        try:
            return int(profile_id)
        except (TypeError, ValueError) as exc:
            raise PaymentGatewayError(
                f"PAYTABS_PROFILE_ID must be numeric, got {profile_id!r}."
            ) from exc

    @property
    def _base_url(self) -> str:
        # Region-specific domains exist (secure.paytabs.sa, secure-egypt...,
        # secure-global...); default to the global endpoint.
        return getattr(settings, "PAYTABS_BASE_URL", "https://secure.paytabs.com")

    @property
    def _callback_url(self) -> str:
        url = getattr(settings, "PAYTABS_CALLBACK_URL", "")
        if not url:
            raise PaymentGatewayError(
                "PAYTABS_CALLBACK_URL is not configured — PayTabs needs a publicly "
                "reachable HTTPS URL for its IPN, it cannot call a localhost callback."
            )
        return url

    @property
    def _default_return_url(self) -> str:
        return getattr(settings, "PAYTABS_DEFAULT_RETURN_URL", "")

    @property
    def _hide_shipping(self) -> bool:
        return bool(getattr(settings, "PAYTABS_HIDE_SHIPPING", True))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._server_key,
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
        cart_id = f"{order_number or 'order'}-{uuid.uuid4().hex[:8]}"

        payload: dict[str, Any] = {
            "profile_id": self._profile_id,
            "tran_type": "sale",
            "tran_class": "ecom",
            "cart_id": cart_id,
            "cart_currency": currency.upper(),
            "cart_amount": _format_amount(amount, currency),
            "cart_description": f"Order {order_number}".strip(),
            "customer_details": self._build_customer(metadata),
            "hide_shipping": self._hide_shipping,
            "callback": self._callback_url,
            "return": metadata.get("merchant_return_url") or self._default_return_url,
        }

        data = self._post("/payment/request", payload)

        tran_ref = data.get("tran_ref", "")
        if not tran_ref:
            raise PaymentGatewayError(f"PayTabs payment request response missing tran_ref: {data!r}")

        redirect_url = data.get("redirect_url", "")

        logger.info(
            "paytabs.payment.created",
            extra={"tran_ref": tran_ref, "order_number": order_number, "cart_id": cart_id},
        )

        return PaymentIntentResult(
            intent_id=tran_ref,
            client_secret="",
            metadata={
                "redirect_url": redirect_url,
                "cart_id": cart_id,
            },
            requires_webhook=True,
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> dict[str, Any]:

        import json

        if not signature:
            raise WebhookVerificationError("PayTabs callback has no Signature header to verify.")

        expected_signature = hmac.new(
            self._server_key.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            raise WebhookVerificationError("PayTabs callback signature mismatch.")

        try:
            event = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError) as exc:
            raise WebhookVerificationError("PayTabs callback payload is not valid JSON.") from exc

        tran_ref = event.get("tran_ref", "")
        payment_result = event.get("payment_result") or {}
        response_status = str(payment_result.get("response_status", "")).upper()

        if response_status in _SUCCESS_STATUSES:
            normalized_status = "success"
        elif response_status in _PENDING_STATUSES:
            normalized_status = "pending"
        else:
            normalized_status = "failed"

        logger.info(
            "paytabs.webhook.verified",
            extra={"tran_ref": tran_ref, "response_status": response_status},
        )

        return {
            "intent_id": tran_ref,
            "transaction_id": tran_ref,  # PayTabs has no separate settlement id
            "status": normalized_status,
            "raw_status": response_status,
        }

    def capture(self, *, intent_id: str) -> PaymentCaptureResult:

        data = self._post(
            "/payment/query",
            {"profile_id": self._profile_id, "tran_ref": intent_id},
        )
        payment_result = data.get("payment_result") or {}
        response_status = str(payment_result.get("response_status", "")).upper()
        success = response_status in _SUCCESS_STATUSES
        return PaymentCaptureResult(
            success=success,
            transaction_id=intent_id,
            metadata={"gateway": self.key, "raw_status": response_status},
        )

    def refund(self, *, transaction_id: str, amount: Decimal) -> PaymentCaptureResult:
        """Full or partial refund of a captured PayTabs transaction."""
        data = self._post(
            "/payment/query",
            {"profile_id": self._profile_id, "tran_ref": transaction_id},
        )
        currency = data.get("cart_currency", "")
        cart_id = data.get("cart_id", transaction_id)

        payload = {
            "profile_id": self._profile_id,
            "tran_type": "refund",
            "tran_class": "ecom",
            "cart_id": cart_id,
            "cart_currency": currency,
            "cart_amount": _format_amount(amount, currency),
            "tran_ref": transaction_id,
        }
        result = self._post("/payment/request", payload)

        payment_result = result.get("payment_result") or {}
        refund_status = str(payment_result.get("response_status", "")).upper()
        success = refund_status in _SUCCESS_STATUSES | _PENDING_STATUSES
        return PaymentCaptureResult(
            success=success,
            transaction_id=result.get("tran_ref", transaction_id),
            metadata={"gateway": self.key, "raw_status": refund_status},
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _build_customer(metadata: dict[str, Any]) -> dict[str, Any]:
        customer: dict[str, Any] = {
            "name": " ".join(
                part
                for part in (
                    metadata.get("customer_first_name", "Guest"),
                    metadata.get("customer_last_name", "Customer"),
                )
                if part
            ),
        }
        email = metadata.get("customer_email")
        if email:
            customer["email"] = email
        phone_number = metadata.get("customer_phone_number")
        if phone_number:
            country_code = metadata.get("customer_phone_country_code", "")
            customer["phone"] = f"{country_code}{phone_number}"
        street = metadata.get("customer_street")
        if street:
            customer["street1"] = street
        city = metadata.get("customer_city")
        if city:
            customer["city"] = city
        country = metadata.get("customer_country")
        if country:
            customer["country"] = country
        zip_code = metadata.get("customer_zip")
        if zip_code:
            customer["zip"] = zip_code
        return customer

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json=payload)

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
            logger.error("paytabs.request.network_error", extra={"path": path, "error": str(exc)})
            raise PaymentGatewayError(f"Network error calling PayTabs ({path}): {exc}") from exc

        if response.status_code >= 500:
            logger.error(
                "paytabs.request.server_error",
                extra={"path": path, "status_code": response.status_code},
            )
            raise PaymentGatewayError(
                f"PayTabs returned a server error ({response.status_code}) for {path}."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise PaymentGatewayError(f"PayTabs response for {path} was not JSON.") from exc

        if response.status_code >= 400:
            error_detail = data.get("message") or data.get("result") or data
            logger.warning(
                "paytabs.request.rejected",
                extra={"path": path, "status_code": response.status_code, "detail": error_detail},
            )
            raise PaymentGatewayRejected(
                f"PayTabs rejected the request ({response.status_code}) for {path}: {error_detail}"
            )

        return data
