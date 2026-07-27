"""HTTP views for the accounts app; thin request parsing delegating to selectors/services."""

from __future__ import annotations

import json
from typing import Any

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.exceptions import (
    CorporateRegistrationError,
    GoogleAuthError,
    OTPRateLimitError,
    OTPVerificationError,
)
from accounts.forms import (
    AddressForm,
    CorporateRegistrationForm,
    EmailOTPRequestForm,      
    EmailOTPVerifyForm,       
    ForgotPasswordForm,
    GoogleLoginForm,
    GuestCheckoutForm,
    OTPRequestForm,
    OTPVerifyForm,
    ResetPasswordForm,
)
from accounts.models import CustomerProfile, OTPPurpose
from accounts.selectors import (
    get_address_by_id,
    get_customer_dashboard_context,
    get_pending_corporate_approvals,
    get_saved_addresses,
    get_saved_payment_methods,
    get_wishlist,
)
from accounts.services import (
    _check_login_rate_limit,
    _increment_login_rate_limit,
    authenticate_google,
    create_address,
    create_guest_checkout_token,
    delete_address,
    delete_saved_payment_method,
    login_or_create_customer_by_email,   
    login_or_create_customer_by_phone,
    register_corporate_account,
    request_email_otp,                   
    request_otp,
    reset_password_with_otp,
    update_address,
    verify_email_otp,                    
    verify_otp,
)
from core.decorators import role_required
from cart.services import merge_carts
from checkout.services import merge_checkouts
from orders.services import merge_past_guest_orders
from accounts.selectors import get_customer_subscriptions, get_customer_subscription_by_id, get_saved_addresses, get_upcoming_gift_reminders
from accounts.forms import SubscriptionCreateForm, AddressForm, GiftReminderForm
from accounts.subscription_services import (
    create_subscription,
    pause_subscription,
    resume_subscription,
    cancel_subscription,
    merge_session_wishlist_to_user,
    schedule_gift_reminder,
)
from catalog.selectors import get_active_products_for_picker

def _json_body(request: HttpRequest) -> dict[str, Any]:
    """Parse JSON request body; return empty dict for non-JSON requests."""
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return {}


def _error_response(message: str, status: int = 400, code: str = "error") -> JsonResponse:
    return JsonResponse({"success": False, "code": code, "message": message}, status=status)


def _form_error_message(form) -> str:
    """Flatten Django form errors into a single readable sentence (no HTML)."""
    messages: list[str] = []
    for field, errors in form.errors.items():
        label = form.fields[field].label if field in form.fields and form.fields[field].label else field.replace("_", " ").capitalize()
        for err in errors:
            messages.append(f"{label}: {err}" if field != "__all__" else str(err))
    return " ".join(messages) or "Please check the form and try again."


def _success_response(data: dict[str, Any] | None = None, status: int = 200) -> JsonResponse:
    payload: dict[str, Any] = {"success": True}
    if data:
        payload.update(data)
    return JsonResponse(payload, status=status)


def _serialize_address(address) -> dict[str, Any]:
    return {
        "id": address.pk,
        "label": address.label,
        "line1": address.line1,
        "line2": address.line2,
        "city": address.city.name,
        "city_id": address.city_id,
        "is_default": address.is_default,
    }


def _serialize_payment_method(method) -> dict[str, Any]:
    return {
        "id": method.pk,
        "card_brand": method.card_brand,
        "last4": method.last4,
        "expiry_month": method.expiry_month,
        "expiry_year": method.expiry_year,
        "is_default": method.is_default,
    }


def _serialize_order(order) -> dict[str, Any]:
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "order_status": order.order_status,
        "total_amount": str(order.total_amount),
        "created_at": order.created_at.isoformat(),
    }


