"""HTTP views for the corporate app."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from corporate.selectors import get_corporate_dashboard


@login_required
@require_GET
def corporate_dashboard_view(request: HttpRequest) -> HttpResponse:
    """Corporate portal dashboard."""
    account = getattr(request.user, "corporate_account", None)
    if account is None:
        if request.headers.get("Accept") == "application/json":
            raise Http404("Corporate account not found.")
        return render(
            request,
            "corporate/dashboard.html",
            {"account": None, "dashboard": None},
        )

    dashboard = get_corporate_dashboard(
        corporate_account=account,
        quotes_page=int(request.GET.get("quotes_page", 1)),
        recurring_page=int(request.GET.get("recurring_page", 1)),
        invoices_page=int(request.GET.get("invoices_page", 1)),
    )
    if request.headers.get("Accept") == "application/json":
        return JsonResponse(
            {
                "pending_quotes": [order.pk for order in dashboard.pending_quotes["results"]],
                "active_recurring_orders": [
                    order.pk for order in dashboard.active_recurring_orders["results"]
                ],
                "invoice_history": [inv.pk for inv in dashboard.invoice_history["results"]],
                "pagination": {
                    "pending_quotes": dashboard.pending_quotes,
                    "active_recurring_orders": dashboard.active_recurring_orders,
                    "invoice_history": dashboard.invoice_history,
                },
            }
        )
    return render(
        request,
        "corporate/dashboard.html",
        {"account": account, "dashboard": dashboard},
    )
