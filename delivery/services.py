"""Write operations and business rules for the delivery app."""

from __future__ import annotations

from datetime import date

from django.db import IntegrityError, transaction

from delivery.exceptions import SlotFullyBookedError
from delivery.models import DeliverySlot, DeliverySlotBooking


@transaction.atomic
def reserve_delivery_slot(*, slot: DeliverySlot, delivery_date: date) -> DeliverySlotBooking:
    """
      Atomically reserve one booking against a delivery slot for a date.

      Uses ``select_for_update`` on the ``DeliverySlotBooking`` row to prevent
    overselling capacity under concurrent checkout.
    """
    try:
        booking = (
            DeliverySlotBooking.objects.select_for_update()
            .filter(slot=slot, date=delivery_date)
            .first()
        )
        if booking is None:
            booking = DeliverySlotBooking.objects.create(
                slot=slot,
                date=delivery_date,
                current_bookings=0,
            )
            booking = DeliverySlotBooking.objects.select_for_update().get(pk=booking.pk)
    except IntegrityError:
        booking = DeliverySlotBooking.objects.select_for_update().get(
            slot=slot,
            date=delivery_date,
        )

    if booking.current_bookings >= slot.max_capacity_per_day:
        raise SlotFullyBookedError(
            f"Delivery slot {slot.pk} is fully booked on {delivery_date.isoformat()}."
        )

    booking.current_bookings += 1
    booking.save(update_fields=["current_bookings", "updated_at"])
    return booking
