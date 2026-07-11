"""HTTP views for the core app; thin request parsing delegating to selectors/services."""

from __future__ import annotations

import json

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from core.page_rerender import is_htmx_request, rerender_app_shell
from core.seo import seo_context


def health_view(request: HttpRequest) -> HttpResponse:
    """Return a simple 200 OK for load-balancer health probes."""
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def about_us_view(request: HttpRequest) -> HttpResponse:
    """Render the static About Us page."""
    context = seo_context(
        request=request,
        title=_("About Us | Floward Qatar"),
        description=_("Learn more about Floward Qatar and our mission to deliver flowers and gifts."),
    )
    return render(request, "core/about_us.html", context)


@require_GET
def privacy_policy_view(request: HttpRequest) -> HttpResponse:
    """Render the static Privacy Policy page."""
    context = seo_context(
        request=request,
        title=_("Privacy Policy | Floward Qatar"),
        description=_("Read Floward Qatar's privacy policy to learn how we collect and use your data."),
    )
    return render(request, "core/privacy_policy.html", context)


@require_GET
def contact_us_view(request: HttpRequest) -> HttpResponse:
    """Render the static Contact Us page."""
    context = seo_context(
        request=request,
        title=_("Contact Us | Floward Qatar"),
        description=_("Get in touch with Floward Qatar customer support."),
    )
    return render(request, "core/contact_us.html", context)


@require_GET
def faq_view(request: HttpRequest) -> HttpResponse:
    """Render the static FAQ page."""
    context = seo_context(
        request=request,
        title=_("FAQ | Floward Qatar"),
        description=_("Frequently asked questions about ordering, delivery, and payments at Floward Qatar."),
    )
    return render(request, "core/faq.html", context)


@require_POST
def set_language_view(request: HttpRequest) -> HttpResponse:
    """Persist language choice to session and activate translation."""
    language = request.POST.get("language", "en")
    if language not in ("en", "ar"):
        if is_htmx_request(request):
            return HttpResponse("Invalid language", status=400)
        return redirect("/")

    request.session["django_language"] = language
    translation.activate(language)

    if not is_htmx_request(request):
        response = redirect(request.META.get("HTTP_REFERER", "/"))
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
        return response

    response = rerender_app_shell(request)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
    response["HX-Trigger"] = json.dumps(
        {
            "preferencesUpdated": {
                "lang": language,
                "dir": "rtl" if language == "ar" else "ltr",
            }
        }
    )
    return response


@require_POST
def set_currency_view(request: HttpRequest) -> HttpResponse:
    """Persist currency code to session."""
    code = request.POST.get("currency", "QAR")
    request.session["storefront_currency"] = code

    if not is_htmx_request(request):
        return redirect(request.META.get("HTTP_REFERER", "/"))

    return rerender_app_shell(request)


@require_POST
def set_country_view(request: HttpRequest) -> HttpResponse:
    """Persist the delivery country choice to session."""
    code = request.POST.get("country", "").strip().upper()
    request.session["storefront_country"] = code

    if not is_htmx_request(request):
        return redirect(request.META.get("HTTP_REFERER", "/"))

    return rerender_app_shell(request)
