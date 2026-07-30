"""Domain exceptions for the payments app."""

from __future__ import annotations


class PaymentError(Exception):
    """Base exception for payment gateway operations."""


class PaymentGatewayError(PaymentError):
    """
    Raised when a gateway call fails after retries (network error, 5xx,
    timeout, or a well-formed error response from the gateway).

    Callers (views, Celery tasks) should catch this distinctly from
    PaymentGatewayRejected — this means "we don't know the outcome", not
    "the payment was declined".
    """


class PaymentGatewayRejected(PaymentError):
    """
    Raised when the gateway synchronously rejects the request itself
    (bad request, invalid source, auth failure) — a 4xx that means the
    request was malformed, not that a card was declined. Card declines are
    a normal *charge status*, not an exception, and surface via
    PaymentIntentResult / the webhook instead.
    """


class WebhookVerificationError(PaymentError):
    """Raised when a webhook payload's signature cannot be verified."""
