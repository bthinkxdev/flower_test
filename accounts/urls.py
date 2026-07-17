"""URL routing for the accounts app."""

from __future__ import annotations

from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),   # new — renders login.html
    path("login/otp/email/request/", views.email_otp_request_view, name="otp-email-request"),
    path("login/otp/email/verify/", views.email_otp_verify_view, name="otp-email-verify"),
    path("logout/", views.email_logout_view, name="logout"),
    path("login/otp/request/", views.otp_request_view, name="otp-request"),
    path("login/otp/verify/", views.otp_verify_view, name="otp-verify"),
    path("login/google/", views.google_login_view, name="login-google"),
    path("guest-checkout/", views.guest_checkout_view, name="guest-checkout"),
    path("password/forgot/", views.forgot_password_view, name="forgot-password"),
    path("password/reset/", views.reset_password_view, name="reset-password"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("dashboard/addresses/add/", views.dashboard_add_address_view, name="dashboard-add-address"),
    path("dashboard/addresses/<int:address_id>/delete/", views.dashboard_delete_address_view, name="dashboard-delete-address"),
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
    path("wishlist/remove/", views.wishlist_remove_view, name="wishlist-remove"),
    path(
        "wishlist/shared/mutate/",
        views.wishlist_shared_mutate_view,
        name="wishlist-shared-mutate",
    ),
    path("wishlist/", views.wishlist_view, name="wishlist"),

    path("subscriptions/", views.subscription_list_view, name="subscription-list"),
    path("subscriptions/create/", views.subscription_create_view, name="subscription-create"),
    path(
        "subscriptions/<int:subscription_id>/pause/",
        views.subscription_pause_view,
        name="subscription-pause",
    ),
    path(
        "subscriptions/<int:subscription_id>/resume/",
        views.subscription_resume_view,
        name="subscription-resume",
    ),
    path(
        "subscriptions/<int:subscription_id>/cancel/",
        views.subscription_cancel_view,
        name="subscription-cancel",
    ),

    path("subscriptions/", views.subscription_list_view, name="subscription-list"),
    path("subscriptions/new/", views.subscription_create_view, name="subscription-create"),
    path("subscriptions/<int:subscription_id>/pause/", views.subscription_pause_view, name="subscription-pause"),
    path("subscriptions/<int:subscription_id>/resume/", views.subscription_resume_view, name="subscription-resume"),
    path("subscriptions/<int:subscription_id>/cancel/", views.subscription_cancel_view, name="subscription-cancel"),
    path("gift-reminders/", views.gift_reminder_list_view, name="gift-reminders"),
    path("gift-reminders/add/", views.gift_reminder_create_view, name="gift-reminder-add"),
    path("gift-reminders/<int:reminder_id>/delete/", views.gift_reminder_delete_view, name="gift-reminder-delete"),
]
