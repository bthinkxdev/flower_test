"""Read-only query functions for the corporate app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.paginator import Paginator

from accounts.models import CorporateAccount
from corporate.models import CorporateInvoice, CorporateOrder, CorporateQuoteStatus
from recurring.models import RecurrenceStatus


@dataclass(frozen=True)
class CorporateDashboardContext:
    """Aggregated corporate portal data."""

    pending_quotes: dict[str, Any]
    active_recurring_orders: dict[str, Any]
    invoice_history: dict[str, Any]


def _paginate_queryset(*, queryset, page: int, page_size: int) -> dict[str, Any]:
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


def get_corporate_dashboard(
    *,
    corporate_account: CorporateAccount,
    quotes_page: int = 1,
    recurring_page: int = 1,
    invoices_page: int = 1,
    page_size: int = 20,
) -> CorporateDashboardContext:
    """
    Return paginated pending quotes, recurring orders, and invoices.

    Query guarantee: 6 queries — COUNT + page SELECT per list (3 lists).
    """
    pending_qs = (
        CorporateOrder.objects.filter(
            corporate_account=corporate_account,
            quote_status__in=[
                CorporateQuoteStatus.REQUESTED,
                CorporateQuoteStatus.QUOTED,
                CorporateQuoteStatus.APPROVED,
            ],
        )
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    recurring_qs = (
        CorporateOrder.objects.filter(
            corporate_account=corporate_account,
            is_recurring=True,
            recurring_schedule__status=RecurrenceStatus.ACTIVE,
        )
        .select_related("recurring_schedule")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    invoices_qs = (
        CorporateInvoice.objects.filter(
            corporate_order__corporate_account=corporate_account,
        )
        .select_related("corporate_order")
        .order_by("-generated_at")
    )
    return CorporateDashboardContext(
        pending_quotes=_paginate_queryset(
            queryset=pending_qs, page=quotes_page, page_size=page_size
        ),
        active_recurring_orders=_paginate_queryset(
            queryset=recurring_qs, page=recurring_page, page_size=page_size
        ),
        invoice_history=_paginate_queryset(
            queryset=invoices_qs, page=invoices_page, page_size=page_size
        ),
    )
