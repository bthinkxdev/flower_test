"""HTTP views for the gifting app; thin request parsing delegating to selectors/services."""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from catalog.selectors import get_product_detail
from delivery.selectors import get_available_delivery_slots
from gifting.constants import PERSONAL_MESSAGE_MAX_LENGTH
from gifting.exceptions import GiftCustomizationValidationError
from gifting.forms import GiftBuilderForm
from gifting.selectors import (
    get_active_gift_wrap_options,
    get_active_photo_upload_options,
    get_active_ribbon_options,
    get_available_greeting_cards,
    get_eligible_addons,
    get_gift_customization_config,
    get_gift_customization_snapshot,
    get_line_item_ref_by_id,
)
from gifting.services import build_gift_customization_snapshot, create_line_item_reference


def _get_line_item_ref(*, request: HttpRequest, slug: str):
    session_key = f"gift_line_item:{slug}"
    ref_id = request.session.get(session_key)
    if ref_id:
        ref = get_line_item_ref_by_id(line_item_id=ref_id)
        if ref:
            return ref
    ref = create_line_item_reference()
    request.session[session_key] = ref.pk
    return ref


def _builder_context(*, request: HttpRequest, product, line_item_ref) -> dict:
    config = get_gift_customization_config(product_instance=product, request=request)
    if config is None:
        raise Http404("Gift customization is not available for this product.")
    occasion_id = getattr(product, "primary_occasion_id", None)
    snapshot = get_gift_customization_snapshot(line_item_reference=line_item_ref)
    selected_addon_ids: list[int] = []
    if snapshot is not None:
        selected_addon_ids = [row.addon_product_id for row in snapshot.snapshot_addons.all()]
    return {
        "product": product,
        "config": config,
        "line_item_ref": line_item_ref,
        "greeting_cards": get_available_greeting_cards(occasion_id=occasion_id),
        "gift_wrap_options": get_active_gift_wrap_options(),
        "ribbon_options": get_active_ribbon_options(),
        "photo_upload_options": get_active_photo_upload_options(),
        "eligible_addons": get_eligible_addons(product_instance=product),
        "delivery_slots": get_available_delivery_slots(
            allow_midnight=config.allows_midnight_delivery,
        ),
        "message_max_length": PERSONAL_MESSAGE_MAX_LENGTH,
        "snapshot": snapshot,
        "selected_addon_ids": selected_addon_ids,
    }


@require_GET
def gift_builder_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the HTMX-driven gift builder for a catalog product."""
    product = get_product_detail(slug=slug)
    if product is None:
        raise Http404("Product not found.")
    line_item_ref = _get_line_item_ref(request=request, slug=slug)
    context = _builder_context(request=request, product=product, line_item_ref=line_item_ref)
    return render(request, "gifting/builder.html", context)


@require_http_methods(["GET", "POST"])
def gift_builder_preview_view(request: HttpRequest, line_item_id: int) -> HttpResponse:
    """
    HTMX endpoint: validate selections, persist snapshot, return Order Preview partial.

    Reused verbatim by cart (Phase 6), checkout (Phase 6), and order confirmation
    (Phase 7) via ``get_gift_customization_snapshot`` + the same partial template.
    """
    line_item_ref = get_line_item_ref_by_id(line_item_id=line_item_id)
    if line_item_ref is None:
        raise Http404("Line item not found.")

    slug = request.GET.get("product_slug") or request.POST.get("product_slug")
    if not slug:
        raise Http404("Product slug required.")
    product = get_product_detail(slug=slug)
    if product is None:
        raise Http404("Product not found.")

    context = _builder_context(request=request, product=product, line_item_ref=line_item_ref)

    if request.method == "POST":
        form = GiftBuilderForm(request.POST)
        if form.is_valid():
            try:
                build_gift_customization_snapshot(
                    product_instance=product,
                    selections=form.to_selections(),
                    line_item_reference=line_item_ref,
                )
                context["snapshot"] = get_gift_customization_snapshot(
                    line_item_reference=line_item_ref
                )
                context["success"] = True
            except GiftCustomizationValidationError as exc:
                context["field_errors"] = exc.as_dict()
        else:
            context["field_errors"] = form.errors

    return render(request, "gifting/partials/order_preview.html", context)


@require_http_methods(["POST"])
def gift_message_preview_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial: live personal-message character counter and preview."""
    message = (request.POST.get("personal_message") or "").strip()
    return render(
        request,
        "gifting/partials/message_preview.html",
        {
            "message": message,
            "message_max_length": PERSONAL_MESSAGE_MAX_LENGTH,
        },
    )
