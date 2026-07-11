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
    path("about-us/", views.about_us_view, name="about-us"),
    path("privacy-policy/", views.privacy_policy_view, name="privacy-policy"),
    path("contact-us/", views.contact_us_view, name="contact-us"),
    path("faq/", views.faq_view, name="faq"),
]
