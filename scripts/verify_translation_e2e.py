"""
End-to-end verification of the content translation pipeline.

Run: python scripts/verify_translation_e2e.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import timedelta
from typing import Any

# Ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "floward_clone.settings.dev")

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.utils import timezone, translation
from modeltranslation.translator import translator
from unittest.mock import patch

from catalog.models import (
    Brand,
    Category,
    Occasion,
    Product,
    ProductImage,
    ProductVariant,
    Recipient,
)
from cms.models import (
    BlogPost,
    FAQItem,
    HeroSlide,
    HomepageSection,
    HomepageSectionType,
    Page,
    PolicyDocument,
)
from core.models import ArTranslationSource
from core.services import get_site_settings
from core.translation.registry import (
    TRANSLATED_FIELDS,
    get_translated_fields,
    get_translated_json_fields,
    populate_registry,
)
from core.translation import signals as translation_signals
from delivery.models import City, Country, DeliverySlot, DeliveryZone
from gifting.models import (
    GiftPhotoUploadOption,
    GiftWrapOption,
    GreetingCardDesign,
    RibbonOption,
)
from marketing.models import FlashSale

SUFFIX = uuid.uuid4().hex[:8]
RESULTS: dict[str, str] = {}
SIGNAL_HITS: list[str] = []
ERRORS: list[str] = []


def _ok(name: str) -> None:
    RESULTS[name] = "PASS"
    print(f"  PASS  {name}")


def _fail(name: str, reason: str) -> None:
    RESULTS[name] = f"FAIL: {reason}"
    ERRORS.append(f"{name}: {reason}")
    print(f"  FAIL  {name} — {reason}")


def _tiny_png() -> SimpleUploadedFile:
    # 1x1 PNG
    data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return SimpleUploadedFile("verify.png", data, content_type="image/png")


def _has_ar_script(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def _assert_translated_fields(instance, field_names: list[str], label: str) -> None:
    instance.refresh_from_db()
    for field in field_names:
        en = getattr(instance, f"{field}_en", None)
        ar = getattr(instance, f"{field}_ar", None)
        if en in (None, ""):
            continue
        if ar in (None, ""):
            raise AssertionError(f"{label}.{field}_ar empty (en={en!r})")
        if not isinstance(ar, str):
            # JSON handled separately
            continue
        if ar == en and _has_ar_script(en) is False:
            # Same Latin text usually means translation did not run
            raise AssertionError(f"{label}.{field}_ar equals English ({ar!r})")
        if not _has_ar_script(ar):
            raise AssertionError(f"{label}.{field}_ar has no Arabic script: {ar!r}")


def _raw_columns(table: str, pk: int, columns: list[str]) -> dict[str, Any]:
    cols = ", ".join(columns)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {cols} FROM {table} WHERE id = %s", [pk])
        row = cursor.fetchone()
    return dict(zip(columns, row))


def _track_signal(sender, instance, **kwargs):
    if translation_signals.is_registered(sender):
        SIGNAL_HITS.append(sender.__name__)


def verify_modeltranslation_fields() -> None:
    print("\n=== 2. ModelTranslation field generation ===")
    populate_registry()
    missing = []
    for model, fields in TRANSLATED_FIELDS.items():
        opts = translator.get_options_for_model(model)
        registered = set(opts.fields) if opts else set()
        local = {f.name for f in model._meta.local_fields}
        for field in fields:
            if field not in registered:
                missing.append(f"{model.__name__}.{field} not in modeltranslation registry")
            if f"{field}_en" not in local:
                missing.append(f"{model.__name__}.{field}_en missing on model")
            if f"{field}_ar" not in local:
                missing.append(f"{model.__name__}.{field}_ar missing on model")
        for jf in get_translated_json_fields(model):
            if jf not in registered:
                missing.append(f"{model.__name__}.{jf} JSON not in modeltranslation")
            if f"{jf}_en" not in local or f"{jf}_ar" not in local:
                missing.append(f"{model.__name__}.{jf}_en/_ar missing")
    if missing:
        for m in missing:
            print(f"  FAIL  {m}")
        ERRORS.extend(missing)
        RESULTS["modeltranslation_fields"] = "FAIL"
    else:
        print(f"  PASS  All {len(TRANSLATED_FIELDS)} models have *_en/*_ar for registered fields")
        RESULTS["modeltranslation_fields"] = "PASS"


def verify_all_models_translate() -> dict[str, Any]:
    print("\n=== 3/4/9. Signal + translation + DB for every model ===")
    created: dict[str, Any] = {}
    translation.activate("en")

    # --- Catalog deps ---
    cat = Category.objects.create(
        name="Verify Category Flowers",
        slug=f"verify-cat-{SUFFIX}",
        meta_title="Verify Category Meta",
        meta_description="Verify category description text",
    )
    created["Category"] = cat
    occ = Occasion.objects.create(name="Verify Occasion Birthday", slug=f"verify-occ-{SUFFIX}")
    created["Occasion"] = occ
    brand = Brand.objects.create(name="Verify Brand Blooms", slug=f"verify-brand-{SUFFIX}")
    created["Brand"] = brand
    recip = Recipient.objects.create(name="Verify Recipient Mother", slug=f"verify-rec-{SUFFIX}")
    created["Recipient"] = recip
    product = Product.objects.create(
        name="Verify Red Roses Bouquet",
        slug=f"verify-prod-{SUFFIX}",
        sku=f"VR-{SUFFIX}",
        category=cat,
        primary_occasion=occ,
        brand=brand,
        base_price="100.00",
        color="Red",
        meta_title="Verify Product Meta Title",
        meta_description="Verify product meta description",
        stock_quantity=5,
    )
    created["Product"] = product
    variant = ProductVariant.objects.create(
        product=product,
        variant_type="size",
        name="Verify Large Size",
        sku_suffix=f"L{SUFFIX[:4]}",
        stock_quantity=2,
    )
    created["ProductVariant"] = variant
    image = ProductImage.objects.create(
        product=product,
        image=_tiny_png(),
        alt_text="Verify rose bouquet image",
        is_primary=True,
    )
    created["ProductImage"] = image

    # --- CMS ---
    section = HomepageSection.objects.create(
        section_type=HomepageSectionType.CORPORATE_GIFTS_BANNER,
        title="Verify Homepage Banner",
        config={"subtitle": "Corporate gifts made easy", "link_url": "https://example.com"},
        display_order=9999,
    )
    created["HomepageSection"] = section
    slide = HeroSlide.objects.create(title="Verify Hero Slide Title", display_order=9999)
    created["HeroSlide"] = slide
    blog = BlogPost.objects.create(
        title="Verify Blog Post About Flowers",
        slug=f"verify-blog-{SUFFIX}",
        body="This is a verify blog body about fresh flowers.",
        excerpt="Verify blog excerpt",
        meta_title="Verify Blog Meta",
        meta_description="Verify blog meta description",
        is_published=True,
    )
    created["BlogPost"] = blog
    page = Page.objects.create(
        title="Verify About Page",
        slug=f"verify-page-{SUFFIX}",
        body="Verify about page body content.",
        meta_title="Verify Page Meta",
        meta_description="Verify page meta description",
        is_published=True,
    )
    created["Page"] = page
    faq = FAQItem.objects.create(
        question="Verify how do I order flowers?",
        answer="Verify you can order flowers online easily.",
        display_order=9999,
        is_published=True,
    )
    created["FAQItem"] = faq
    policy = PolicyDocument.objects.create(
        title="Verify Privacy Policy",
        slug=f"verify-policy-{SUFFIX}",
        body="Verify privacy policy body text.",
        meta_title="Verify Policy Meta",
        meta_description="Verify policy meta description",
        policy_type="privacy",
        is_published=True,
    )
    created["PolicyDocument"] = policy

    # --- Gifting ---
    card = GreetingCardDesign.objects.create(
        name="Verify Greeting Card Design",
        occasion=occ,
        image=_tiny_png(),
    )
    created["GreetingCardDesign"] = card
    wrap = GiftWrapOption.objects.create(name=f"Verify Wrap {SUFFIX}", price_delta="5.00")
    created["GiftWrapOption"] = wrap
    ribbon = RibbonOption.objects.create(name=f"Verify Ribbon {SUFFIX}", price_delta="2.00")
    created["RibbonOption"] = ribbon
    photo = GiftPhotoUploadOption.objects.create(
        name="Verify Photo Upload Option", price_delta="10.00"
    )
    created["GiftPhotoUploadOption"] = photo

    # --- Delivery ---
    country_code = SUFFIX[:2].upper()
    country = Country.objects.create(name="Verify Country Qatar", code=country_code)
    created["Country"] = country
    city = City.objects.create(
        country=country,
        name="Verify City Doha",
        slug=f"verify-city-{SUFFIX}",
        delivery_charge_base="25.00",
    )
    created["City"] = city
    zone = DeliveryZone.objects.create(city=city, name="Verify Delivery Zone West")
    created["DeliveryZone"] = zone
    slot = DeliverySlot.objects.create(
        name="Verify Morning Slot",
        start_time="09:00",
        end_time="12:00",
        slot_type="morning",
    )
    created["DeliverySlot"] = slot

    # --- Marketing ---
    flash = FlashSale.objects.create(
        name="Verify Flash Sale Weekend",
        discount_percentage="10.00",
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=2),
    )
    flash.products.add(product)
    created["FlashSale"] = flash

    # --- Core SiteSettings (singleton update) ---
    settings_obj = get_site_settings()
    old_name = settings_obj.site_name_en or settings_obj.site_name
    settings_obj.ar_translation_source = ArTranslationSource.AUTO
    settings_obj.site_name = f"Verify Flowers {SUFFIX}"
    settings_obj.save()
    created["SiteSettings"] = settings_obj

    expected_models = [
        "Product",
        "Category",
        "Brand",
        "Occasion",
        "Recipient",
        "ProductVariant",
        "ProductImage",
        "HomepageSection",
        "HeroSlide",
        "BlogPost",
        "Page",
        "FAQItem",
        "PolicyDocument",
        "GreetingCardDesign",
        "GiftWrapOption",
        "RibbonOption",
        "GiftPhotoUploadOption",
        "Country",
        "City",
        "DeliveryZone",
        "DeliverySlot",
        "FlashSale",
        "SiteSettings",
    ]

    for name in expected_models:
        obj = created[name]
        try:
            if name not in SIGNAL_HITS and name != "SiteSettings":
                # SiteSettings save should still hit; signal records class name
                if obj.__class__.__name__ not in SIGNAL_HITS:
                    raise AssertionError(f"post_save signal did not fire for {name}")
            fields = get_translated_fields(obj.__class__)
            _assert_translated_fields(obj, fields, name)
            if name == "HomepageSection":
                obj.refresh_from_db()
                cfg_ar = obj.config_ar or {}
                sub = cfg_ar.get("subtitle", "")
                if not sub or not _has_ar_script(sub):
                    raise AssertionError(f"config_ar.subtitle not translated: {cfg_ar!r}")
                if cfg_ar.get("link_url") != "https://example.com":
                    raise AssertionError("JSON non-translatable key was altered")
            # DB raw check on primary text field
            primary = fields[0]
            table = obj._meta.db_table
            raw = _raw_columns(table, obj.pk, [f"{primary}_en", f"{primary}_ar"])
            if not raw[f"{primary}_en"]:
                raise AssertionError(f"DB {primary}_en empty")
            if not raw[f"{primary}_ar"] or not _has_ar_script(str(raw[f"{primary}_ar"])):
                raise AssertionError(f"DB {primary}_ar not Arabic: {raw}")
            _ok(name)
        except Exception as exc:
            _fail(name, str(exc))

    # restore site name somewhat
    settings_obj.site_name = old_name or "Floward"
    settings_obj.ar_translation_source = ArTranslationSource.AUTO
    settings_obj.save()

    return created


def verify_manual_lock(created: dict[str, Any]) -> None:
    print("\n=== 5. Manual translation lock ===")
    brand = created["Brand"]
    brand.refresh_from_db()
    locked_ar = brand.name_ar
    brand.ar_translation_source = ArTranslationSource.MANUAL
    brand.name = f"Verify Brand Manual Changed {SUFFIX}"
    brand.save()
    brand.refresh_from_db()
    if brand.name_ar != locked_ar:
        _fail("manual_lock", f"Arabic changed under MANUAL: {locked_ar!r} -> {brand.name_ar!r}")
    else:
        _ok("manual_lock")


def verify_failure_handling(created: dict[str, Any]) -> None:
    print("\n=== 6. Failure handling ===")
    brand = created["Brand"]
    brand.ar_translation_source = ArTranslationSource.AUTO
    brand.save(update_fields=["ar_translation_source"])
    brand.refresh_from_db()
    previous_ar = brand.name_ar
    with patch(
        "core.translation.service._get_translator"
    ) as mock_get:
        mock_get.return_value.translate.side_effect = RuntimeError("simulated translator down")
        brand.name = f"Verify Brand Failure {SUFFIX}"
        try:
            brand.save()
            save_ok = True
        except Exception as exc:
            save_ok = False
            _fail("failure_handling", f"save raised: {exc}")
            return
    brand.refresh_from_db()
    if not save_ok:
        return
    if brand.name_en != f"Verify Brand Failure {SUFFIX}" and brand.name != f"Verify Brand Failure {SUFFIX}":
        # name_en should hold English
        en = brand.name_en
        if en != f"Verify Brand Failure {SUFFIX}":
            _fail("failure_handling", f"English not preserved: {en!r}")
            return
    if brand.name_ar != previous_ar:
        _fail(
            "failure_handling",
            f"Arabic changed on failure: {previous_ar!r} -> {brand.name_ar!r}",
        )
        return
    _ok("failure_handling")


def verify_storefront_no_runtime_translation(created: dict[str, Any]) -> None:
    print("\n=== 7. Storefront: no runtime translation ===")
    client = Client()
    product = created["Product"]
    with patch("core.translation.service._get_translator") as mock_tr:
        mock_tr.return_value.translate.side_effect = AssertionError(
            "deep-translator must not be called from storefront"
        )
        # Also patch the module-level path used if translator already cached
        with patch("core.translation.service.GoogleTranslator") as mock_cls:
            mock_cls.return_value.translate.side_effect = AssertionError(
                "deep-translator must not be called from storefront"
            )
            with patch("core.translation.service._translator", None):
                with patch(
                    "core.translation.service._translate_text",
                    side_effect=AssertionError("storefront called _translate_text"),
                ):
                    r_en = client.get("/")
                    r_ar = client.get("/ar/")
                    # product PDP if route exists
                    try:
                        from django.urls import reverse

                        pdp = reverse("catalog:product-detail", kwargs={"slug": product.slug})
                    except Exception:
                        pdp = f"/products/{product.slug}/"
                    r_pdp_en = client.get(pdp)
                    r_pdp_ar = client.get(f"/ar{pdp}" if not pdp.startswith("/ar") else pdp)

    if r_en.status_code >= 500 or r_ar.status_code >= 500:
        _fail("storefront", f"pages errored en={r_en.status_code} ar={r_ar.status_code}")
        return

    # Language-specific field access without translator
    translation.activate("en")
    product.refresh_from_db()
    en_name = product.name
    translation.activate("ar")
    ar_name = product.name
    translation.activate("en")
    if en_name != product.name_en:
        _fail("storefront", f"EN locale name mismatch: {en_name!r} vs {product.name_en!r}")
        return
    if ar_name != product.name_ar:
        _fail("storefront", f"AR locale name mismatch: {ar_name!r} vs {product.name_ar!r}")
        return
    if en_name == ar_name:
        _fail("storefront", "EN and AR display names are identical")
        return
    _ok("storefront")
    print(f"         EN name={en_name!r}")
    print(f"         AR name has Arabic script={_has_ar_script(ar_name)} len={len(ar_name)}")
    print(
        f"         homepage en={r_en.status_code} ar={r_ar.status_code} "
        f"pdp_en={r_pdp_en.status_code} pdp_ar={r_pdp_ar.status_code}"
    )


def verify_legacy() -> None:
    print("\n=== 8. Legacy / duplicate translation code ===")
    import pathlib
    import re

    root = pathlib.Path(ROOT)
    skip = {
        ".git",
        "venv",
        ".venv",
        "node_modules",
        "__pycache__",
        "migrations",
        "locale",
        "scripts",
        "dashboard",
    }
    offenders: list[str] = []
    allowed_translator = {str(root / "core" / "translation" / "service.py")}

    for path in root.rglob("*.py"):
        if any(part in skip for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = str(path.relative_to(root))

        if path.name == "tasks.py" and re.search(r"translat", text, re.I):
            offenders.append(f"{rel}: translation referenced in Celery tasks")

        if re.search(r"GoogleTranslator|deep_translator|from deep_translator", text):
            if str(path) not in allowed_translator:
                offenders.append(f"{rel}: translator import outside service.py")

        if re.search(r"on_commit", text) and re.search(r"translat", text, re.I):
            offenders.append(f"{rel}: on_commit + translation")

        if re.search(r"threading\.(Thread|Timer)", text) and re.search(
            r"translat", text, re.I
        ):
            offenders.append(f"{rel}: thread + translation")

        if path.name in {"admin.py", "views.py", "forms.py"} and re.search(
            r"GoogleTranslator|deep_translator|translate_and_save|_translate_text",
            text,
        ):
            offenders.append(f"{rel}: translation logic in {path.name}")

        if re.search(r"^def translate_and_save\b", text, re.M):
            if path.as_posix() != "core/translation/service.py":
                offenders.append(f"{rel}: duplicate translate_and_save definition")

    if offenders:
        for o in offenders:
            print(f"  FAIL  {o}")
        RESULTS["legacy"] = "FAIL"
        ERRORS.extend(offenders)
    else:
        _ok("legacy")


def cleanup(created: dict[str, Any]) -> None:
    print("\n=== Cleanup test records ===")
    # Delete in FK-safe order
    order = [
        "ProductImage",
        "ProductVariant",
        "FlashSale",
        "GiftPhotoUploadOption",
        "RibbonOption",
        "GiftWrapOption",
        "GreetingCardDesign",
        "Product",
        "Recipient",
        "Brand",
        "HomepageSection",
        "HeroSlide",
        "BlogPost",
        "Page",
        "FAQItem",
        "PolicyDocument",
        "DeliverySlot",
        "DeliveryZone",
        "City",
        "Country",
        "Occasion",
        "Category",
    ]
    for name in order:
        obj = created.get(name)
        if not obj:
            continue
        try:
            if name == "FlashSale":
                obj.products.clear()
            obj.delete()
        except Exception as exc:
            print(f"  cleanup warn {name}: {exc}")


def main() -> int:
    print("=== 1. Project health (invoked separately; assuming check/migrate done) ===")
    from django.core.management import call_command
    from io import StringIO

    err = StringIO()
    call_command("check", stdout=StringIO(), stderr=err)
    check_err = err.getvalue()
    if check_err.strip():
        _fail("django_check", check_err)
    else:
        _ok("django_check")

    out = StringIO()
    try:
        call_command("makemigrations", dry_run=True, check=True, stdout=out, stderr=out)
        _ok("makemigrations_clean")
    except SystemExit as e:
        if e.code not in (0, None):
            _fail("makemigrations_clean", out.getvalue() or str(e))
        else:
            _ok("makemigrations_clean")
    except Exception as exc:
        # Django raises CommandError when changes detected with --check
        msg = str(exc)
        if "No changes detected" in msg or not msg:
            _ok("makemigrations_clean")
        else:
            _fail("makemigrations_clean", msg)

    call_command("migrate", interactive=False, run_syncdb=False, stdout=StringIO())
    _ok("migrate")

    # Probe runserver
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=5) as resp:
            if resp.status == 200:
                _ok("runserver")
            else:
                _fail("runserver", f"status {resp.status}")
    except Exception as exc:
        _fail("runserver", str(exc))

    verify_modeltranslation_fields()

    from django.db.models.signals import post_save

    post_save.connect(_track_signal)
    created: dict[str, Any] = {}
    try:
        created = verify_all_models_translate()
        verify_manual_lock(created)
        verify_failure_handling(created)
        verify_storefront_no_runtime_translation(created)
        verify_legacy()
    finally:
        post_save.disconnect(_track_signal)
        if created:
            cleanup(created)

    print("\n=== FINAL SCORECARD ===")
    model_names = [
        "Product",
        "Category",
        "Brand",
        "Occasion",
        "Recipient",
        "ProductVariant",
        "ProductImage",
        "HomepageSection",
        "HeroSlide",
        "BlogPost",
        "Page",
        "FAQItem",
        "PolicyDocument",
        "GreetingCardDesign",
        "GiftWrapOption",
        "RibbonOption",
        "GiftPhotoUploadOption",
        "Country",
        "City",
        "DeliveryZone",
        "DeliverySlot",
        "FlashSale",
        "SiteSettings",
    ]
    for m in model_names:
        print(f"  {m}: {RESULTS.get(m, 'FAIL: not run')}")
    for key in [
        "django_check",
        "makemigrations_clean",
        "migrate",
        "runserver",
        "modeltranslation_fields",
        "manual_lock",
        "failure_handling",
        "storefront",
        "legacy",
    ]:
        print(f"  {key}: {RESULTS.get(key, 'FAIL: not run')}")

    failed = [k for k, v in RESULTS.items() if not str(v).startswith("PASS")]
    print(f"\nSignal hits ({len(SIGNAL_HITS)}): {sorted(set(SIGNAL_HITS))}")
    if failed:
        print(f"\nFAILED ITEMS ({len(failed)}): {failed}")
        for e in ERRORS:
            print(f"  - {e}")
        return 1
    print("\nALL VERIFICATIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
