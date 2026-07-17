"""HTTP views for the checkout app."""

from __future__ import annotations

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
from delivery.selectors import get_available_slots
from payments.registry import PAYMENT_GATEWAYS
from payments.services import process_payment
from datetime import date
from accounts.forms import AddressForm
from accounts.services import create_address
from django.shortcuts import get_object_or_404
from decimal import Decimal
from accounts.models import Address
from django.urls import reverse
from core.page_rerender import is_htmx_request
from orders.selectors import get_order_for_customer


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
        if saved_addresses:
            update_checkout_session(checkout_session=session, address=saved_addresses[0])
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
        },
    )


@require_http_methods(["POST"])
def checkout_place_order_view(request: HttpRequest) -> HttpResponse:
    """Place order and process payment in one HTMX step. Works for guests too."""
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

    profile = request.user.customer_profile if request.user.is_authenticated else None
    session = create_checkout_session(
        cart=cart,
        customer_profile=profile,
        session_key=request.session.session_key or "",
    )

    if profile:
        address_form = CheckoutAddressForm(request.POST)
        if address_form.is_valid() and address_form.cleaned_data.get("address_id"):
            address = get_address_by_id(
                address_id=address_form.cleaned_data["address_id"],
                customer_profile=profile,
            )
            if address:
                update_checkout_session(checkout_session=session, address=address)
    else:
        guest_form = CheckoutGuestDetailsForm(request.POST)
        if not guest_form.is_valid():
            return render(
                request,
                "checkout/partials/errors.html",
                {"errors": guest_form.errors},
                status=400,
            )
        cd = guest_form.cleaned_data
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

    delivery_form = CheckoutDeliveryForm(request.POST)
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

@login_required
@require_POST
def checkout_update_session_view(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint to update draft session options (address, date) and recalculate delivery charges."""
    cart = get_or_create_cart(request=request)
    profile = request.user.customer_profile
    session = create_checkout_session(
        cart=cart,
        customer_profile=profile,
        session_key=request.session.session_key or "",
    )
    
    address_id = request.POST.get("address_id")
    delivery_date_str = request.POST.get("delivery_date")
    
    if address_id:
        address = get_address_by_id(address_id=int(address_id), customer_profile=profile)
        if address:
            update_checkout_session(checkout_session=session, address=address)
            
    if delivery_date_str:
        try:
            delivery_date = date.fromisoformat(delivery_date_str)
            update_checkout_session(checkout_session=session, delivery_date=delivery_date)
        except ValueError:
            pass
            
    summary = get_cart_summary(cart=cart)
    
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

@login_required
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
        line1=form.cleaned_data["line1"],
        line2=form.cleaned_data.get("line2", ""),
        city_id=form.cleaned_data["city"].pk,
        is_default=form.cleaned_data.get("is_default", False),
    )
    update_checkout_session(checkout_session=session, address=address)

    summary = get_cart_summary(cart=cart)
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
    city = session.address.city if session.address_id else None
    delivery_date_iso = session.delivery_date.isoformat() if session.delivery_date else None
    delivery_slots = []
    if city and delivery_date_iso:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date_iso)

    return render(
        request,
        "checkout/partials/address_added.html",
        {
            "checkout_session": session,
            "summary": summary,
            "addresses": addresses,
            "delivery_slots": delivery_slots,
            "address_form": AddressForm(),
        }
    )


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
        
    address = form.save()
    
    cart = get_or_create_cart(request=request)
    session = create_checkout_session(cart=cart, customer_profile=profile)
    update_checkout_session(checkout_session=session, address=address)
    
    summary = get_cart_summary(cart=cart)
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
    
    city = session.address.city if session.address_id else None
    delivery_date_iso = session.delivery_date.isoformat() if session.delivery_date else None
    delivery_slots = []
    if city and delivery_date_iso:
        delivery_slots = get_available_slots(city=city, delivery_date=delivery_date_iso)
        
    return render(
        request,
        "checkout/partials/address_added.html",
        {
            "checkout_session": session,
            "summary": summary,
            "addresses": addresses,
            "delivery_slots": delivery_slots,
            "address_form": AddressForm(),
        }
    )

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
    
    summary = get_cart_summary(cart=cart)
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
    
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