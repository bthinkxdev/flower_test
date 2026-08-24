"""Read-only query helpers for the admin dashboard (home + reports charts)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, F, Sum
from django.utils import timezone

from accounts.models import CustomerProfile
from catalog.models import Product
from orders.models import Order, OrderItem, OrderStatus
from reports.models import (
    DailyCustomerReport,
    DailyProductPerformance,
    DailySalesReport,
)


def get_sales_series(*, days: int = 14) -> dict[str, list]:
    """Return ordered date labels, revenue and order counts for the last N days.
    
    """
    start = timezone.localdate() - timedelta(days=days - 1)
    today = timezone.localdate()
    rows = {
        r.report_date: r
        for r in DailySalesReport.objects.filter(report_date__gte=start).order_by("report_date")
    }
    categories: list[str] = []
    revenue: list[float] = []
    orders: list[int] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        categories.append(day.strftime("%b %d"))
        if day == today:
            today_agg = (
                Order.objects.filter(created_at__date=today)
                .exclude(order_status=OrderStatus.CANCELLED)
                .aggregate(order_count=Count("id"), revenue=Sum("total_amount"))
            )
            revenue.append(float(today_agg["revenue"] or 0))
            orders.append(today_agg["order_count"] or 0)
            continue
        row = rows.get(day)
        revenue.append(float(row.revenue) if row else 0.0)
        orders.append(row.order_count if row else 0)
    return {"categories": categories, "revenue": revenue, "orders": orders}


def get_customer_split() -> dict[str, list[float]]:
    """Return [new%, returning%] from the most recent customer report."""
    latest = DailyCustomerReport.objects.order_by("-report_date").first()
    if not latest:
        return {"series": [0, 0]}
    total = (latest.new_customers or 0) + (latest.returning_customers or 0)
    if total == 0:
        return {"series": [0, 0]}
    new_pct = round(100 * latest.new_customers / total)
    return {"series": [new_pct, 100 - new_pct]}


def _primary_image_url(product: Product) -> str | None:
    """Best-effort primary image URL for a product (images assumed prefetched)."""
    images = list(product.images.all())
    if not images:
        return None
    primary = next((im for im in images if im.is_primary), images[0])
    try:
        return primary.image.url if primary.image else None
    except ValueError:
        return None


def _format_top_products(rows: list[tuple[Product, int, float]]) -> list[dict[str, Any]]:
    """Shape (product, units_sold, revenue) tuples into the home-dashboard row format."""
    top_revenue = max((rev for _, _, rev in rows), default=0.0)
    result: list[dict[str, Any]] = []
    for product, units_sold, revenue in rows:
        result.append(
            {
                "name": product.name,
                "units": units_sold,
                "revenue": revenue,
                "category": product.category.name if product.category_id else "",
                "image": _primary_image_url(product),
                "share": round(100 * revenue / top_revenue) if top_revenue else 0,
            }
        )
    return result


def _get_live_top_products(*, limit: int) -> list[dict[str, Any]]:
    """
    Top products for today, aggregated live from order items.

    """
    today = timezone.localdate()
    agg_rows = list(
        OrderItem.objects.filter(order__created_at__date=today)
        .exclude(order__order_status=OrderStatus.CANCELLED)
        .values("product_id")
        .annotate(units_sold=Sum("quantity"), revenue=Sum(F("unit_price") * F("quantity")))
        .order_by("-revenue")[:limit]
    )
    if not agg_rows:
        return []
    products_by_id = {
        p.pk: p
        for p in Product.objects.filter(
            pk__in=[r["product_id"] for r in agg_rows]
        ).select_related("category").prefetch_related("images")
    }
    rows = [
        (products_by_id[r["product_id"]], r["units_sold"] or 0, float(r["revenue"] or 0))
        for r in agg_rows
        if r["product_id"] in products_by_id
    ]
    return _format_top_products(rows)


def get_top_products(*, limit: int = 5) -> list[dict[str, Any]]:
    """
    Top products by revenue on the most recent day that has performance data.

    """
    latest = (
        DailyProductPerformance.objects.order_by("-report_date")
        .values_list("report_date", flat=True)
        .first()
    )
    if latest:
        rows = list(
            DailyProductPerformance.objects.filter(report_date=latest)
            .select_related("product", "product__category")
            .prefetch_related("product__images")
            .order_by("-revenue")[:limit]
        )
        if rows:
            return _format_top_products(
                [(r.product, r.units_sold, float(r.revenue or 0)) for r in rows]
            )
    return _get_live_top_products(limit=limit)


def get_low_stock_products(*, limit: int = 5) -> list[dict[str, Any]]:
    """Active products at or below their low-stock threshold."""
    products = (
        Product.objects.filter(is_active=True, stock_quantity__lte=F("low_stock_threshold"))
        .select_related("category")
        .prefetch_related("images")
        .order_by("stock_quantity")[:limit]
    )
    return [
        {
            "name": p.name,
            "sku": p.sku,
            "stock": p.stock_quantity,
            "category": p.category.name if p.category_id else "",
            "image": _primary_image_url(p),
        }
        for p in products
    ]


def get_recent_orders(*, limit: int = 6) -> list[Order]:
    """Most recent orders with their customer preloaded."""
    return list(
        Order.objects.select_related("customer_profile__user", "currency").order_by("-created_at")[
            :limit
        ]
    )


def get_dashboard_counts() -> dict[str, int]:
    """Cheap top-level counts for the overview widget."""
    return {
        "product_count": Product.objects.filter(is_active=True).count(),
        "customer_count": CustomerProfile.objects.count(),
        "order_count": Order.objects.count(),
    }
