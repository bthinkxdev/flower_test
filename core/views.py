"""HTTP views for the core app; thin request parsing delegating to selectors/services."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods

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
        title=_("About Us | Story of Flowers"),
        description=_("Learn more about Story of Flowers and our mission to deliver flowers and gifts."),
    )
    return render(request, "core/about_us.html", context)


@require_GET
def privacy_policy_view(request: HttpRequest) -> HttpResponse:
    """Render the static Privacy Policy page."""
    context = seo_context(
        request=request,
        title=_("Privacy Policy | Story of Flowers"),
        description=_("Read Story of Flower's privacy policy to learn how we collect and use your data."),
    )
    return render(request, "core/privacy_policy.html", context)


@require_http_methods(["GET", "POST"])
def contact_us_view(request: HttpRequest) -> HttpResponse:
    """Render the Contact Us page and handle message submissions."""
    from core.forms import ContactForm

    submitted = False
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            submitted = True
            form = ContactForm()
    else:
        form = ContactForm()

    context = seo_context(
        request=request,
        title=_("Contact Us | Story of Flowers"),
        description=_("Get in touch with Story of Flowers customer support."),
    )
    context["form"] = form
    context["submitted"] = submitted
    return render(request, "core/contact_us.html", context)


@require_GET
def faq_view(request: HttpRequest) -> HttpResponse:
    """Render the dynamic FAQ page."""
    from cms.models import FAQItem
    faqs = FAQItem.objects.filter(is_published=True).order_by("display_order")

    context = seo_context(
        request=request,
        title=_("FAQ | Story of Flowers"),
        description=_("Frequently asked questions about ordering, delivery, and payments at Story of Flowers."),
    )
    context["faqs"] = faqs
    return render(request, "core/faq.html", context)


@require_GET
def blog_list_view(request: HttpRequest) -> HttpResponse:
    """Render the blog list page."""
    from cms.models import BlogPost
    posts = BlogPost.objects.filter(is_published=True).order_by("-publish_at", "-created_at")

    context = seo_context(
        request=request,
        title=_("Blog | Story of Flowers"),
        description=_("Read the latest news, tips, and stories from Story of Flowers."),
    )
    context["posts"] = posts
    return render(request, "core/blog.html", context)


@require_POST
def set_language_view(request: HttpRequest) -> HttpResponse:
    """
    Persist language choice and navigate to the matching localized URL.

    With ``prefix_default_language=False``, Arabic pages live under ``/ar/...``.
    Session/cookie alone are not enough on reload of ``/`` because
    LocaleMiddleware treats the bare path as English. Redirecting to the
    translated path keeps language stable across reloads.
    """
    from urllib.parse import urlparse

    from core.i18n_urls import localize_storefront_path

    language = request.POST.get("language", "en")
    if language not in ("en", "ar"):
        if is_htmx_request(request):
            return HttpResponse("Invalid language", status=400)
        return redirect("/")

    raw = request.headers.get("HX-Current-URL") or request.META.get("HTTP_REFERER") or "/"
    parsed = urlparse(raw)
    path = parsed.path or "/"
    localized = localize_storefront_path(path, language)
    target = f"{localized}?{parsed.query}" if parsed.query else localized

    request.session["django_language"] = language
    translation.activate(language)

    if is_htmx_request(request):
        # Full navigation so the address bar matches the active language.
        response = HttpResponse(status=204)
        response["HX-Redirect"] = target
    else:
        response = redirect(target)

    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
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
