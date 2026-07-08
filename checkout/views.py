"""HTTP views for the checkout app."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.selectors import get_address_by_id, get_saved_addresses
from cart.selectors import get_cart_for_request, get_cart_summary
from cart.services import get_or_create_cart
from checkout.forms import CheckoutAddressForm, CheckoutDeliveryForm, CheckoutPaymentForm
from checkout.selectors import get_checkout_session_by_id
from checkout.services import create_checkout_session, place_order, update_checkout_session
from delivery.selectors import get_available_slots
from payments.registry import PAYMENT_GATEWAYS
from payments.services import process_payment


@login_required
@require_GET
def checkout_view(request: HttpRequest) -> HttpResponse:
    """Multi-step checkout page with gift Order Preview partial."""
    cart = get_or_create_cart(request=request)
    summary = get_cart_summary(cart=cart)
    if not summary.lines:
        return redirect("catalog:plp")

    profile = request.user.customer_profile
    session = create_checkout_session(
        cart=cart,
        customer_profile=profile,
        session_key=request.session.session_key or "",
    )
    preview_lines = [
        {"product": line.product, "snapshot": line.gift_snapshot} for line in summary.lines
    ]
    city = session.address.city if session.address_id else None
    delivery_date = session.delivery_date.isoformat() if session.delivery_date else None
    delivery_slots = []
    if city and delivery_date:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date)
    return render(
        request,
        "checkout/checkout.html",
        {
            "checkout_session": session,
            "summary": summary,
            "preview_lines": preview_lines,
            "addresses": get_saved_addresses(customer_profile=profile, page=1)["results"],
            "delivery_slots": delivery_slots,
            "payment_gateways": PAYMENT_GATEWAYS,
        },
    )


@login_required
@require_http_methods(["POST"])
def checkout_place_order_view(request: HttpRequest) -> HttpResponse:
    """Place order and process payment in one HTMX step."""
    form = CheckoutPaymentForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "checkout/partials/errors.html",
            {"errors": form.errors},
            status=400,
        )

    cart = get_cart_for_request(request=request)
    if cart is None:
        raise Http404("Cart not found.")

    profile = request.user.customer_profile
    session = create_checkout_session(cart=cart, customer_profile=profile)
    address_form = CheckoutAddressForm(request.POST)
    delivery_form = CheckoutDeliveryForm(request.POST)
    if address_form.is_valid() and address_form.cleaned_data.get("address_id"):
        address = get_address_by_id(
            address_id=address_form.cleaned_data["address_id"],
            customer_profile=profile,
        )
        if address:
            update_checkout_session(checkout_session=session, address=address)
    if delivery_form.is_valid():
        update_checkout_session(
            checkout_session=session,
            delivery_date=delivery_form.cleaned_data.get("delivery_date"),
            delivery_slot_id=delivery_form.cleaned_data.get("delivery_slot_id"),
        )

    order = place_order(
        checkout_session_id=session.pk,
        idempotency_key=form.cleaned_data["idempotency_key"],
        customer_profile=profile,
    )

    payment_data = {}
    if form.cleaned_data.get("voucher_code"):
        payment_data["voucher_code"] = form.cleaned_data["voucher_code"]

    process_payment(
        order=order,
        gateway_key=form.cleaned_data["gateway_key"],
        payment_data=payment_data,
    )

    return render(
        request,
        "checkout/confirmation.html",
        {
            "order": order,
            "checkout_session": get_checkout_session_by_id(session_id=session.pk),
        },
    )
