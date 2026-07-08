"""Read-only query functions for the delivery app; views must not call the ORM directly."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional, Union

from django.db.models import F, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.models import Product
from delivery.models import (
    City,
    Country,
    DeliverySlot,
    DeliverySlotBooking,
    DeliverySlotType,
)


def get_active_countries() -> list[Country]:
    """Return all active delivery countries for the header selector. 1 SELECT."""
    return list(Country.objects.filter(is_active=True).order_by("name"))


def get_city_by_slug(*, slug: str) -> Optional[City]:
    """
    Return an active city by slug.

    Query guarantee: exactly 1 SELECT on delivery_city filtered by slug (indexed).
    """
    return City.objects.select_related("country").filter(slug=slug, is_active=True).first()


def get_active_cities() -> list[City]:
    """Return all active delivery cities. Query guarantee: 1 SELECT."""
    return list(City.objects.select_related("country").filter(is_active=True).order_by("name"))


def _same_day_allowed(*, city: City, delivery_date: date) -> bool:
    """Return True when same-day slots may still be offered for a city."""
    today = timezone.localdate()
    if delivery_date != today:
        return delivery_date > today
    return timezone.localtime().hour < city.same_day_cutoff_hour


def get_available_slots(
    *,
    city: City,
    delivery_date: Union[date, str],
    allow_midnight: bool = False,
) -> list[DeliverySlot]:
    """
    Return active delivery slots with remaining capacity for a city and date.

    Excludes slots at ``max_capacity_per_day`` and applies the city's
    per-city same-day cutoff hour.

    Query guarantee: 1 SELECT on delivery slots with annotated booking counts.
    """
    if isinstance(delivery_date, str):
        delivery_date = date.fromisoformat(delivery_date)

    if delivery_date < timezone.localdate():
        return []
    if not _same_day_allowed(city=city, delivery_date=delivery_date):
        return []

    qs = DeliverySlot.objects.filter(is_active=True)
    if not allow_midnight:
        qs = qs.exclude(slot_type=DeliverySlotType.MIDNIGHT)

    booking_count = DeliverySlotBooking.objects.filter(
        slot_id=OuterRef("pk"),
        date=delivery_date,
    ).values("current_bookings")[:1]

    qs = (
        qs.annotate(
            bookings=Coalesce(Subquery(booking_count), 0),
        )
        .filter(bookings__lt=F("max_capacity_per_day"))
        .order_by("start_time")
    )
    return list(qs)


def get_available_delivery_slots(
    *,
    city_id: Optional[int] = None,
    delivery_date: Optional[str] = None,
    allow_midnight: bool = False,
) -> list[DeliverySlot]:
    """
    Backward-compatible wrapper around ``get_available_slots``.

    When city/date are omitted, returns all active slots (legacy gift builder).
    """
    if city_id and delivery_date:
        city = City.objects.filter(pk=city_id, is_active=True).first()
        if city is None:
            return []
        return get_available_slots(
            city=city,
            delivery_date=delivery_date,
            allow_midnight=allow_midnight,
        )

    qs = DeliverySlot.objects.filter(is_active=True)
    if not allow_midnight:
        qs = qs.exclude(slot_type=DeliverySlotType.MIDNIGHT)
    return list(qs.order_by("start_time"))


def get_earliest_delivery_estimate(*, product: Product, destination_city: City) -> dict[str, Any]:
    """
    Return the earliest delivery estimate for a product to a destination city.

    Uses per-city same-day cutoff, product same-day eligibility, and slot
    capacity — replacing the Phase 4/5 today/tomorrow stub.
    """
    today = timezone.localdate()
    allow_midnight = bool(getattr(product, "supports_gift_customization", False))

    candidate_dates: list[date] = []
    if product.is_same_day_eligible and _same_day_allowed(
        city=destination_city,
        delivery_date=today,
    ):
        candidate_dates.append(today)
    candidate_dates.append(today + timedelta(days=1))
    candidate_dates.append(today + timedelta(days=2))

    for candidate in candidate_dates:
        slots = get_available_slots(
            city=destination_city,
            delivery_date=candidate,
            allow_midnight=allow_midnight,
        )
        if slots:
            is_same_day = candidate == today
            label = "Today" if is_same_day else candidate.strftime("%a, %b %d")
            return {
                "label": label,
                "delivery_date": candidate.isoformat(),
                "is_same_day": is_same_day,
                "city": destination_city.name,
                "slot_count": len(slots),
            }

    fallback = today + timedelta(days=1)
    return {
        "label": "Tomorrow",
        "delivery_date": fallback.isoformat(),
        "is_same_day": False,
        "city": destination_city.name,
        "slot_count": 0,
    }


def get_delivery_charge(*, item_count: int, destination_city: City) -> Decimal:
    """
    Return delivery charge for a cart heading to a destination city.

    Uses the city's ``delivery_charge_base`` field.
    """
    if item_count <= 0:
        return Decimal("0.00")
    return destination_city.delivery_charge_base


def get_slot_booking_count(*, slot_id: int, delivery_date: date) -> int:
    """Return current bookings for a slot on a date. Query guarantee: 1 SELECT."""
    booking = DeliverySlotBooking.objects.filter(slot_id=slot_id, date=delivery_date).first()
    return booking.current_bookings if booking else 0
