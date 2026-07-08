"""Delivery configuration: cities and delivery slots."""

from __future__ import annotations

from dashboard import forms
from dashboard.views.base import (
    DashboardCreateView,
    DashboardDeleteView,
    DashboardListView,
    DashboardUpdateView,
)
from delivery.models import City, DeliverySlot


class CityListView(DashboardListView):
    model = City
    nav_section = "cities"
    url_basename = "city"
    singular_name = "City"
    plural_name = "Cities"
    search_fields = ["name", "slug"]
    select_related = ["country"]
    columns = [
        {"label": "City", "name": "name"},
        {"label": "Country", "name": "country.name"},
        {"label": "Delivery charge", "name": "delivery_charge_base", "type": "money"},
        {"label": "Same-day cutoff", "name": "same_day_cutoff_hour"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class CityCreateView(DashboardCreateView):
    model = City
    form_class = forms.CityForm
    nav_section = "cities"
    url_basename = "city"
    singular_name = "City"


class CityUpdateView(DashboardUpdateView):
    model = City
    form_class = forms.CityForm
    nav_section = "cities"
    url_basename = "city"
    singular_name = "City"


class CityDeleteView(DashboardDeleteView):
    model = City
    nav_section = "cities"
    url_basename = "city"
    singular_name = "City"


class DeliverySlotListView(DashboardListView):
    model = DeliverySlot
    nav_section = "slots"
    url_basename = "slot"
    singular_name = "Delivery Slot"
    plural_name = "Delivery Slots"
    search_fields = ["name"]
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Start", "name": "start_time"},
        {"label": "End", "name": "end_time"},
        {"label": "Type", "name": "get_slot_type_display"},
        {"label": "Capacity", "name": "max_capacity_per_day"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class DeliverySlotCreateView(DashboardCreateView):
    model = DeliverySlot
    form_class = forms.DeliverySlotForm
    nav_section = "slots"
    url_basename = "slot"
    singular_name = "Delivery Slot"


class DeliverySlotUpdateView(DashboardUpdateView):
    model = DeliverySlot
    form_class = forms.DeliverySlotForm
    nav_section = "slots"
    url_basename = "slot"
    singular_name = "Delivery Slot"


class DeliverySlotDeleteView(DashboardDeleteView):
    model = DeliverySlot
    nav_section = "slots"
    url_basename = "slot"
    singular_name = "Delivery Slot"
