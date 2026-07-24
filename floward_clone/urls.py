"""Root URL configuration for floward_clone."""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import index, sitemap
from django.urls import include, path

from core.sitemaps import (
    BlogPostSitemap,
    CategorySitemap,
    OccasionSitemap,
    PageSitemap,
    ProductSitemap,
)

sitemaps = {
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "occasions": OccasionSitemap,
    "blog": BlogPostSitemap,
    "pages": PageSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", index, {"sitemaps": sitemaps}, name="sitemap-index"),
    path(
        "sitemap-<section>.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("marketing/", include("marketing.urls")),
]

urlpatterns += i18n_patterns(
    path("", include("cms.urls")),
    path("shop/", include("catalog.urls")),
    path("gifting/", include("gifting.urls")),
    path("cart/", include("cart.urls")),
    path("checkout/", include("checkout.urls")),
    path("orders/", include("orders.urls")),
    path("corporate/", include("corporate.urls")),
    prefix_default_language=False,
)

urlpatterns += [
    path("payments/", include("payments.urls")),
    path("reports/", include("reports.urls")),
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    try:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
