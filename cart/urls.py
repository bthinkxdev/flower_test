"""URL routing for the cart app."""

from __future__ import annotations

from django.urls import path

from cart import views

app_name = "cart"

urlpatterns = [
    path("drawer/", views.cart_drawer_view, name="drawer"),
    path("count/", views.cart_count_view, name="count"),
    path("add/", views.cart_add_view, name="add"),
    path("remove/", views.cart_remove_view, name="remove"),
    path("wishlist/toggle/", views.wishlist_toggle_view, name="wishlist-toggle"),
]
