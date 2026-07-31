"""Purge catalog products, categories, orders, and related storefront test data."""

from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction


def _delete(model_label: str) -> int:
    try:
        model = apps.get_model(model_label)
    except LookupError:
        return 0
    count = model.objects.count()
    if count:
        model.objects.all().delete()
    return count


class Command(BaseCommand):
    help = (
        "Delete products, categories, orders, carts, checkout sessions, payments, "
        "wishlists, reviews, and related test transactional data. Keeps delivery, "
        "currency, CMS structure, and gift wrap/card design options."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Required confirmation flag to actually delete data.",
        )
        parser.add_argument(
            "--keep-brands-occasions",
            action="store_true",
            help="Do not delete brands/occasions/recipients.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["yes"]:
            self.stderr.write(
                self.style.ERROR("Refusing to purge without --yes confirmation.")
            )
            return

        deleted: dict[str, int] = {}

        # Order matters for clarity; CASCADE handles most FKs.
        purge_labels = [
            "payments.PaymentTransaction",
            "orders.ProofOfDelivery",
            "orders.OrderStatusHistory",
            "orders.OrderItem",
            "orders.Order",
            "checkout.CheckoutSession",
            "cart.CartItem",
            "cart.Cart",
            "gifting.GiftSnapshotAddon",
            "gifting.GiftCustomizationSnapshot",
            "gifting.GiftAddonEligibility",
            "gifting.GiftCardEligibility",
            "gifting.GiftWrapEligibility",
            "gifting.RibbonEligibility",
            "gifting.GiftPhotoUploadEligibility",
            "accounts.WishlistItem",
            "accounts.GiftReminder",
            "accounts.Subscription",
            "recurring.RecurringSchedule",
            "corporate.CorporateOrderItem",
            "corporate.CorporateOrder",
            "reports.DailyProductPerformance",
            "reports.InventorySnapshot",
            "marketing.CartRecoveryLog",
            "marketing.CouponRedemption",
            "marketing.FlashSale",
            "marketing.Coupon",
            "catalog.ReviewPhoto",
            "catalog.Review",
            "catalog.ProductRelation",
            "catalog.ProductVideo",
            "catalog.ProductImage",
            "catalog.ProductVariant",
            "catalog.Product",
            "catalog.Category",
        ]

        for label in purge_labels:
            deleted[label] = _delete(label)

        if not options["keep_brands_occasions"]:
            # Occasions are referenced by GreetingCardDesign (PROTECT) — keep them.
            for label in ("catalog.Brand", "catalog.Recipient"):
                deleted[label] = _delete(label)
            deleted["catalog.Occasion"] = 0
            self.stdout.write(
                "  catalog.Occasion: kept (referenced by greeting card designs)"
            )

        # Clear product id lists from homepage section configs.
        try:
            HomepageSection = apps.get_model("cms.HomepageSection")
            cleared = 0
            for section in HomepageSection.objects.all():
                changed = False
                for field in ("config", "config_en", "config_ar"):
                    cfg = getattr(section, field, None)
                    if isinstance(cfg, dict) and cfg:
                        new_cfg = dict(cfg)
                        for key in list(new_cfg.keys()):
                            if "product" in key.lower():
                                new_cfg[key] = [] if isinstance(new_cfg[key], list) else None
                                changed = True
                        if changed:
                            setattr(section, field, new_cfg)
                if changed:
                    section.save(update_fields=["config", "config_en", "config_ar", "updated_at"])
                    cleared += 1
            deleted["cms.HomepageSection.config_product_refs"] = cleared
        except LookupError:
            pass

        self.stdout.write(self.style.SUCCESS("Purge complete."))
        for label, count in deleted.items():
            if count:
                self.stdout.write(f"  {label}: {count}")
