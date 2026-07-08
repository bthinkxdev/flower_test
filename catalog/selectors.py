"""Read-only query functions for the catalog app; views must not call the ORM directly."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Avg, Prefetch, Q, QuerySet

from catalog.models import (
    ModerationStatus,
    Product,
    ProductImage,
    ProductRelation,
    ProductVariant,
    ProductVideo,
    RelationType,
    Review,
    ReviewPhoto,
)

PLP_CARD_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "slug",
    "sku",
    "base_price",
    "color",
    "is_same_day_eligible",
    "is_bestseller",
    "is_new_arrival",
    "stock_quantity",
    "category_id",
    "brand_id",
    "primary_occasion_id",
)

HOMEPAGE_RAIL_LIMIT = 12
CATEGORY_TREE_CACHE_KEY = "catalog:category_tree:v1"
CATEGORY_TREE_TTL = 300
DEFAULT_CURRENCY_CACHE_KEY = "core:default_currency:v1"
DEFAULT_CURRENCY_TTL = 300


def get_product_display_price(*, product: Product) -> Decimal:
    """Return flash-sale-adjusted display price for PLP cards."""
    from marketing.selectors import get_active_flash_sale_price

    sale = get_active_flash_sale_price(product_id=product.pk, base_price=product.base_price)
    return sale["price"]


def _primary_image_prefetch() -> Prefetch:
    """
    Prefetch only the primary image per product — not the full gallery.

    Used by homepage rails and PLP to avoid loading all ProductImage rows.
    """
    return Prefetch(
        "images",
        queryset=ProductImage.objects.filter(is_primary=True).order_by("display_order"),
        to_attr="primary_images",
    )


def _homepage_rail_queryset(*, filters: Q) -> QuerySet[Product]:
    """Base queryset for a single homepage rail with shared optimizations."""
    return (
        Product.objects.filter(is_active=True)
        .filter(filters)
        .select_related("category", "brand")
        .prefetch_related(_primary_image_prefetch())
        .only(*PLP_CARD_FIELDS)
        .order_by("-created_at")[:HOMEPAGE_RAIL_LIMIT]
    )


def get_homepage_product_rails() -> dict[str, list[Product]]:
    """
    Return homepage merchandising rails keyed by rail name.

    Query guarantee: exactly 6 DB queries total (3 rails × 2 queries each) —
      trending/bestsellers share one evaluated bestseller rail.
    """
    bestseller_rail = list(_homepage_rail_queryset(filters=Q(is_bestseller=True)))
    new_arrivals = list(_homepage_rail_queryset(filters=Q(is_new_arrival=True)))
    same_day = list(_homepage_rail_queryset(filters=Q(is_same_day_eligible=True)))
    return {
        "trending": bestseller_rail,
        "bestsellers": bestseller_rail,
        "new_arrivals": new_arrivals,
        "same_day": same_day,
    }


def _apply_plp_filters(queryset: QuerySet[Product], filters: dict[str, Any]) -> QuerySet[Product]:
    """Apply PLP filter dict to a base queryset."""
    if category_id := filters.get("category_id"):
        queryset = queryset.filter(category_id=category_id)
    if occasion_id := filters.get("occasion_id"):
        queryset = queryset.filter(primary_occasion_id=occasion_id)
    if brand_id := filters.get("brand_id"):
        queryset = queryset.filter(brand_id=brand_id)
    if recipient_id := filters.get("recipient_id"):
        queryset = queryset.filter(recipients__id=recipient_id)
    if color := filters.get("color"):
        queryset = queryset.filter(color__iexact=color)
    if filters.get("same_day"):
        queryset = queryset.filter(is_same_day_eligible=True)
    if filters.get("bestseller"):
        queryset = queryset.filter(is_bestseller=True)
    if filters.get("new_arrival"):
        queryset = queryset.filter(is_new_arrival=True)
    if filters.get("in_stock"):
        queryset = queryset.filter(stock_quantity__gt=0)
    if min_price := filters.get("min_price"):
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price := filters.get("max_price"):
        queryset = queryset.filter(base_price__lte=max_price)
    return queryset


def _apply_plp_sort(queryset: QuerySet[Product], sort: str) -> QuerySet[Product]:
    """Apply PLP sort key to queryset."""
    sort_map = {
        "price_asc": "base_price",
        "price_desc": "-base_price",
        "newest": "-created_at",
        "rating": "-average_rating",
        "name": "name",
    }
    return queryset.order_by(sort_map.get(sort, "-created_at"))


def get_plp_products(
    *,
    filters: Optional[dict[str, Any]] = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int = 24,
) -> dict[str, Any]:
    """
    Return a paginated PLP page with advanced filters and average rating annotation.

    Query guarantee: exactly 4 DB queries (COUNT + page SELECT + primary image
    prefetch + active flash-sale lookup) regardless of total product count.

    Approved reviews only contribute to average_rating annotation.
    """
    filters = filters or {}
    queryset = (
        Product.objects.filter(is_active=True)
        .select_related("category", "brand", "primary_occasion")
        .prefetch_related(_primary_image_prefetch())
        .only(*PLP_CARD_FIELDS)
        .annotate(
            average_rating=Avg(
                "reviews__rating",
                filter=Q(reviews__moderation_status=ModerationStatus.APPROVED),
            ),
        )
    )
    queryset = _apply_plp_filters(queryset, filters)
    queryset = _apply_plp_sort(queryset, sort)

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    results = list(page_obj.object_list)

    from marketing.selectors import get_flash_sale_discounts_for_products

    flash_discounts = get_flash_sale_discounts_for_products(
        product_prices={product.pk: product.base_price for product in results},
    )
    display_prices: dict[int, Decimal] = {}
    for product in results:
        discount_pct = flash_discounts.get(product.pk)
        if discount_pct is None:
            display_prices[product.pk] = product.base_price
        else:
            discount = (product.base_price * discount_pct / Decimal("100")).quantize(
                Decimal("0.01")
            )
            display_prices[product.pk] = product.base_price - discount
        product.display_price = display_prices[product.pk]

    return {
        "results": results,
        "display_prices": display_prices,
        "page": page_obj.number,
        "page_size": page_size,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }


def get_product_detail(*, slug: str) -> Optional[Product]:
    """
    Return a fully hydrated product for the PDP in a bounded number of queries.

    Query guarantee: exactly 10 DB queries (constant regardless of variant/image/
    review/related counts) —
      1) product + select_related(category, brand, primary_occasion)
      2) variants prefetch
      3) images prefetch (ordered)
      4) videos prefetch
      5) approved reviews prefetch
      6) review photos prefetch (via nested Prefetch on reviews)
      7) related products prefetch
      8) related product primary images prefetch
      9) FBT products prefetch
      10) FBT product primary images prefetch
    """
    approved_reviews_prefetch = Prefetch(
        "reviews",
        queryset=(
            Review.objects.filter(moderation_status=ModerationStatus.APPROVED)
            .select_related("customer", "customer__user")
            .prefetch_related(
                Prefetch("photos", queryset=ReviewPhoto.objects.order_by("id")),
            )
            .order_by("-created_at")
        ),
        to_attr="approved_reviews",
    )
    related_prefetch = Prefetch(
        "relations",
        queryset=ProductRelation.objects.filter(
            relation_type=RelationType.RELATED,
        )
        .select_related(
            "related_product",
            "related_product__category",
            "related_product__brand",
        )
        .prefetch_related(
            Prefetch(
                "related_product__images",
                queryset=ProductImage.objects.filter(is_primary=True).order_by("id"),
                to_attr="primary_images",
            ),
        ),
        to_attr="related_relations",
    )
    fbt_prefetch = Prefetch(
        "relations",
        queryset=ProductRelation.objects.filter(
            relation_type=RelationType.FREQUENTLY_BOUGHT_TOGETHER,
        )
        .select_related(
            "related_product",
            "related_product__category",
            "related_product__brand",
        )
        .prefetch_related(
            Prefetch(
                "related_product__images",
                queryset=ProductImage.objects.filter(is_primary=True).order_by("id"),
                to_attr="primary_images",
            ),
        ),
        to_attr="fbt_relations",
    )

    return (
        Product.objects.filter(is_active=True, slug=slug)
        .select_related("category", "brand", "primary_occasion")
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=ProductVariant.objects.order_by("variant_type", "name"),
                to_attr="variant_list",
            ),
            Prefetch(
                "images",
                queryset=ProductImage.objects.order_by("display_order"),
            ),
            Prefetch(
                "videos",
                queryset=ProductVideo.objects.order_by("id"),
            ),
            approved_reviews_prefetch,
            related_prefetch,
            fbt_prefetch,
        )
        .first()
    )


RECENTLY_VIEWED_KEY_TEMPLATE = "catalog:recently_viewed:{viewer_key}"
RECENTLY_VIEWED_MAX = 20


def _recently_viewed_cache_key(*, viewer_key: str) -> str:
    return RECENTLY_VIEWED_KEY_TEMPLATE.format(viewer_key=viewer_key)


def record_product_view(*, viewer_key: str, product_id: int) -> None:
    """
    Push a product ID onto the Redis-backed recently-viewed list for a viewer.

    Not a selector — write path for Redis only (no DB).
    """
    from django.core.cache import cache

    key = _recently_viewed_cache_key(viewer_key=viewer_key)
    viewed: list[int] = cache.get(key, [])
    viewed = [pid for pid in viewed if pid != product_id]
    viewed.insert(0, product_id)
    cache.set(key, viewed[:RECENTLY_VIEWED_MAX], timeout=60 * 60 * 24 * 30)


def get_recently_viewed(
    *,
    viewer_key: str,
) -> list[Product]:
    """
    Hydrate the Redis recently-viewed list in a single DB round trip.

    Query guarantee: exactly 2 DB queries when IDs exist (1 product SELECT with
    select_related + 1 primary-image prefetch). Zero DB queries when list is empty.
    Redis order is preserved in Python — DB ORDER BY is intentionally not used.

    Params:
        viewer_key: Customer profile PK string or session key.
    Returns:
        List of Product instances in most-recent-first order.
    """
    from django.core.cache import cache

    key = _recently_viewed_cache_key(viewer_key=viewer_key)
    product_ids: list[int] = cache.get(key, [])
    if not product_ids:
        return []

    products = (
        Product.objects.filter(id__in=product_ids, is_active=True)
        .select_related("category", "brand")
        .prefetch_related(_primary_image_prefetch())
        .only(*PLP_CARD_FIELDS)
    )
    product_map = {product.id: product for product in products}
    return [product_map[pid] for pid in product_ids if pid in product_map]


def get_category_tree() -> list:
    """
    Return active root categories with prefetched children for the mega menu.

    Query guarantee: 2 queries (roots + children prefetch); cached 5 minutes.
    """
    from catalog.models import Category

    cached = cache.get(CATEGORY_TREE_CACHE_KEY)
    if cached is not None:
        return cached

    tree = list(
        Category.objects.filter(is_active=True, parent__isnull=True)
        .prefetch_related(
            Prefetch(
                "children",
                queryset=Category.objects.filter(is_active=True).order_by("display_order", "name"),
            )
        )
        .order_by("display_order", "name")
    )
    cache.set(CATEGORY_TREE_CACHE_KEY, tree, CATEGORY_TREE_TTL)
    return tree


def invalidate_category_tree_cache() -> None:
    """Clear cached navigation tree after category mutations."""
    cache.delete(CATEGORY_TREE_CACHE_KEY)


def get_search_suggestions(*, query: str, limit: int = 8) -> list[Product]:
    """
    Return product name matches for HTMX live search.

    Query guarantee: exactly 1 SELECT with primary-image prefetch.
    """
    if not query or len(query.strip()) < 2:
        return []
    return list(
        Product.objects.filter(is_active=True, name__icontains=query.strip())
        .select_related("category")
        .prefetch_related(_primary_image_prefetch())
        .only(*PLP_CARD_FIELDS)[:limit]
    )


def get_occasions_for_display() -> list:
    """Return all occasions for the homepage shop-by-occasion rail and PLP filters."""
    from catalog.models import Occasion

    return list(Occasion.objects.all().order_by("name"))


def get_recipients_for_display() -> list:
    """Return active recipients for the homepage shop-by-recipient rail and PLP filters."""
    from catalog.models import Recipient

    return list(Recipient.objects.filter(is_active=True).order_by("display_order", "name"))


def get_root_categories(*, category_ids: list[int] | None = None) -> list:
    """Return root categories for homepage shop-by-category rail."""
    from catalog.models import Category

    qs = Category.objects.filter(is_active=True, parent__isnull=True).order_by(
        "display_order", "name"
    )
    if category_ids:
        qs = qs.filter(pk__in=category_ids)
    return list(qs)


def get_featured_brands(*, brand_ids: list[int] | None = None) -> list:
    """Return featured brands for homepage brand rail."""
    from catalog.models import Brand

    qs = Brand.objects.filter(is_featured=True).order_by("name")
    if brand_ids:
        qs = qs.filter(pk__in=brand_ids)
    return list(qs)


def get_products_for_section_config(*, config: dict) -> list[Product]:
    """
    Return products for collection sections driven by CMS config JSON.

    Config keys: product_ids, category_id, brand_id, recipient_id, min_price,
    limit, flags (model booleans).
    Query guarantee: 1 SELECT + 1 primary-image prefetch.
    """
    qs = Product.objects.filter(is_active=True)
    if product_ids := config.get("product_ids"):
        qs = qs.filter(pk__in=product_ids)
    if category_id := config.get("category_id"):
        qs = qs.filter(category_id=category_id)
    if brand_id := config.get("brand_id"):
        qs = qs.filter(brand_id=brand_id)
    if recipient_id := config.get("recipient_id"):
        qs = qs.filter(recipients__id=recipient_id)
    if min_price := config.get("min_price"):
        qs = qs.filter(base_price__gte=min_price)
    for flag in config.get("flags", []):
        if hasattr(Product, flag):
            qs = qs.filter(**{flag: True})
    limit = config.get("limit", HOMEPAGE_RAIL_LIMIT)
    return list(
        qs.select_related("category", "brand")
        .prefetch_related(_primary_image_prefetch())
        .only(*PLP_CARD_FIELDS)
        .order_by("-created_at")[:limit]
    )


def get_recent_approved_reviews(*, limit: int = 6) -> list[Review]:
    """
    Return recent approved reviews for homepage reviews section.

    Query guarantee: 1 SELECT with select_related product + customer.
    """
    return list(
        Review.objects.filter(moderation_status=ModerationStatus.APPROVED)
        .select_related("product", "customer", "customer__user")
        .order_by("-created_at")[:limit]
    )


def get_variant_price(*, product_id: int, variant_id: int | None = None) -> dict[str, str]:
    """
    Return computed price for a product/variant combination.

    Applies active flash sale pricing via marketing selector when applicable.
    Query guarantee: 1–2 SELECTs on product/variant + 0–1 on flash sale.
    """

    from marketing.selectors import get_active_flash_sale_price

    product = Product.objects.get(pk=product_id, is_active=True)
    price = product.base_price
    resolved_variant_id = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product=product).first()
        if variant:
            price = product.base_price + variant.price_delta
            resolved_variant_id = variant.pk

    sale = get_active_flash_sale_price(product_id=product.pk, base_price=price)
    display_price = sale["price"]

    result = {
        "base_price": str(product.base_price),
        "price": str(display_price),
        "variant_id": str(resolved_variant_id) if resolved_variant_id else "",
        "is_flash_sale": str(sale["is_flash_sale"]).lower(),
    }
    if sale["is_flash_sale"]:
        result["original_price"] = str(sale["original_price"])
    return result


def get_category_by_slug(*, slug: str):
    """Return an active category by slug. Query guarantee: 1 SELECT."""
    from catalog.models import Category

    return Category.objects.filter(slug=slug, is_active=True).first()


def get_plp_filter_options() -> dict:
    """
    Return sidebar filter options for PLP.

    Query guarantee: 4 queries (categories, occasions, brands, recipients).
    """
    return {
        "categories": get_root_categories(),
        "occasions": get_occasions_for_display(),
        "brands": get_featured_brands(),
        "recipients": get_recipients_for_display(),
    }


def get_product_for_cart_add(
    *,
    product_id: int,
    variant_id: int | None = None,
) -> tuple[Optional[Product], Optional[ProductVariant]]:
    """
    Return product and optional variant for cart add operations.

    Query guarantee: 1 SELECT on product (+ 1 on variant when variant_id set).
    """
    product = (
        Product.objects.filter(pk=product_id, is_active=True)
        .select_related("category", "brand")
        .first()
    )
    if product is None:
        return None, None
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product=product).first()
    return product, variant


def get_products_by_ids(*, product_ids: list[int]) -> list[Product]:
    """Return minimal product rows for cart drawer. Query guarantee: 1 SELECT."""
    if not product_ids:
        return []
    return list(
        Product.objects.filter(pk__in=product_ids, is_active=True).only(
            "id", "name", "slug", "base_price"
        )
    )
