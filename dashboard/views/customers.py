"""Customer and corporate account management."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from accounts.models import CorporateAccount, CorporateApprovalStatus, CustomerProfile
from dashboard import forms
from dashboard.access import dashboard_required
from dashboard.views.base import DashboardListView, DashboardUpdateView


import datetime
from dataclasses import dataclass
from orders.models import Order
from django.db.models import Max

@dataclass
class CustomerItem:
    pk: int
    name: str
    email: str
    phone: str
    preferred_language: str
    phone_verified: bool
    is_guest: bool
    latest_activity: datetime.datetime

class CustomerListView(DashboardListView):
    model = CustomerProfile
    nav_section = "customers"
    url_basename = "customer"
    singular_name = "Customer"
    plural_name = "Customers"
    search_fields = ["name", "email", "phone"]
    can_create = False
    can_delete = False
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Email", "name": "email"},
        {"label": "Phone", "name": "phone"},
        {"label": "Language", "name": "preferred_language"},
        {"label": "Verified", "name": "phone_verified", "type": "bool"},
    ]

    def get_queryset(self):
        query = self.request.GET.get("q", "").strip().lower()
        items = []

        seen_emails = set()
        
        #1.logged customers
        profiles = CustomerProfile.objects.select_related("user").prefetch_related("addresses").annotate(
            latest_order=Max('orders__created_at')
        )
        for p in profiles:
            name = p.user.get_full_name().strip()
            if not name:
                default_address = p.addresses.filter(is_default=True).first() or p.addresses.first()
                if default_address:
                    name = default_address.contact_name
            
            phone = p.phone
            if not phone:
                default_address = p.addresses.filter(is_default=True).first() or p.addresses.first()
                if default_address:
                    phone = default_address.phone
            
            email = p.user.email
            if email:
                seen_emails.add(email.strip())
            
            if query:
                search_target = f"{name} {email} {phone}".lower()
                if query not in search_target:
                    continue
                    
            items.append(CustomerItem(
                pk=p.pk,
                name=name or "",
                email=email or "",
                phone=phone or "",
                preferred_language=p.preferred_language,
                phone_verified=p.phone_verified,
                is_guest=False,
                latest_activity=p.latest_order or p.created_at
            ))

        #2.guest customers
        guest_orders = Order.objects.filter(customer_profile__isnull=True).exclude(delivery_address_snapshot={}).order_by('-created_at')
        
        for o in guest_orders:
            snap = o.delivery_address_snapshot
            if not isinstance(snap, dict):
                continue
                
            email = snap.get("guest_email", "").strip()
            if not email or email in seen_emails:
                continue
                
            name = snap.get("guest_name", "").strip()
            phone = snap.get("guest_phone", "").strip()
            
            if query:
                search_target = f"{name} {email} {phone}".lower()
                if query not in search_target:
                    continue
                    
            seen_emails.add(email)
            items.append(CustomerItem(
                pk=0,
                name=name,
                email=email,
                phone=phone,
                preferred_language="en",
                phone_verified=False,
                is_guest=True,
                latest_activity=o.created_at
            ))

        items.sort(key=lambda x: x.latest_activity, reverse=True)
        return items


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
