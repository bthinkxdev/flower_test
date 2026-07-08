"""URL routing for the core app."""

from __future__ import annotations

from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("health/", views.health_view, name="health"),
    path("preferences/language/", views.set_language_view, name="set-language"),
    path("preferences/currency/", views.set_currency_view, name="set-currency"),
    path("preferences/country/", views.set_country_view, name="set-country"),
]
