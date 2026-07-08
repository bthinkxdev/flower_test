"""URL routing for the gifting app."""

from __future__ import annotations

from django.urls import path

from gifting import views

app_name = "gifting"

urlpatterns = [
    path("products/<slug:slug>/builder/", views.gift_builder_view, name="builder"),
    path(
        "builder/<int:line_item_id>/preview/",
        views.gift_builder_preview_view,
        name="builder-preview",
    ),
    path(
        "builder/message-preview/",
        views.gift_message_preview_view,
        name="message-preview",
    ),
]
