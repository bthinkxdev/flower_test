"""HTTP views for the orders app."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from orders.selectors import get_order_tracking_view


@login_required
@require_GET
def order_tracking_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """Customer order tracking page with status timeline."""
    profile = request.user.customer_profile
    tracking = get_order_tracking_view(order_id=order_id, customer_profile=profile)
    if tracking is None:
        raise Http404("Order not found.")
    return render(
        request,
        "orders/tracking.html",
        {
            "tracking": tracking,
            "order": tracking.order,
            "status_history": tracking.status_history,
        },
    )
