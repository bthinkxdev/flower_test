"""Import Story of Flowers catalog from Excel mapping JSON into Django models."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.signals import post_save
from django.utils.text import slugify

from catalog.import_mapping import (
    DEFAULT_MAP_JSON,
    DEFAULT_MEDIA,
    load_mapping_json,
    write_mapping_json,
)
from catalog.models import Brand, Category, Occasion, Product, ProductImage
from catalog.taxonomy import sync_story_of_flowers_taxonomy
from core.models import ArTranslationSource
from core.translation.signals import on_registered_model_saved
from gifting.models import GiftAddonEligibility


class Command(BaseCommand):
    help = (
        "Import Story of Flowers products from the mapping JSON "
        "(regenerates JSON from Excel unless --map is provided)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--map", type=str, default="", help="Path to mapping JSON.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-no-image", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--refresh-map", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument(
            "--create-greeting-card-addon",
            action="store_true",
            default=True,
        )
        parser.add_argument(
            "--no-create-greeting-card-addon",
            action="store_false",
            dest="create_greeting_card_addon",
        )

    def handle(self, *args, **options):
        map_path = Path(options["map"]) if options["map"] else DEFAULT_MAP_JSON
        if options["refresh_map"] or not map_path.exists():
            self.stdout.write("Regenerating mapping JSON from Excel...")
            map_path = write_mapping_json(out_path=map_path)
        else:
            self.stdout.write(f"Using existing map: {map_path}")

        report = load_mapping_json(map_path)
        products = report.get("products") or []
        if len(products) != 1212:
            self.stdout.write(
                self.style.WARNING(f"Expected 1212 products in map, found {len(products)}.")
            )
        if options["limit"]:
            products = products[: options["limit"]]

        summary = report.get("summary") or {}
        self.stdout.write(
            f"Map: {map_path} | products={len(products)} "
            f"| matched_any={summary.get('matched_any')} "
            f"| rate={summary.get('match_rate_pct')}%"
        )

        if options["dry_run"]:
            status_counts: dict[str, int] = {}
            for p in products:
                key = p.get("status", "?")
                status_counts[key] = status_counts.get(key, 0) + 1
            self.stdout.write(self.style.SUCCESS(f"Dry-run OK. statuses={status_counts}"))
            return

        media_root = Path(report.get("media_root") or DEFAULT_MEDIA)
        if not media_root.exists():
            raise CommandError(f"Media root not found: {media_root}")

        # Excel already includes Arabic — do not call Google Translate per row.
        post_save.disconnect(on_registered_model_saved)
        try:
            self._run_import(products, report, media_root, options)
        finally:
            post_save.connect(on_registered_model_saved)

    def _run_import(self, products, report, media_root, options):
        brand = self._ensure_brand()
        occasion_cache = self._ensure_occasions(products)
        category_cache = self._ensure_categories(report, products)

        created = updated = images_attached = skipped = 0
        addon_product = None
        if options["create_greeting_card_addon"]:
            addon_product = self._ensure_greeting_card_addon(brand, occasion_cache)

        product_ct = ContentType.objects.get_for_model(Product)
        used_slugs: set[str] = set(Product.objects.values_list("slug", flat=True))
        batch_size = max(1, options["batch_size"])
        batch: list[dict] = []

        def flush(batch_items: list[dict]) -> None:
            nonlocal created, updated, images_attached, skipped
            with transaction.atomic():
                for item in batch_items:
                    if options["skip_no_image"] and item.get("status") == "no_image":
                        skipped += 1
                        continue
                    if item.get("price") is None:
                        skipped += 1
                        continue

                    category = category_cache[item["canonical_category_en"]]
                    occasion = occasion_cache[item["occasion_slug"]]
                    slug = self._unique_slug(item["name_en"], item["sku"], used_slugs)
                    used_slugs.add(slug)

                    defaults = {
                        "name": item["name_en"],
                        "name_en": item["name_en"],
                        "name_ar": item["name_ar"] or item["name_en"],
                        "description": item.get("desc_en") or "",
                        "description_en": item.get("desc_en") or "",
                        "description_ar": item.get("desc_ar") or "",
                        "slug": slug,
                        "category": category,
                        "primary_occasion": occasion,
                        "brand": brand,
                        "base_price": Decimal(str(item["price"])),
                        "preparation_minutes": item.get("preparation_minutes"),
                        "is_active": True,
                        "is_same_day_eligible": bool(
                            item.get("preparation_minutes") is not None
                            and int(item["preparation_minutes"]) <= 60
                        ),
                        "supports_gift_customization": True,
                        "stock_quantity": 100,
                        "ar_translation_source": ArTranslationSource.MANUAL,
                        "meta_title": (item["name_en"] or "")[:70],
                        "meta_title_en": (item["name_en"] or "")[:70],
                        "meta_title_ar": (item.get("name_ar") or item["name_en"] or "")[:70],
                        "meta_description": (item.get("desc_en") or "")[:160],
                        "meta_description_en": (item.get("desc_en") or "")[:160],
                        "meta_description_ar": (item.get("desc_ar") or "")[:160],
                    }

                    product, was_created = Product.objects.update_or_create(
                        sku=item["sku"],
                        defaults=defaults,
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

                    images_attached += self._attach_images(product, item, media_root)

                    if addon_product and item.get("addon_en"):
                        GiftAddonEligibility.objects.get_or_create(
                            content_type=product_ct,
                            object_id=product.pk,
                            addon_product=addon_product,
                        )

        total = len(products)
        for idx, item in enumerate(products, start=1):
            batch.append(item)
            if len(batch) >= batch_size:
                flush(batch)
                batch = []
                self.stdout.write(
                    f"  progress {idx}/{total} (created={created} updated={updated})"
                )

        if batch:
            flush(batch)

        taxonomy_result = sync_story_of_flowers_taxonomy()
        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: created={created} updated={updated} "
                f"images={images_attached} skipped={skipped}"
            )
        )
        self.stdout.write(
            f"DB totals: categories={Category.objects.count()} "
            f"products={Product.objects.count()} "
            f"images={ProductImage.objects.count()}"
        )
        self.stdout.write(
            "Taxonomy: "
            f"parents={taxonomy_result['parent_count']} "
            f"collections={taxonomy_result['collections_assigned']}"
        )

    def _ensure_brand(self) -> Brand:
        brand, _ = Brand.objects.get_or_create(
            slug="story-of-flowers",
            defaults={
                "name": "Story of Flowers",
                "name_en": "Story of Flowers",
                "name_ar": "قصة الزهور",
                "is_featured": True,
                "ar_translation_source": ArTranslationSource.MANUAL,
            },
        )
        return brand

    def _ensure_occasions(self, products: list[dict]) -> dict[str, Occasion]:
        cache: dict[str, Occasion] = {}
        seasonal = {
            "eid",
            "eid-al-adha",
            "ramadan",
            "valentines",
            "mothers-day",
            "fathers-day",
            "teachers-day",
            "garangao",
        }
        for item in products:
            slug = item["occasion_slug"]
            if slug in cache:
                continue
            name = item.get("occasion_name_en") or slug.replace("-", " ").title()
            obj, created = Occasion.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "name_en": name,
                    "name_ar": name,
                    "ar_translation_source": ArTranslationSource.MANUAL,
                    "is_seasonal": slug in seasonal,
                },
            )
            if not created and not obj.name_en:
                obj.name_en = name
                obj.save(update_fields=["name_en", "updated_at"])
            cache[slug] = obj
        return cache

    def _ensure_categories(self, report: dict, products: list[dict]) -> dict[str, Category]:
        categories_meta = report.get("categories") or {}
        cache: dict[str, Category] = {}
        order = 0
        seen: list[str] = []
        for item in products:
            name_en = item["canonical_category_en"]
            if name_en not in seen:
                seen.append(name_en)

        for name_en in seen:
            order += 10
            meta = categories_meta.get(name_en) or {}
            name_ar = meta.get("name_ar") or name_en
            for item in products:
                if item["canonical_category_en"] == name_en and item.get("category_ar"):
                    name_ar = item["category_ar"]
                    break
            slug = slugify(name_en)[:120] or f"category-{order}"
            obj, created = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name_en,
                    "name_en": name_en,
                    "name_ar": name_ar,
                    "display_order": order,
                    "is_active": True,
                    "ar_translation_source": ArTranslationSource.MANUAL,
                    "meta_title": name_en[:70],
                    "meta_title_en": name_en[:70],
                    "meta_title_ar": name_ar[:70],
                },
            )
            if not created:
                obj.name = name_en
                obj.name_en = name_en
                obj.name_ar = name_ar
                obj.display_order = order
                obj.is_active = True
                obj.ar_translation_source = ArTranslationSource.MANUAL
                obj.save()
            cache[name_en] = obj
        return cache

    def _ensure_greeting_card_addon(
        self, brand: Brand, occasion_cache: dict[str, Occasion]
    ) -> Product:
        occasion = next(iter(occasion_cache.values()))
        category, _ = Category.objects.get_or_create(
            slug="add-ons",
            defaults={
                "name": "Add-ons",
                "name_en": "Add-ons",
                "name_ar": "إضافات",
                "display_order": 9990,
                "is_active": True,
                "ar_translation_source": ArTranslationSource.MANUAL,
            },
        )
        product, _ = Product.objects.update_or_create(
            sku="SOF-ADDON-GREETING-CARD",
            defaults={
                "name": "Greeting Card",
                "name_en": "Greeting Card",
                "name_ar": "بطاقة تهنئة",
                "description": "A greeting card add-on for your gift.",
                "description_en": "A greeting card add-on for your gift.",
                "description_ar": "بطاقة تهنئة لإضافتها إلى هديتك.",
                "slug": "greeting-card-addon",
                "category": category,
                "primary_occasion": occasion,
                "brand": brand,
                "base_price": Decimal("15.00"),
                "preparation_minutes": 0,
                "is_active": True,
                "supports_gift_customization": False,
                "stock_quantity": 9999,
                "ar_translation_source": ArTranslationSource.MANUAL,
            },
        )
        return product

    def _unique_slug(self, name_en: str, sku: str, used: set[str]) -> str:
        base = slugify(name_en)[:200] or slugify(sku) or "product"
        sku_tail = re.sub(r"[^a-z0-9]+", "-", sku.lower()).strip("-")
        candidate = f"{base}-{sku_tail}"[:255]
        if candidate not in used and not Product.objects.filter(slug=candidate).exclude(sku=sku).exists():
            return candidate
        n = 2
        while True:
            candidate = f"{base}-{sku_tail}-{n}"[:255]
            if candidate not in used and not Product.objects.filter(slug=candidate).exclude(sku=sku).exists():
                return candidate
            n += 1

    def _attach_images(self, product: Product, item: dict, media_root: Path) -> int:
        """Point ImageField at existing files under media/products/ (no re-copy)."""
        rels = item.get("image_relpaths") or []
        if not rels:
            return 0

        product.images.all().delete()
        settings_media = Path(settings.MEDIA_ROOT).resolve()
        attached = 0
        for idx, rel in enumerate(rels[:5]):
            src = (media_root / Path(rel)).resolve()
            if not src.exists():
                self.stdout.write(
                    self.style.WARNING(f"Missing image for {product.sku}: {rel}")
                )
                continue
            try:
                relative_to_media = src.relative_to(settings_media).as_posix()
            except ValueError:
                self.stdout.write(
                    self.style.WARNING(f"Image outside MEDIA_ROOT for {product.sku}: {src}")
                )
                continue
            image = ProductImage(
                product=product,
                alt_text=product.name_en or product.name,
                alt_text_en=product.name_en or product.name,
                alt_text_ar=product.name_ar or product.name,
                display_order=idx,
                is_primary=(idx == 0),
                ar_translation_source=ArTranslationSource.MANUAL,
            )
            image.image.name = relative_to_media
            image.save()
            attached += 1
        return attached
