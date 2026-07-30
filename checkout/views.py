"""HTTP views for the checkout app."""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.selectors import get_address_by_id, get_saved_addresses
from cart.selectors import get_cart_for_request, get_cart_summary
from cart.services import get_or_create_cart
from checkout.forms import CheckoutAddressForm, CheckoutDeliveryForm, CheckoutPaymentForm, CheckoutGuestDetailsForm
from checkout.selectors import get_checkout_session_by_id
from checkout.services import create_checkout_session, place_order, update_checkout_session, build_guest_order_token, verify_guest_order_token
from checkout.exceptions import CheckoutError
from cart.exceptions import OutOfStockError
from catalog.exceptions import InsufficientStockError
from delivery.exceptions import SlotFullyBookedError
from django.utils.translation import gettext as _
from delivery.selectors import get_available_slots
from payments.registry import PAYMENT_GATEWAYS
from payments.services import process_payment
from payments.exceptions import PaymentGatewayError, PaymentGatewayRejected
from payments.models import PaymentStatus
from datetime import date
from accounts.forms import AddressForm
from accounts.services import create_address, update_address
from django.shortcuts import get_object_or_404
from decimal import Decimal
from accounts.models import Address
from django.urls import reverse

logger = logging.getLogger(__name__)
from core.page_rerender import is_htmx_request
from orders.selectors import get_order_for_customer
import json

def _pick_default_address(addresses):
    """Prefer the address marked as default; fall back to the first saved address."""
    if not addresses:
        return None
    return next((addr for addr in addresses if addr.is_default), addresses[0])


@require_GET
def checkout_view(request: HttpRequest) -> HttpResponse:
    """Multi-step checkout page with gift Order Preview partial. Works for guests too."""
    cart = get_or_create_cart(request=request)
    summary = get_cart_summary(cart=cart)
    if not summary.lines:
        return redirect("catalog:plp")
    profile = request.user.customer_profile if request.user.is_authenticated else None
    session = create_checkout_session(
        cart=cart,
        customer_profile=profile,
        session_key=request.session.session_key or "",
    )

    if profile and not session.address_id:
        saved_addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
        default_address = _pick_default_address(saved_addresses)
        if default_address is not None:
            update_checkout_session(checkout_session=session, address=default_address)
            summary = get_cart_summary(cart=cart)
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
            "addresses": get_saved_addresses(customer_profile=profile, page=1)["results"] if profile else [],
            "delivery_slots": delivery_slots,
            "payment_gateways": PAYMENT_GATEWAYS,
            "address_form": AddressForm() if profile else None,
            "is_guest": profile is None,
            "guest_details_form": CheckoutGuestDetailsForm() if profile is None else None,
            "checkout_address_form": CheckoutAddressForm() if profile else None,
            "delivery_form": CheckoutDeliveryForm(
                initial={
                    "delivery_date": session.delivery_date,
                    "delivery_slot_id": session.delivery_slot_id,
                }
            ),
            "payment_form": CheckoutPaymentForm(),
            "selected_address_id": session.address_id,
            "selected_delivery_slot_id": session.delivery_slot_id,
            "selected_gateway_key": None,
        },
    )


