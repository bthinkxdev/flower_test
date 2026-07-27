"""HTTP views for the payments app."""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from payments.exceptions import PaymentGatewayError, WebhookVerificationError
from payments.services import handle_payment_webhook

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def payment_webhook_view(request: HttpRequest, gateway_key: str) -> HttpResponse:
    """
    CSRF-exempt webhook receiver — signature verified per adapter.
    
    """
    signature = request.headers.get("X-Payment-Signature", "")

    try:
        payment_tx = handle_payment_webhook(
            gateway_key=gateway_key,
            payload=request.body,
            signature=signature,
        )
    except WebhookVerificationError:
        logger.warning("payment.webhook.verification_failed", extra={"gateway_key": gateway_key})
        return JsonResponse({"status": "invalid_signature"}, status=400)
    except PaymentGatewayError:
        logger.exception("payment.webhook.gateway_error", extra={"gateway_key": gateway_key})
        # 502 (not 500) signals "our fault talking to the gateway" clearly
        # in logs/alerts, and importantly it's a status Tap will retry on.
        return JsonResponse({"status": "error"}, status=502)
    except KeyError:
        # get_payment_adapter() raises this for an unknown gateway_key.
        return JsonResponse({"status": "unknown_gateway"}, status=404)

    if payment_tx is None:
        return JsonResponse({"status": "ignored"}, status=404)
    return JsonResponse({"status": payment_tx.status})
