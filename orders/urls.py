"""URL routing for the orders app."""

from __future__ import annotations

from django.urls import path

from orders import views

app_name = "orders"

urlpatterns = [
    path("<int:order_id>/tracking/", views.order_tracking_view, name="tracking"),
]
