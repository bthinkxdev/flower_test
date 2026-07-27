"""Verify Arabic static UI on key storefront pages."""

from __future__ import annotations

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "floward_clone.settings.dev")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.test import Client

from catalog.models import Product


def check(name: str, path: str, ar_needles: list[str], en_forbidden: list[str], client: Client) -> None:
    resp = client.get(path, follow=True)
    body = resp.content.decode("utf-8", "ignore")
    ok = resp.status_code < 400
    missing = [n for n in ar_needles if n not in body]
    leaked = [n for n in en_forbidden if n in body]
    # Auth-gated pages may land on login — still require Arabic shell
    if "تسجيل الدخول" in body and name in {"Wishlist", "Subscriptions", "Gift calendar"}:
        missing = [n for n in missing if n not in {"قائمة أمنياتي", "اشتراكاتي", "تقويم الهدايا"}]
    status = "PASS" if ok and not missing and not leaked else "FAIL"
    print(f"{status} {name} [{resp.status_code}] {path}")
    if missing:
        print(f"  missing AR: {missing}")
    if leaked:
        print(f"  EN leaked: {leaked}")


def main() -> None:
    product = (
        Product.objects.filter(is_active=True)
        .exclude(name_en="")
        .exclude(name_en__isnull=True)
        .first()
    )
    slug = product.slug if product else "luxury-arrangement-2"

    client = Client()
    # Establish Arabic via language switch redirect target
    r = client.post(
        "/preferences/language/",
        {"language": "ar"},
        HTTP_HX_REQUEST="true",
        HTTP_HX_CURRENT_URL="http://testserver/",
    )
    assert r["HX-Redirect"] == "/ar/"

    pages = [
        ("Homepage", "/ar/", ["قصة الزهور", "توصيل سريع", "تسوق حسب المناسبة"], ["Express Delivery"]),
        ("PLP", "/ar/shop/", ["التصفية", "تسوق الكل", "تطبيق"], ["Clear Filters"]),
        ("PDP", f"/ar/shop/products/{slug}/", ["أضف إلى السلة", "تقدير التوصيل"], []),
        ("Cart", "/ar/cart/", ["السلة"], []),
        ("Login", "/accounts/login/", ["تسجيل الدخول", "قصة الزهور"], []),
        ("Wishlist", "/accounts/wishlist/", ["قائمة أمنياتي", "قصة الزهور"], []),
        ("About", "/about-us/", ["من نحن", "قصة الزهور"], []),
        ("FAQ", "/faq/", ["الأسئلة الشائعة"], []),
        ("Contact", "/contact-us/", ["اتصل بنا"], []),
        ("Blog", "/blog/", ["المدونة"], []),
        ("Privacy", "/privacy-policy/", ["سياسة الخصوصية"], []),
        ("Subscriptions", "/accounts/subscriptions/", ["اشتراكاتي", "قصة الزهور"], []),
        ("Gift calendar", "/accounts/gift-reminders/", ["تقويم الهدايا", "قصة الزهور"], []),
        ("Corporate register", "/accounts/corporate/register/", ["تسجيل الشركات"], []),
        ("Quote", "/ar/corporate/quote/new/", ["تسجيل الدخول"], []),
    ]

    for name, path, ar_needles, en_forbidden in pages:
        check(name, path, ar_needles, en_forbidden, client)

    # English still works
    client.post(
        "/preferences/language/",
        {"language": "en"},
        HTTP_HX_REQUEST="true",
        HTTP_HX_CURRENT_URL="http://testserver/ar/",
    )
    en = client.get("/").content.decode("utf-8", "ignore")
    print("PASS English homepage" if "Express Delivery" in en else "FAIL English homepage")


if __name__ == "__main__":
    main()
