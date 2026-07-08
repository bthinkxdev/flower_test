"""Corporate order recurrence handler registration."""

from __future__ import annotations

from corporate.models import CorporateOrder
from corporate.services import execute_corporate_order_recurrence
from recurring.registry import register_recurrence_handler


def register() -> None:
    register_recurrence_handler(
        model_class=CorporateOrder,
        handler=execute_corporate_order_recurrence,
    )


register()