def _render_checkout_order_form_errors(
    request: HttpRequest,
    *,
    session,
    cart,
    profile,
    payment_form: CheckoutPaymentForm,
    delivery_form: CheckoutDeliveryForm,
    checkout_address_form: CheckoutAddressForm | None,
    guest_details_form: CheckoutGuestDetailsForm | None,
    address=None,
    general_error: str = "",
) -> HttpResponse:
    """Re-render the checkout form with bound (invalid) forms so each field shows its own error."""
    summary = get_cart_summary(cart=cart)
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"] if profile else []

    # Prefer whatever the user just submitted (even if some other field on the
    # form is invalid) over stale session data, so delivery slots line up with
    # what's currently on screen.
    city = None
    if profile:
        if address is not None:
            city = address.city
        elif session.address_id:
            city = session.address.city
    else:
        if guest_details_form is not None:
            city = guest_details_form.cleaned_data.get("city")
        if city is None and session.guest_details:
            from delivery.models import City

            city = City.objects.filter(pk=session.guest_details.get("city_id")).first()

    delivery_date = delivery_form.cleaned_data.get("delivery_date") if delivery_form.is_bound else None
    if delivery_date is None:
        delivery_date = session.delivery_date
    delivery_date_iso = delivery_date.isoformat() if delivery_date else None

    delivery_slots = []
    if city and delivery_date_iso:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date_iso)

    return render(
        request,
        "checkout/partials/checkout_order_form.html",
        {
            "checkout_session": session,
            "summary": summary,
            "addresses": addresses,
            "delivery_slots": delivery_slots,
            "payment_gateways": PAYMENT_GATEWAYS,
            "is_guest": profile is None,
            "guest_details_form": guest_details_form,
            "checkout_address_form": checkout_address_form,
            "delivery_form": delivery_form,
            "payment_form": payment_form,
            "general_error": general_error,
            "selected_address_id": request.POST.get("address_id"),
            "selected_delivery_slot_id": request.POST.get("delivery_slot_id"),
            "selected_gateway_key": request.POST.get("gateway_key"),
        },
        status=400,
    )


