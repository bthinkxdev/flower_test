"""Read-only query functions for the accounts app; views must not call the ORM directly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Prefetch

from accounts.models import (
    Address,
    CorporateAccount,
    CorporateApprovalStatus,
    CustomerProfile,
    GiftReminder,
    SavedPaymentMethod,
    Wishlist,
)
from notifications.selectors import get_unread_notification_count
from orders.selectors import get_customer_orders


@dataclass(frozen=True)
class CustomerDashboardContext:
    """Aggregated data for the customer account dashboard."""

    profile: CustomerProfile
    default_address: Optional[Address]
    recent_orders: list[Any]
    unread_notification_count: int


def get_customer_profile_for_user(*, user: User) -> Optional[CustomerProfile]:
    """
    Return the customer profile for a user with related currency and default address.

    Query guarantee: exactly 1 SELECT with select_related on preferred_currency,
    default_address, and default_address__city.
    """
    return (
        CustomerProfile.objects.select_related(
            "preferred_currency",
            "default_address",
            "default_address__city",
        )
        .filter(user=user)
        .first()
    )


def get_customer_dashboard_context(*, user: User) -> Optional[CustomerDashboardContext]:
    """
    Build the customer dashboard context from dedicated selectors.

    Query guarantee: exactly 4 queries total —
      1) customer profile + preferred_currency + default_address + city (select_related),
      2–3) paginated orders via orders.get_customer_orders (COUNT + page SELECT),
      4) unread notification count via notifications.get_unread_notification_count.
    Params:
        user: Authenticated Django User.
    Returns:
        CustomerDashboardContext or None if no profile exists.
    """
    profile = get_customer_profile_for_user(user=user)
    if profile is None:
        return None

    orders_page = get_customer_orders(customer_profile=profile, page=1, page_size=5)
    recent_orders = orders_page["results"]
    unread_count = get_unread_notification_count(user=user)

    return CustomerDashboardContext(
        profile=profile,
        default_address=profile.default_address,
        recent_orders=recent_orders,
        unread_notification_count=unread_count,
    )


def get_address_by_id(
    *,
    address_id: int,
    customer_profile: CustomerProfile,
) -> Optional[Address]:
    """
    Return a single address owned by the customer.

    Query guarantee: exactly 1 SELECT with select_related(city).
    """
    return (
        Address.objects.select_related("city")
        .filter(pk=address_id, customer_profile=customer_profile)
        .first()
    )


def get_saved_addresses(
    *,
    customer_profile: CustomerProfile,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """
    Return a paginated page of customer addresses.

    Query guarantee: 2 queries — COUNT + page SELECT with select_related(city).
    """
    queryset = (
        Address.objects.select_related("city")
        .filter(customer_profile=customer_profile)
        .order_by("-is_default", "-created_at")
    )
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return {
        "results": list(page_obj.object_list),
        "page": page_obj.number,
        "page_size": page_size,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }


def get_saved_payment_methods(
    *,
    customer_profile: CustomerProfile,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """
    Return a paginated page of saved payment methods.

    Query guarantee: 2 queries — COUNT + page SELECT.
    """
    queryset = SavedPaymentMethod.objects.filter(customer_profile=customer_profile).order_by(
        "-is_default",
        "-created_at",
    )
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return {
        "results": list(page_obj.object_list),
        "page": page_obj.number,
        "page_size": page_size,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }


def get_pending_corporate_approvals(*, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """
    Return a paginated page of corporate accounts awaiting admin approval.

    Query guarantee: 2 queries — 1 COUNT + 1 SELECT page (Paginator pattern).
    Params:
        page: 1-based page number.
        page_size: Number of records per page.
    Returns:
        Dict with keys: results, page, page_size, total_count, total_pages, has_next, has_previous.
    """
    queryset = (
        CorporateAccount.objects.select_related("user")
        .filter(approval_status=CorporateApprovalStatus.PENDING)
        .order_by("created_at")
    )
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return {
        "results": list(page_obj.object_list),
        "page": page_obj.number,
        "page_size": page_size,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }


@dataclass(frozen=True)
class WishlistView:
    """Wishlist data for card rendering."""

    wishlist: Wishlist
    items: list
    readonly: bool


def get_wishlist(
    *,
    customer_profile: Optional[CustomerProfile] = None,
    share_token: Optional[str] = None,
) -> Optional[WishlistView]:
    """
    Return wishlist items for an owner or shared read-only token.

    Query guarantee: 1 SELECT on wishlist + 1 prefetch on items/products.
    """
    from django.core import signing

    from accounts.models import WishlistItem
    from accounts.subscription_services import WISHLIST_SHARE_SALT

    if share_token:
        try:
            data = signing.loads(share_token, salt=WISHLIST_SHARE_SALT)
            wishlist_id = data["wishlist_id"]
        except signing.BadSignature:
            return None
        wishlist = (
            Wishlist.objects.prefetch_related(
                Prefetch(
                    "items",
                    queryset=WishlistItem.objects.select_related("product"),
                )
            )
            .filter(pk=wishlist_id)
            .first()
        )
        if wishlist is None:
            return None
        return WishlistView(wishlist=wishlist, items=list(wishlist.items.all()), readonly=True)

    if customer_profile is None:
        return None

    wishlist = (
        Wishlist.objects.filter(customer_profile=customer_profile)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=WishlistItem.objects.select_related("product"),
            )
        )
        .first()
    )
    if wishlist is None:
        return None
    return WishlistView(wishlist=wishlist, items=list(wishlist.items.all()), readonly=False)


def get_upcoming_gift_reminders(*, customer_profile: CustomerProfile) -> list[GiftReminder]:
    """Return gift reminders ordered by reminder_date. Query guarantee: 1 SELECT."""
    return list(
        GiftReminder.objects.filter(customer_profile=customer_profile).order_by("reminder_date")
    )
