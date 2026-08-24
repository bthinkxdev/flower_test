"""Cross-app signal handlers for the reports app (side effects only)."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order
from orders.signals import order_status_changed
from reports.selectors import ADMIN_DASHBOARD_CACHE_KEY


@receiver(post_save, sender=Order)
def invalidate_dashboard_cache_on_order_created(sender, instance, created, **kwargs) -> None:
    """
    Drop the cached admin dashboard summary whenever a new order is placed.

    """
    if created:
        cache.delete(ADMIN_DASHBOARD_CACHE_KEY)


@receiver(order_status_changed)
def invalidate_dashboard_cache_on_status_change(
    sender, *, order, old_status: str, new_status: str, **kwargs
) -> None:
    """
    Drop the cached admin dashboard summary whenever an order's status changes.

    """
    cache.delete(ADMIN_DASHBOARD_CACHE_KEY)
