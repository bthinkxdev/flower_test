"""HTTP views for the corporate app."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import CorporateApprovalStatus
from catalog.selectors import get_variant_price
from corporate.exceptions import CorporateOrderError
from corporate.forms import CorporateQuoteRequestForm
from corporate.selectors import get_corporate_dashboard
from corporate.services import request_corporate_quote


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

@login_required
@require_http_methods(["GET", "POST"])
def corporate_quote_request_view(request: HttpRequest) -> HttpResponse:
    """Submit a new bulk/recurring quote request for an approved corporate account."""
    from catalog.models import Product

    account = getattr(request.user, "corporate_account", None)
    if account is None or account.approval_status != CorporateApprovalStatus.APPROVED:
        raise Http404("Corporate account not found or not yet approved.")

    products = Product.objects.filter(is_active=True).only("id", "name", "base_price").order_by("name")

    if request.method == "GET":
        return render(
            request,
            "corporate/quote_request.html",
            {"form": CorporateQuoteRequestForm(), "products": products},
        )

    form = CorporateQuoteRequestForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "corporate/quote_request.html",
            {"form": form, "products": products},
            status=400,
        )

    resolved_items = []
    for row in form.cleaned_data["items_json"]:
        try:
            price_data = get_variant_price(product_id=row["product_id"], variant_id=row["variant_id"])
        except Product.DoesNotExist:
            form.add_error(None, f"Product #{row['product_id']} is not available.")
            return render(
                request,
                "corporate/quote_request.html",
                {"form": form, "products": products},
                status=400,
            )
        resolved_items.append(
            {
                "product_id": row["product_id"],
                "variant_id": row["variant_id"],
                "quantity": row["quantity"],
                "unit_price": price_data["price"],
            }
        )

    try:
        request_corporate_quote(
            corporate_account=account,
            items=resolved_items,
            notes=form.cleaned_data.get("notes", ""),
            is_recurring=form.cleaned_data.get("is_recurring", False),
            frequency=form.cleaned_data.get("frequency") or None,
            next_run_date=form.cleaned_data.get("next_run_date"),
            created_by=request.user,
        )
    except CorporateOrderError as exc:
        form.add_error(None, str(exc))
        return render(
            request,
            "corporate/quote_request.html",
            {"form": form, "products": products},
            status=400,
        )

    return redirect("corporate:dashboard")