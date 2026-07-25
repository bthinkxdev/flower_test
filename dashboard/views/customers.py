"""Customer and corporate account management."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from accounts.models import CorporateAccount, CorporateApprovalStatus, CustomerProfile
from dashboard import forms
from dashboard.access import dashboard_required
from dashboard.views.base import DashboardListView, DashboardUpdateView


class CustomerListView(DashboardListView):
    model = CustomerProfile
    nav_section = "customers"
    url_basename = "customer"
    singular_name = "Customer"
    plural_name = "Customers"
    search_fields = ["user__email", "user__username", "phone"]
    select_related = ["user"]
    can_create = False
    can_delete = False
    columns = [
        {"label": "Name", "name": "user.get_full_name"},
        {"label": "Email", "name": "user.email"},
        {"label": "Phone", "name": "phone"},
        {"label": "Language", "name": "preferred_language"},
        {"label": "Verified", "name": "phone_verified", "type": "bool"},
    ]


class CustomerUpdateView(DashboardUpdateView):
    model = CustomerProfile
    form_class = forms.CustomerProfileForm
    nav_section = "customers"
    url_basename = "customer"
    singular_name = "Customer"


@dashboard_required
def customer_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Customer profile with addresses and recent orders."""
    profile = get_object_or_404(CustomerProfile.objects.select_related("user"), pk=pk)
    context = {
        "nav_section": "customers",
        "page_title": str(profile),
        "profile": profile,
        "addresses": profile.addresses.select_related("city").all(),
        "orders": profile.orders.order_by("-created_at")[:10],
    }
    return render(request, "dashboard/customers/detail.html", context)


class CorporateListView(DashboardListView):
    model = CorporateAccount
    nav_section = "corporate"
    url_basename = "corporate"
    singular_name = "Corporate Account"
    plural_name = "Corporate Accounts"
    search_fields = ["company_name", "trade_license_number", "user__email"]
    select_related = ["user"]
    can_create = False
    can_delete = False
    columns = [
        {"label": "Company", "name": "company_name"},
        {"label": "License", "name": "trade_license_number"},
        {"label": "Contact", "name": "user.email"},
        {"label": "Status", "name": "get_approval_status_display", "type": "badge"},
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(approval_status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["extra_filters"] = CorporateApprovalStatus.choices
        context["current_status"] = self.request.GET.get("status", "")
        return context


class CorporateUpdateView(DashboardUpdateView):
    model = CorporateAccount
    form_class = forms.CorporateAccountForm
    nav_section = "corporate"
    url_basename = "corporate"
    singular_name = "Corporate Account"

    def form_valid(self, form):
        status = form.cleaned_data.get("approval_status")
        if status in {CorporateApprovalStatus.APPROVED, CorporateApprovalStatus.REJECTED}:
            form.instance.approved_by = self.request.user

        response = super().form_valid(form)

        if status == CorporateApprovalStatus.APPROVED:
            from notifications.models import Notification
            account = form.instance
            Notification.objects.filter(
                title="New corporate account pending approval",
                body=f"{account.company_name} ({account.trade_license_number}) awaits review."
            ).delete()

        return response
