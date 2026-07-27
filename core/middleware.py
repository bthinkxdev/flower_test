"""Locale middleware that respects cookie/session on non-i18n storefront routes."""

from __future__ import annotations

from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation

from core.i18n_urls import is_i18n_storefront_path, strip_language_prefix


class StorefrontLocaleMiddleware(LocaleMiddleware):
    """
    Django's LocaleMiddleware with ``prefix_default_language=False`` forces
    ``LANGUAGE_CODE`` on every path that lacks a language prefix — including
    routes outside ``i18n_patterns`` (accounts, about, FAQ, etc.).

    For those non-prefixed *non-i18n* routes, honor the session/cookie language
    so static UI translations still switch with the header toggle.
    Prefixed i18n routes (``/`` vs ``/ar/``) keep Django's URL-based behavior.
    """

    def process_request(self, request):
        super().process_request(request)

        language_from_path = translation.get_language_from_path(request.path_info)
        if language_from_path:
            return

        path = strip_language_prefix(request.path_info or "/")
        if is_i18n_storefront_path(path):
            return

        lang = request.session.get("django_language") or request.COOKIES.get(
            settings.LANGUAGE_COOKIE_NAME
        )
        supported = {code for code, _label in settings.LANGUAGES}
        if lang in supported:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
