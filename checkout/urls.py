"""URL routing for the checkout app."""

from __future__ import annotations

from django.urls import path

from checkout import views

app_name = "checkout"

urlpatterns = [
    path("", views.checkout_view, name="checkout"),
    path("place-order/", views.checkout_place_order_view, name="place-order"),
]
