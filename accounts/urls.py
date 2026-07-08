"""URL routing for the accounts app."""

from __future__ import annotations

from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.email_register_view, name="register"),
    path("login/email/", views.email_login_view, name="login-email"),
    path("logout/", views.email_logout_view, name="logout"),
    path("login/otp/request/", views.otp_request_view, name="otp-request"),
    path("login/otp/verify/", views.otp_verify_view, name="otp-verify"),
    path("login/google/", views.google_login_view, name="login-google"),
    path("guest-checkout/", views.guest_checkout_view, name="guest-checkout"),
    path("password/forgot/", views.forgot_password_view, name="forgot-password"),
    path("password/reset/", views.reset_password_view, name="reset-password"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("addresses/", views.address_list_create_view, name="address-list-create"),
    path("addresses/<int:address_id>/", views.address_detail_view, name="address-detail"),
    path("payment-methods/", views.payment_methods_list_view, name="payment-methods-list"),
    path(
        "payment-methods/<int:payment_method_id>/delete/",
        views.payment_method_delete_view,
        name="payment-method-delete",
    ),
    path("corporate/register/", views.corporate_register_view, name="corporate-register"),
    path(
        "corporate/pending/",
        views.corporate_pending_approvals_view,
        name="corporate-pending",
    ),
    path("wishlist/shared/", views.wishlist_shared_view, name="wishlist-shared"),
    path("wishlist/add/", views.wishlist_add_view, name="wishlist-add"),
    path(
        "wishlist/shared/mutate/",
        views.wishlist_shared_mutate_view,
        name="wishlist-shared-mutate",
    ),
]
