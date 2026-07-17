"""URL routing for the checkout app."""

from __future__ import annotations

from django.urls import path

from checkout import views

app_name = "checkout"

urlpatterns = [
    path("", views.checkout_view, name="checkout"),
    path("place-order/", views.checkout_place_order_view, name="place-order"),
    path("update-session/", views.checkout_update_session_view, name="update-session"),
    path("add-address/", views.checkout_add_address_view, name="add-address"),
    
    path("addresses/<int:address_id>/form/", views.checkout_address_form_view, name="address-form"),
    path("addresses/<int:address_id>/edit/", views.checkout_edit_address_view, name="edit-address"),
    path("addresses/form/reset/", views.checkout_address_form_reset_view, name="address-form-reset"),
    path("addresses/<int:address_id>/delete/", views.checkout_delete_address_view, name="delete-address"),
    path("order/<int:order_id>/confirmation/",views.checkout_confirmation_view,name="confirmation"),
    path("preview-delivery/", views.checkout_preview_delivery_view, name="preview-delivery"),
]
