"""Gift-option-library management: greeting cards, wrap, ribbon, photo upload."""

from __future__ import annotations

from dashboard import forms
from dashboard.views.base import (
    DashboardCreateView,
    DashboardDeleteView,
    DashboardListView,
    DashboardUpdateView,
)
from gifting.models import GiftPhotoUploadOption, GiftWrapOption, GreetingCardDesign, RibbonOption


class GreetingCardListView(DashboardListView):
    model = GreetingCardDesign
    nav_section = "greetingcards"
    url_basename = "greetingcard"
    singular_name = "Greeting Card"
    plural_name = "Greeting Cards"
    search_fields = ["name"]
    select_related = ["occasion"]
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Occasion", "name": "occasion.name"},
        {"label": "Image", "name": "image", "type": "image"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class GreetingCardCreateView(DashboardCreateView):
    model = GreetingCardDesign
    form_class = forms.GreetingCardDesignForm
    nav_section = "greetingcards"
    url_basename = "greetingcard"
    singular_name = "Greeting Card"


class GreetingCardUpdateView(DashboardUpdateView):
    model = GreetingCardDesign
    form_class = forms.GreetingCardDesignForm
    nav_section = "greetingcards"
    url_basename = "greetingcard"
    singular_name = "Greeting Card"


class GreetingCardDeleteView(DashboardDeleteView):
    model = GreetingCardDesign
    nav_section = "greetingcards"
    url_basename = "greetingcard"
    singular_name = "Greeting Card"


class GiftWrapListView(DashboardListView):
    model = GiftWrapOption
    nav_section = "giftwrap"
    url_basename = "giftwrap"
    singular_name = "Gift Wrap Option"
    plural_name = "Gift Wrap Options"
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Price delta", "name": "price_delta", "type": "money"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class GiftWrapCreateView(DashboardCreateView):
    model = GiftWrapOption
    form_class = forms.GiftWrapOptionForm
    nav_section = "giftwrap"
    url_basename = "giftwrap"
    singular_name = "Gift Wrap Option"


class GiftWrapUpdateView(DashboardUpdateView):
    model = GiftWrapOption
    form_class = forms.GiftWrapOptionForm
    nav_section = "giftwrap"
    url_basename = "giftwrap"
    singular_name = "Gift Wrap Option"


class GiftWrapDeleteView(DashboardDeleteView):
    model = GiftWrapOption
    nav_section = "giftwrap"
    url_basename = "giftwrap"
    singular_name = "Gift Wrap Option"


class RibbonListView(DashboardListView):
    model = RibbonOption
    nav_section = "ribbons"
    url_basename = "ribbon"
    singular_name = "Ribbon Option"
    plural_name = "Ribbon Options"
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Price delta", "name": "price_delta", "type": "money"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class RibbonCreateView(DashboardCreateView):
    model = RibbonOption
    form_class = forms.RibbonOptionForm
    nav_section = "ribbons"
    url_basename = "ribbon"
    singular_name = "Ribbon Option"


class RibbonUpdateView(DashboardUpdateView):
    model = RibbonOption
    form_class = forms.RibbonOptionForm
    nav_section = "ribbons"
    url_basename = "ribbon"
    singular_name = "Ribbon Option"


class RibbonDeleteView(DashboardDeleteView):
    model = RibbonOption
    nav_section = "ribbons"
    url_basename = "ribbon"
    singular_name = "Ribbon Option"


class PhotoUploadOptionListView(DashboardListView):
    model = GiftPhotoUploadOption
    nav_section = "photouploadoptions"
    url_basename = "photouploadoption"
    singular_name = "Photo Upload Option"
    plural_name = "Photo Upload Options"
    search_fields = ["name"]
    columns = [
        {"label": "Name", "name": "name"},
        {"label": "Price delta", "name": "price_delta", "type": "money"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class PhotoUploadOptionCreateView(DashboardCreateView):
    model = GiftPhotoUploadOption
    form_class = forms.GiftPhotoUploadOptionForm
    nav_section = "photouploadoptions"
    url_basename = "photouploadoption"
    singular_name = "Photo Upload Option"


class PhotoUploadOptionUpdateView(DashboardUpdateView):
    model = GiftPhotoUploadOption
    form_class = forms.GiftPhotoUploadOptionForm
    nav_section = "photouploadoptions"
    url_basename = "photouploadoption"
    singular_name = "Photo Upload Option"


class PhotoUploadOptionDeleteView(DashboardDeleteView):
    model = GiftPhotoUploadOption
    nav_section = "photouploadoptions"
    url_basename = "photouploadoption"
    singular_name = "Photo Upload Option"