@require_http_methods(["POST"])
def checkout_place_order_view(request: HttpRequest) -> HttpResponse:
    """Place order and process payment in one HTMX step. Works for guests too."""
    cart = get_cart_for_request(request=request)
    if cart is None:
        raise Http404("Cart not found.")

    profile = request.user.customer_profile if request.user.is_authenticated else None
    session = create_checkout_session(
        cart=cart,
        customer_profile=profile,
        session_key=request.session.session_key or "",
    )

    payment_form = CheckoutPaymentForm(request.POST)
    delivery_form = CheckoutDeliveryForm(request.POST)
    payment_ok = payment_form.is_valid()
    delivery_ok = delivery_form.is_valid()

    checkout_address_form = None
    guest_details_form = None
    address = None

    if profile:
        checkout_address_form = CheckoutAddressForm(request.POST)
        address_ok = checkout_address_form.is_valid()
        if address_ok:
            address = get_address_by_id(
                address_id=checkout_address_form.cleaned_data["address_id"],
                customer_profile=profile,
            )
            if address is None:
                checkout_address_form.add_error(
                    "address_id",
                    _("The selected address is no longer available. Please choose another."),
                )
                address_ok = False
    else:
        guest_details_form = CheckoutGuestDetailsForm(request.POST)
        address_ok = guest_details_form.is_valid()

    if not (payment_ok and delivery_ok and address_ok):
        return _render_checkout_order_form_errors(
            request,
            session=session,
            cart=cart,
            profile=profile,
            payment_form=payment_form,
            delivery_form=delivery_form,
            checkout_address_form=checkout_address_form,
            guest_details_form=guest_details_form,
            address=address,
        )

    if profile:
        update_checkout_session(checkout_session=session, address=address)
    else:
        cd = guest_details_form.cleaned_data
        update_checkout_session(
            checkout_session=session,
            guest_details={
                "full_name": cd["full_name"],
                "email": cd["email"],
                "phone": cd["phone"],
                "line1": cd["line1"],
                "line2": cd.get("line2", ""),
                "city_id": cd["city"].pk,
                "city_name": cd["city"].name,
            },
        )

    update_checkout_session(
        checkout_session=session,
        delivery_date=delivery_form.cleaned_data.get("delivery_date"),
        delivery_slot_id=delivery_form.cleaned_data.get("delivery_slot_id"),
    )

    try:
        order = place_order(
            checkout_session_id=session.pk,
            idempotency_key=payment_form.cleaned_data["idempotency_key"],
            customer_profile=profile,
        )

        payment_data = {}
        if payment_form.cleaned_data.get("voucher_code"):
            payment_data["voucher_code"] = payment_form.cleaned_data["voucher_code"]

    
        payment_data["merchant_return_url"] = request.build_absolute_uri(
            reverse("checkout:payment-return", kwargs={"order_id": order.pk})
        )
        if profile is None:
            payment_data["merchant_return_url"] += f"?gt={build_guest_order_token(order_id=order.pk)}"

        if request.user.is_authenticated:
            payment_data["customer_first_name"] = request.user.first_name or "Guest"
            payment_data["customer_last_name"] = request.user.last_name or "Customer"
            payment_data["customer_email"] = request.user.email
        else:
            guest_details = session.guest_details or {}
            full_name = guest_details.get("full_name", "Guest Customer").split(" ", 1)
            payment_data["customer_first_name"] = full_name[0]
            payment_data["customer_last_name"] = full_name[1] if len(full_name) > 1 else ""
            payment_data["customer_email"] = guest_details.get("email", "")
            payment_data["customer_phone_number"] = guest_details.get("phone", "")

        payment_tx = process_payment(
            order=order,
            gateway_key=payment_form.cleaned_data["gateway_key"],
            payment_data=payment_data,
        )
    except (CheckoutError, SlotFullyBookedError, InsufficientStockError, OutOfStockError) as exc:
        return _render_checkout_order_form_errors(
            request,
            session=session,
            cart=cart,
            profile=profile,
            payment_form=payment_form,
            delivery_form=delivery_form,
            checkout_address_form=checkout_address_form,
            guest_details_form=guest_details_form,
            address=address,
            general_error=str(exc),
        )
    except (PaymentGatewayError, PaymentGatewayRejected) as exc:
        logger.warning(
            "checkout.payment.gateway_error order_id=%s detail=%s",
            order.pk,
            str(exc),
        )
        return _render_checkout_order_form_errors(
            request,
            session=session,
            cart=cart,
            profile=profile,
            payment_form=payment_form,
            delivery_form=delivery_form,
            checkout_address_form=checkout_address_form,
            guest_details_form=guest_details_form,
            address=address,
            general_error=_("We couldn't reach the payment provider. Please try again."),
        )

    
    gateway_redirect_url = (payment_tx.metadata or {}).get("redirect_url")
    if gateway_redirect_url:
        redirect_url = gateway_redirect_url
    else:
        redirect_url = reverse("checkout:confirmation", kwargs={"order_id": order.pk})
        if profile is None:
            token = build_guest_order_token(order_id=order.pk)
            redirect_url = f"{redirect_url}?gt={token}"

    if is_htmx_request(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = redirect_url
        return response
    return redirect(redirect_url)



@require_GET
def checkout_payment_return_view(request: HttpRequest, order_id: int) -> HttpResponse:
    
    if request.user.is_authenticated:
        profile = request.user.customer_profile
        order = get_order_for_customer(order_id=order_id, customer_profile=profile)
    else:
        token = request.GET.get("gt", "")
        if not token or not verify_guest_order_token(token=token, order_id=order_id):
            raise Http404("Order not found.")
        order = get_order_for_customer(order_id=order_id, customer_profile=None)

    payment_tx = order.payment_transactions.order_by("-created_at").first()
    gt_suffix = f"?gt={request.GET['gt']}" if request.GET.get("gt") else ""

    if payment_tx is not None and payment_tx.status == PaymentStatus.SUCCESS:
        return redirect(f"{reverse('checkout:confirmation', kwargs={'order_id': order.pk})}{gt_suffix}")

    if payment_tx is not None and payment_tx.status == PaymentStatus.FAILED:
        return redirect(f"{reverse('checkout:checkout')}?payment_failed=1")

    
    return render(request, "checkout/payment_pending.html", {"order": order}, status=202)


@require_GET
def checkout_confirmation_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """Standalone order-success page shown after checkout completes. Guest-accessible via signed token."""
    if request.user.is_authenticated:
        profile = request.user.customer_profile
        order = get_order_for_customer(order_id=order_id, customer_profile=profile)
    else:
        token = request.GET.get("gt", "")
        if not token or not verify_guest_order_token(token=token, order_id=order_id):
            raise Http404("Order not found.")
        order = get_order_for_customer(order_id=order_id, customer_profile=None)
        if order is not None and order.customer_profile_id is not None:
            # A guest token can never authorize viewing a registered customer's order.
            order = None

    if order is None:
        raise Http404("Order not found.")
    return render(request, "checkout/order_confirmation.html", {"order": order})

@require_POST
def checkout_update_session_view(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint to update draft session options (address, date, guest city) and recalculate delivery charges. Works for guests too."""
    from delivery.models import City
    from cart.services import recalculate_delivery_charge

    cart = get_or_create_cart(request=request)
    profile = request.user.customer_profile if request.user.is_authenticated else None
    session = create_checkout_session(
        cart=cart,
        customer_profile=profile,
        session_key=request.session.session_key or "",
    )

    address_id = request.POST.get("address_id")
    delivery_date_str = request.POST.get("delivery_date")
    city_id = request.POST.get("city")

    city = None
    if address_id and profile:
        address = get_address_by_id(address_id=int(address_id), customer_profile=profile)
        if address:
            update_checkout_session(checkout_session=session, address=address)
            city = address.city
    elif not profile and city_id:
        city = City.objects.filter(pk=city_id, is_active=True).first()
        if city:
            recalculate_delivery_charge(cart=cart, destination_city=city)

    if delivery_date_str:
        try:
            delivery_date = date.fromisoformat(delivery_date_str)
            update_checkout_session(checkout_session=session, delivery_date=delivery_date)
        except ValueError:
            pass

    cart.refresh_from_db()

    summary = get_cart_summary(cart=cart)

    if city is None:
        city = session.address.city if session.address_id else None
    delivery_date_iso = session.delivery_date.isoformat() if session.delivery_date else None
    delivery_slots = []
    if city and delivery_date_iso:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date_iso)

    return render(
        request,
        "checkout/partials/checkout_updates.html",
        {
            "checkout_session": session,
            "summary": summary,
            "delivery_slots": delivery_slots,
        },
    )

@require_POST
def checkout_add_address_view(request: HttpRequest) -> HttpResponse:
    """Endpoint for HTMX address creation during checkout and reload lists/summaries."""
    profile = request.user.customer_profile
    cart = get_or_create_cart(request=request)
    session = create_checkout_session(cart=cart, customer_profile=profile)

    form = AddressForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "checkout/partials/checkout_address_create_form.html",  
            {"address_form": form},
        )

    address = create_address(
        customer_profile=profile,
        label=form.cleaned_data["label"],
        contact_name=form.cleaned_data.get("contact_name", ""),
        phone=form.cleaned_data.get("phone", ""),
        line1=form.cleaned_data["line1"],
        line2=form.cleaned_data.get("line2", ""),
        city_id=form.cleaned_data["city"].pk,
        is_default=form.cleaned_data.get("is_default", False),
    )
    if address.is_default or not session.address_id:
        update_checkout_session(checkout_session=session, address=address)
    cart.refresh_from_db()

    summary = get_cart_summary(cart=cart)
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
    city = session.address.city if session.address_id else None
    delivery_date_iso = session.delivery_date.isoformat() if session.delivery_date else None
    delivery_slots = []
    if city and delivery_date_iso:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date_iso)

    response = render(
        request,
        "checkout/partials/address_added.html",
        {
            "checkout_session": session,
            "summary": summary,
            "addresses": addresses,
            "delivery_slots": delivery_slots,
            "address_form": AddressForm(),
            "selected_address_id": session.address_id,
        }
    )
    response["HX-Trigger"] = json.dumps({"addressSaved": {"message": "Address saved"}})
    return response


@require_GET
def checkout_address_form_view(request: HttpRequest, address_id: int) -> HttpResponse:
    """Return the populated address form fields for editing inside the checkout collapse."""
    profile = request.user.customer_profile
    address = get_object_or_404(Address, pk=address_id, customer_profile=profile)
    form = AddressForm(instance=address)
    
    return render(
        request,
        "checkout/partials/checkout_address_edit_form.html",
        {
            "address_form": form,
            "address": address,
        }
    )

@require_GET
def checkout_address_form_reset_view(request: HttpRequest) -> HttpResponse:
    """Reset the collapse address card back to clean Add Address mode."""
    return render(
        request,
        "checkout/partials/checkout_address_create_form.html",
        {"address_form": AddressForm()}
    )

@require_POST
def checkout_edit_address_view(request: HttpRequest, address_id: int) -> HttpResponse:
    """Save modifications to an address during checkout and refresh charges."""
    profile = request.user.customer_profile
    address = get_object_or_404(Address, pk=address_id, customer_profile=profile)

    form = AddressForm(request.POST, instance=address)
    if not form.is_valid():
        return render(
            request,
            "checkout/partials/checkout_address_edit_form.html",
            {"address_form": form, "address": address}
        )

    # Route through the service (not form.save()) so promoting this address to
    # default atomically demotes any other default — form.save() would just
    # flip this row's flag and leave a stale second "default" in place.
    address = update_address(
        customer_profile=profile,
        address_id=address.pk,
        label=form.cleaned_data["label"],
        line1=form.cleaned_data["line1"],
        line2=form.cleaned_data.get("line2", ""),
        city_id=form.cleaned_data["city"].pk,
        contact_name=form.cleaned_data.get("contact_name", ""),
        phone=form.cleaned_data.get("phone", ""),
        is_default=form.cleaned_data.get("is_default", False),
    )

    cart = get_or_create_cart(request=request)
    session = create_checkout_session(cart=cart, customer_profile=profile)
    # Same rule as adding an address: keep the current selection unless this
    # address is now the default, is the one already selected, or nothing is
    # selected yet.
    if address.is_default or not session.address_id or session.address_id == address.pk:
        update_checkout_session(checkout_session=session, address=address)

    cart.refresh_from_db()

    summary = get_cart_summary(cart=cart)
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
    
    city = session.address.city if session.address_id else None
    delivery_date_iso = session.delivery_date.isoformat() if session.delivery_date else None
    delivery_slots = []
    if city and delivery_date_iso:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date_iso)
        
    response = render(
        request,
        "checkout/partials/address_added.html",
        {
            "checkout_session": session,
            "summary": summary,
            "addresses": addresses,
            "delivery_slots": delivery_slots,
            "address_form": AddressForm(),
            "selected_address_id": session.address_id,
        }
    )
    response["HX-Trigger"] = json.dumps({"addressSaved": {"message": "Address updated"}})
    return response

@require_POST
def checkout_delete_address_view(request: HttpRequest, address_id: int) -> HttpResponse:
    """Delete address during checkout and reset delivery charges if currently active."""
    profile = request.user.customer_profile
    from accounts.services import delete_address
    
    cart = get_or_create_cart(request=request)
    session = create_checkout_session(cart=cart, customer_profile=profile)
    
    if session.address_id == address_id:
        session.address = None
        session.save(update_fields=["address"])
        cart.destination_city = None
        cart.delivery_charge = Decimal("0.00")
        cart.save(update_fields=["destination_city", "delivery_charge", "updated_at"])
        
    delete_address(customer_profile=profile, address_id=address_id)

    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]

    # If checkout is left without a selected address (the one just deleted was
    # the active one), fall back to the default address rather than leaving
    # the order unaddressable.
    if not session.address_id and addresses:
        fallback_address = _pick_default_address(addresses)
        if fallback_address is not None:
            update_checkout_session(checkout_session=session, address=fallback_address)
            cart.refresh_from_db()

    summary = get_cart_summary(cart=cart)

    city = session.address.city if session.address_id else None
    delivery_date_iso = session.delivery_date.isoformat() if session.delivery_date else None
    delivery_slots = []
    if city and delivery_date_iso:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date_iso)

    return render(
        request,
        "checkout/partials/address_deleted.html",
        {
            "checkout_session": session,
            "summary": summary,
            "addresses": addresses,
            "delivery_slots": delivery_slots,
            "selected_address_id": session.address_id,
        }
    )

@require_POST
def checkout_preview_delivery_view(request: HttpRequest) -> HttpResponse:
    from cart.services import preview_delivery_charge
    from delivery.models import City

    city_id = request.POST.get("city")
    cart = get_or_create_cart(request=request)
    city = City.objects.filter(pk=city_id, is_active=True).first() if city_id else None
    charge = preview_delivery_charge(cart=cart, destination_city=city) if city else Decimal("0.00")
    summary = get_cart_summary(cart=cart)
    grand_total = summary.subtotal - summary.coupon_discount + charge
    return render(
        request,
        "checkout/partials/delivery_charge_preview.html",
        {"delivery_charge": charge, "grand_total": grand_total},
    )