def _wants_json(request: HttpRequest) -> bool:
    """Return True when the client expects a JSON API response."""
    content_type = request.headers.get("Content-Type", "")
    if request.body and content_type.startswith("application/json"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept

@require_GET
def login_view(request: HttpRequest) -> HttpResponse:
    """Render the email-OTP login page. Redirects if already authenticated."""
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    return render(request, "accounts/login.html", {})

@require_POST
def email_otp_request_view(request: HttpRequest) -> HttpResponse:
    """Request an OTP for email-based customer login (auto-registers on first use)."""
    data = _json_body(request) or request.POST.dict()
    form = EmailOTPRequestForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    try:
        otp_request = request_email_otp(email=form.cleaned_data["email"])
    except OTPRateLimitError as exc:
        return _error_response(str(exc), code="rate_limited", status=429)
    return _success_response(
        {"otp_request_id": otp_request.pk, "expires_at": otp_request.expires_at.isoformat()}
    )


@require_POST
def email_otp_verify_view(request: HttpRequest) -> HttpResponse:
    """Verify an email OTP and log the customer in, creating the account if new."""
    data = _json_body(request) or request.POST.dict()
    form = EmailOTPVerifyForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    try:
        verify_email_otp(email=form.cleaned_data["email"], otp_code=form.cleaned_data["otp_code"])
    except OTPVerificationError as exc:
        return _error_response(str(exc), code=exc.__class__.__name__, status=400)

    profile = login_or_create_customer_by_email(email=form.cleaned_data["email"])
    old_session_key = request.session.session_key
    login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
    merge_carts(user=profile.user, old_session_key=old_session_key)
    merge_checkouts(user=profile.user, old_session_key=old_session_key)
    merge_past_guest_orders(user=profile.user)
    merge_session_wishlist_to_user(old_session_key=old_session_key, user=profile.user)
    return _success_response({"user_id": profile.user_id})


@require_http_methods(["GET", "POST"])
def email_logout_view(request: HttpRequest) -> HttpResponse:
    """Log out the current session."""
    logout(request)
    if _wants_json(request):
        return _success_response()
    return redirect("cms:homepage")


@require_POST
def otp_request_view(request: HttpRequest) -> HttpResponse:
    """Request an OTP for phone-based authentication."""
    data = _json_body(request) or request.POST.dict()
    form = OTPRequestForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    try:
        otp_request = request_otp(
            phone=form.cleaned_data["phone"],
            purpose=form.cleaned_data["purpose"],
        )
    except OTPRateLimitError as exc:
        return _error_response(str(exc), code="rate_limited", status=429)
    return _success_response(
        {"otp_request_id": otp_request.pk, "expires_at": otp_request.expires_at.isoformat()}
    )


@require_POST
def otp_verify_view(request: HttpRequest) -> HttpResponse:
    """Verify an OTP and log the customer in."""
    data = _json_body(request) or request.POST.dict()
    form = OTPVerifyForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    try:
        verify_otp(
            phone=form.cleaned_data["phone"],
            otp_code=form.cleaned_data["otp_code"],
            purpose=form.cleaned_data["purpose"],
        )
    except OTPVerificationError as exc:
        return _error_response(str(exc), code=exc.__class__.__name__, status=400)

    purpose = form.cleaned_data["purpose"]
    if purpose in (OTPPurpose.LOGIN, OTPPurpose.SIGNUP):
        profile = login_or_create_customer_by_phone(phone=form.cleaned_data["phone"])
        old_session_key = request.session.session_key
        login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
        merge_carts(user=profile.user, old_session_key=old_session_key)
        merge_checkouts(user=profile.user, old_session_key=old_session_key)
        merge_past_guest_orders(user=profile.user)
        merge_session_wishlist_to_user(old_session_key=old_session_key, user=profile.user)
        return _success_response({"user_id": profile.user_id})

    return _success_response({"verified": True})


@require_POST
def google_login_view(request: HttpRequest) -> HttpResponse:
    """Authenticate via Google ID token and log the customer in."""
    data = _json_body(request) or request.POST.dict()
    form = GoogleLoginForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    try:
        profile = authenticate_google(google_id_token=form.cleaned_data["id_token"])
    except GoogleAuthError as exc:
        return _error_response(str(exc), code="google_auth_failed", status=401)
    old_session_key = request.session.session_key
    login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
    merge_carts(user=profile.user, old_session_key=old_session_key)
    merge_checkouts(user=profile.user, old_session_key=old_session_key)
    merge_past_guest_orders(user=profile.user)
    merge_session_wishlist_to_user(old_session_key=old_session_key, user=profile.user)
    return _success_response({"user_id": profile.user_id})


@require_POST
def guest_checkout_view(request: HttpRequest) -> HttpResponse:
    """Issue a signed guest checkout token for a cart session."""
    data = _json_body(request) or request.POST.dict()
    form = GuestCheckoutForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    token = create_guest_checkout_token(cart_id=form.cleaned_data["cart_id"])
    return _success_response({"guest_token": token})


@require_POST
def forgot_password_view(request: HttpRequest) -> HttpResponse:
    """Send a password-reset OTP to the customer's phone."""
    data = _json_body(request) or request.POST.dict()
    form = ForgotPasswordForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    try:
        request_otp(phone=form.cleaned_data["phone"], purpose=OTPPurpose.PASSWORD_RESET)
    except OTPRateLimitError as exc:
        return _error_response(str(exc), code="rate_limited", status=429)
    return _success_response({"message": "OTP sent if the phone is registered."})


@require_POST
def reset_password_view(request: HttpRequest) -> HttpResponse:
    """Reset password after OTP verification."""
    data = _json_body(request) or request.POST.dict()
    form = ResetPasswordForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    try:
        user = reset_password_with_otp(
            phone=form.cleaned_data["phone"],
            otp_code=form.cleaned_data["otp_code"],
            new_password=form.cleaned_data["new_password"],
        )
    except OTPVerificationError as exc:
        return _error_response(str(exc), code=exc.__class__.__name__, status=400)
    except CustomerProfile.DoesNotExist:
        return _error_response("Customer profile not found.", status=404)
    old_session_key = request.session.session_key
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    merge_carts(user=user, old_session_key=old_session_key)
    merge_checkouts(user=user, old_session_key=old_session_key)
    merge_past_guest_orders(user=user)
    merge_session_wishlist_to_user(old_session_key=old_session_key, user=user)
    return _success_response({"user_id": user.pk})


@login_required
@require_GET
def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Customer account dashboard."""
    context = get_customer_dashboard_context(user=request.user)
    if context is None:
        if _wants_json(request):
            return _error_response("Customer profile not found.", status=404)
        return render(
            request,
            "accounts/dashboard.html",
            {"error_message": "Customer profile not found."},
            status=404,
        )
    if _wants_json(request):
        return _success_response(
            {
                "profile": {
                    "id": context.profile.pk,
                    "phone": context.profile.phone,
                    "phone_verified": context.profile.phone_verified,
                    "preferred_language": context.profile.preferred_language,
                    "preferred_currency": context.profile.preferred_currency.code,
                },
                "default_address": (
                    _serialize_address(context.default_address) if context.default_address else None
                ),
                "recent_orders": [_serialize_order(o) for o in context.recent_orders],
                "unread_notification_count": context.unread_notification_count,
            }
        )
        
    return render(
        request, 
        "accounts/dashboard.html", 
        {
            "dashboard": context,
            "addresses": get_saved_addresses(customer_profile=request.user.customer_profile, page=1)["results"],
            "address_form": AddressForm(),
        }
    )


@login_required
@require_http_methods(["GET", "POST"])
def address_list_create_view(request: HttpRequest) -> HttpResponse:
    """List saved addresses or create a new one."""
    profile = request.user.customer_profile
    if request.method == "GET":
        page = int(request.GET.get("page", 1))
        data = get_saved_addresses(customer_profile=profile, page=page)
        return _success_response(
            {
                "addresses": [_serialize_address(a) for a in data["results"]],
                "pagination": {
                    "page": data["page"],
                    "total_count": data["total_count"],
                    "has_next": data["has_next"],
                },
            }
        )
    data = _json_body(request) or request.POST.dict()
    form = AddressForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    address = create_address(
        customer_profile=profile,
        label=form.cleaned_data["label"],
        line1=form.cleaned_data["line1"],
        line2=form.cleaned_data.get("line2", ""),
        city_id=form.cleaned_data["city"].pk,
        is_default=form.cleaned_data.get("is_default", False),
    )
    return _success_response({"address": _serialize_address(address)}, status=201)


@login_required
@require_http_methods(["PUT", "PATCH", "DELETE"])
def address_detail_view(request: HttpRequest, address_id: int) -> HttpResponse:
    """Update or delete a saved address."""
    profile = request.user.customer_profile
    if request.method == "DELETE":
        delete_address(customer_profile=profile, address_id=address_id)
        return _success_response()

    data = _json_body(request)
    form = AddressForm(data)
    if not form.is_valid():
        return _error_response(_form_error_message(form), code="validation_error")
    address = update_address(
        customer_profile=profile,
        address_id=address_id,
        label=form.cleaned_data["label"],
        line1=form.cleaned_data["line1"],
        line2=form.cleaned_data.get("line2", ""),
        city_id=form.cleaned_data["city"].pk,
        contact_name=form.cleaned_data.get("contact_name", ""),
        phone=form.cleaned_data.get("phone", ""),
        is_default=form.cleaned_data.get("is_default", False),
    )
    address = get_address_by_id(address_id=address.pk, customer_profile=profile)
    return _success_response({"address": _serialize_address(address)})


@login_required
@require_GET
def payment_methods_list_view(request: HttpRequest) -> HttpResponse:
    """List saved payment methods (token metadata only)."""
    page = int(request.GET.get("page", 1))
    data = get_saved_payment_methods(customer_profile=request.user.customer_profile, page=page)
    return _success_response(
        {
            "payment_methods": [_serialize_payment_method(m) for m in data["results"]],
            "pagination": {
                "page": data["page"],
                "total_count": data["total_count"],
                "has_next": data["has_next"],
            },
        }
    )


@login_required
@require_POST
def payment_method_delete_view(request: HttpRequest, payment_method_id: int) -> HttpResponse:
    """Delete a saved payment method."""
    delete_saved_payment_method(
        customer_profile=request.user.customer_profile,
        payment_method_id=payment_method_id,
    )
    return _success_response()


@require_http_methods(["GET", "POST"])
def corporate_register_view(request: HttpRequest) -> HttpResponse:
    """Register a corporate account (HTML form or JSON API)."""
    if request.method == "GET":
        return render(
            request, "accounts/corporate_register.html", {"form": CorporateRegistrationForm()}
        )

    data = _json_body(request) or request.POST.dict()
    form = CorporateRegistrationForm(data)
    if not form.is_valid():
        if _wants_json(request):
            return _error_response(_form_error_message(form), code="validation_error")
        return render(
            request,
            "accounts/corporate_register.html",
            {"form": form, "errors": form.errors},
            status=400,
        )
    try:
        account = register_corporate_account(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
            name=form.cleaned_data["name"],
            company_name=form.cleaned_data["company_name"],
            trade_license_number=form.cleaned_data["trade_license_number"],
        )
    except CorporateRegistrationError as exc:
        if _wants_json(request):
            return _error_response(str(exc), code="registration_failed")
        return render(
            request,
            "accounts/corporate_register.html",
            {"form": form, "errors": str(exc)},
            status=400,
        )

    if _wants_json(request):
        return _success_response(
            {"corporate_account_id": account.pk, "approval_status": account.approval_status},
            status=201,
        )
    return render(
        request,
        "accounts/corporate_register_pending.html",
        {"account": account},
    )


@login_required
@role_required("SuperAdmin", "StoreAdmin")
@require_GET
def corporate_pending_approvals_view(request: HttpRequest) -> HttpResponse:
    """Admin view: paginated list of pending corporate approvals."""
    page = int(request.GET.get("page", 1))
    data = get_pending_corporate_approvals(page=page)
    return _success_response(
        {
            "results": [
                {
                    "id": a.pk,
                    "company_name": a.company_name,
                    "trade_license_number": a.trade_license_number,
                    "email": a.user.email,
                    "created_at": a.created_at.isoformat(),
                }
                for a in data["results"]
            ],
            "pagination": {
                "page": data["page"],
                "page_size": data["page_size"],
                "total_count": data["total_count"],
                "total_pages": data["total_pages"],
                "has_next": data["has_next"],
                "has_previous": data["has_previous"],
            },
        }
    )


@require_GET
def wishlist_shared_view(request: HttpRequest) -> HttpResponse:
    """Read-only shared wishlist via signed token — no auth required."""
    token = request.GET.get("token", "")
    view = get_wishlist(share_token=token)
    if view is None:
        return JsonResponse({"error": "Invalid or expired wishlist link."}, status=404)
    return JsonResponse(
        {
            "readonly": True,
            "items": [
                {"product_id": item.product_id, "name": item.product.name} for item in view.items
            ],
        }
    )


@require_POST
def wishlist_add_view(request: HttpRequest) -> HttpResponse:
    """Add a product to the authenticated customer's wishlist."""
    from accounts.subscription_services import add_to_wishlist, get_or_create_wishlist

    product_id = int(request.POST.get("product_id", 0))
    wishlist = get_or_create_wishlist(request=request)
    add_to_wishlist(wishlist=wishlist, product_id=product_id)
    return JsonResponse({"status": "added"})

@require_POST
def wishlist_remove_view(request: HttpRequest) -> HttpResponse:
    """Remove a product from the authenticated customer's wishlist."""
    from accounts.subscription_services import get_or_create_wishlist, remove_from_wishlist

    product_id = int(request.POST.get("product_id", 0))
    wishlist = get_or_create_wishlist(request=request)
    remove_from_wishlist(wishlist=wishlist, product_id=product_id)
    return redirect("accounts:wishlist")

@require_POST
def wishlist_shared_mutate_view(request: HttpRequest) -> HttpResponse:
    """Mutations via share token are forbidden."""
    token = request.POST.get("token", "")
    if token:
        return JsonResponse({"error": "Shared wishlists are read-only."}, status=403)
    return JsonResponse({"error": "Authentication required."}, status=401)

@require_GET
def wishlist_view(request: HttpRequest) -> HttpResponse:
    """Render the wishlist page for guest or authenticated customers."""
    from accounts.subscription_services import get_or_create_wishlist

    wl = get_or_create_wishlist(request=request)
    view = get_wishlist(wishlist=wl)
    if view is None:
        return render(request, "accounts/wishlist.html", {"items": []})
    return render(request, "accounts/wishlist.html", {"wishlist": view.wishlist, "items": view.items})

@login_required
@require_GET
def gift_reminder_list_view(request: HttpRequest) -> HttpResponse:
    """Personal gift calendar — upcoming occasions."""
    profile = request.user.customer_profile
    reminders = get_upcoming_gift_reminders(customer_profile=profile)
    return render(
        request,
        "accounts/gift_reminders.html",
        {"reminders": reminders, "form": GiftReminderForm()},
    )


@login_required
@require_POST
def gift_reminder_create_view(request: HttpRequest) -> HttpResponse:
    """Add a gift reminder to the calendar."""
    profile = request.user.customer_profile
    form = GiftReminderForm(request.POST)
    if not form.is_valid():
        reminders = get_upcoming_gift_reminders(customer_profile=profile)
        return render(
            request,
            "accounts/gift_reminders.html",
            {"reminders": reminders, "form": form},
            status=400,
        )
    schedule_gift_reminder(
        customer_profile=profile,
        occasion_type=form.cleaned_data["occasion_type"],
        reminder_date=form.cleaned_data["reminder_date"],
        recipient_name=form.cleaned_data["recipient_name"],
        notes=form.cleaned_data.get("notes", ""),
        notify_days_before=form.cleaned_data["notify_days_before"],
    )
    return redirect("accounts:gift-reminders")


@login_required
@require_POST
def gift_reminder_delete_view(request: HttpRequest, reminder_id: int) -> HttpResponse:
    """Remove a gift reminder owned by the current customer."""
    from accounts.models import GiftReminder

    profile = request.user.customer_profile
    GiftReminder.objects.filter(pk=reminder_id, customer_profile=profile).delete()
    return redirect("accounts:gift-reminders")

@login_required
@require_GET
def subscription_list_view(request: HttpRequest) -> HttpResponse:
    """List the authenticated customer's subscriptions."""
    profile = request.user.customer_profile
    subscriptions = get_customer_subscriptions(customer_profile=profile)
    return render(request, "accounts/subscription_list.html", {"subscriptions": subscriptions})


@login_required
@require_http_methods(["GET", "POST"])
def subscription_create_view(request: HttpRequest) -> HttpResponse:
    profile = request.user.customer_profile
    products = get_active_products_for_picker()

    if request.method == "GET":
        initial = {}
        product_id = request.GET.get("product_id")
        if product_id:
            initial["product_id"] = product_id
        form = SubscriptionCreateForm(initial=initial, customer_profile=profile)
        return render(request, "accounts/subscription_create.html", {"form": form, "products": products})

    data = _json_body(request) or request.POST.dict()
    form = SubscriptionCreateForm(data, customer_profile=profile)
    if not form.is_valid():
        if _wants_json(request):
            return _error_response(_form_error_message(form), code="validation_error")
        return render(
            request,
            "accounts/subscription_create.html",
            {"form": form, "errors": form.errors, "products": products},
            status=400,
        )
    subscription = create_subscription(
        customer_profile=profile,
        product_id=form.cleaned_data["product_id"].pk,
        delivery_address_id=form.cleaned_data["delivery_address_id"].pk,
        frequency=form.cleaned_data["frequency"],
        next_run_date=form.cleaned_data["next_run_date"],
        quantity=form.cleaned_data["quantity"],
        created_by=request.user,
    )
    if _wants_json(request):
        return _success_response({"subscription_id": subscription.pk}, status=201)
    return redirect("accounts:subscription-list")


@login_required
@require_POST
def subscription_pause_view(request: HttpRequest, subscription_id: int) -> HttpResponse:
    """Pause a subscription owned by the current customer."""
    subscription = get_customer_subscription_by_id(
        subscription_id=subscription_id, customer_profile=request.user.customer_profile
    )
    if subscription is None:
        return _error_response("Subscription not found.", status=404)
    pause_subscription(subscription=subscription)
    return _success_response()


@login_required
@require_POST
def subscription_resume_view(request: HttpRequest, subscription_id: int) -> HttpResponse:
    """Resume a paused subscription owned by the current customer."""
    subscription = get_customer_subscription_by_id(
        subscription_id=subscription_id, customer_profile=request.user.customer_profile
    )
    if subscription is None:
        return _error_response("Subscription not found.", status=404)
    resume_subscription(subscription=subscription)
    return _success_response()


@login_required
@require_POST
def subscription_cancel_view(request: HttpRequest, subscription_id: int) -> HttpResponse:
    """Cancel a subscription owned by the current customer."""
    subscription = get_customer_subscription_by_id(
        subscription_id=subscription_id, customer_profile=request.user.customer_profile
    )
    if subscription is None:
        return _error_response("Subscription not found.", status=404)
    cancel_subscription(subscription=subscription)
    return _success_response()

@login_required
@require_POST
def dashboard_add_address_view(request: HttpRequest) -> HttpResponse:
    """Endpoint for HTMX address creation from dashboard."""
    profile = request.user.customer_profile
    form = AddressForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "accounts/partials/address_list_partial.html",
            {
                "addresses": get_saved_addresses(customer_profile=profile, page=1)["results"],
                "address_form": form,
            }
        )
        
    create_address(
        customer_profile=profile,
        label=form.cleaned_data["label"],
        line1=form.cleaned_data["line1"],
        line2=form.cleaned_data.get("line2", ""),
        city_id=form.cleaned_data["city"].pk,
        is_default=form.cleaned_data.get("is_default", False),
    )
    
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
    return render(
        request,
        "accounts/partials/address_list_partial.html",
        {
            "addresses": addresses,
            "address_form": AddressForm(),
        }
    )

@login_required
@require_http_methods(["POST", "DELETE"])
def dashboard_delete_address_view(request: HttpRequest, address_id: int) -> HttpResponse:
    """Endpoint for HTMX address deletion from dashboard."""
    profile = request.user.customer_profile
    delete_address(customer_profile=profile, address_id=address_id)
    
    addresses = get_saved_addresses(customer_profile=profile, page=1)["results"]
    return render(
        request,
        "accounts/partials/address_list_partial.html",
        {
            "addresses": addresses,
            "address_form": AddressForm(),
        }
    )