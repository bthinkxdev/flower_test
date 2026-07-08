"""HTTP views for the core app; thin request parsing delegating to selectors/services."""

from __future__ import annotations

import json

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils import translation
from django.views.decorators.http import require_POST

from core.page_rerender import is_htmx_request, rerender_app_shell


def health_view(request: HttpRequest) -> HttpResponse:
    """Return a simple 200 OK for load-balancer health probes."""
    return HttpResponse("ok", content_type="text/plain")


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
