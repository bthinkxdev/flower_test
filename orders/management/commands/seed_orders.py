"""
Seed ~20 realistic orders across every ordering mode the platform supports.

Modes exercised
---------------
* Standard single-item and multi-item orders
* Orders with a product variant
* Gift-customized orders (personal message, greeting card, wrap, ribbon)
* Gift with paid add-ons
* Gift with "anonymous" + "gift receipt" flags
* Gift with photo upload + midnight delivery (config-gated)
* Coupon orders (percentage and fixed)
* Scheduled delivery with a booked delivery slot (+ saved address)
* Guest checkout (no customer profile)
* Bulk-quantity order
* Corporate (B2B) order via the corporate quote → convert pipeline
* Subscription-originated order via the recurring engine

Everything flows through the *real* services (cart → checkout → place_order,
gifting snapshot builder, delivery slot reservation, coupon redemption), so the
seeded data is faithful to production behaviour. Orders are then walked through
the order state machine, paid, back-dated across the last two weeks, and the
daily report tables are aggregated so the dashboard and reports show live data.

Usage
-----
    python manage.py seed_orders                # create/refresh seed orders
    python manage.py seed_orders --reset         # delete previous seed orders first
    python manage.py seed_orders --count 20      # (informational cap; see notes)
"""

from __future__ import annotations

import random
import uuid
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Address, CorporateAccount, CorporateApprovalStatus, CustomerProfile
from accounts.services import ensure_customer_profile_for_user, register_customer_email
from accounts.subscription_services import create_subscription, execute_subscription_recurrence
from cart.models import Cart
from cart.services import add_to_cart, apply_coupon
from catalog.models import Product, ProductVariant, VariantType
from checkout.services import create_checkout_session, place_order, update_checkout_session
from core.selectors import get_default_currency
from corporate.models import CorporateQuoteStatus
from corporate.services import approve_and_convert_to_order, request_corporate_quote
from delivery.models import City, DeliverySlot, DeliverySlotType
from gifting.models import (
    GiftAddonEligibility,
    GiftPhotoUploadOption,
    GiftWrapName,
    GiftWrapOption,
    GreetingCardDesign,
    RibbonName,
    RibbonOption,
)
from gifting.services import ensure_gift_customization_config
from marketing.models import Coupon, CouponDiscountType
from orders.exceptions import InvalidOrderStatusTransitionError
from orders.models import Order, OrderStatus, OrderStatusHistory, ProofOfDelivery
from orders.services import transition_order_status
from payments.models import PaymentStatus, PaymentTransaction

User = get_user_model()

SEED_KEY_PREFIXES = ("seed-", "corporate-", "recurring-sub-")
SEED_EMAIL_DOMAIN = "seed.floward.test"

LINEAR_FLOW = [
    OrderStatus.RECEIVED,
    OrderStatus.PREPARING,
    OrderStatus.PACKAGING,
    OrderStatus.READY,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
]


class Command(BaseCommand):
    help = "Seed ~20 orders spanning every ordering mode (gifting, coupons, corporate, etc.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded orders (and their payments) before seeding.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=20,
            help="Informational target order count (the scenario matrix defines the real set).",
        )

    def handle(self, *args, **options):
        self.rng = random.Random(20260709)
        self.now = timezone.now()

        if options["reset"]:
            self._reset()

        self.currency = get_default_currency()
        if self.currency is None:
            self.stderr.write(self.style.ERROR("No default currency configured. Aborting."))
            return

        products = list(
            Product.objects.filter(is_active=True, supports_gift_customization=True).order_by("pk")
        )
        if len(products) < 6:
            products = list(Product.objects.filter(is_active=True).order_by("pk"))
        if not products:
            self.stderr.write(self.style.ERROR("No active products found. Seed the catalog first."))
            return

        self.stdout.write("Setting up prerequisites (stock, slots, gift options, customers)...")
        self._ensure_stock(products)
        city = self._ensure_city()
        slots = self._ensure_slots()
        self._ensure_gift_options(products)
        cards_by_occasion = self._ensure_greeting_cards(products)
        addon_products, addon_target = self._ensure_addons(products)
        customers = self._ensure_customers(city)
        self._ensure_coupons()

        self.stdout.write("Placing orders across all ordering modes...")
        placed: list[tuple[Order, OrderStatus, str]] = []

        scenarios = self._build_scenarios(
            products=products,
            customers=customers,
            slots=slots,
            cards_by_occasion=cards_by_occasion,
            addon_products=addon_products,
            addon_target=addon_target,
        )

        for idx, sc in enumerate(scenarios, start=1):
            idem = f"seed-{idx:02d}"
            try:
                order = self._place(idem_key=idem, **sc["place"])
            except Exception as exc:  # noqa: BLE001 - report and continue seeding
                self.stderr.write(self.style.WARNING(f"  ! {sc['label']}: {exc}"))
                continue
            placed.append((order, sc["status"], sc["label"]))
            self.stdout.write(f"  + [{order.order_number}] {sc['label']}")

        corp = self._place_corporate(products, city)
        if corp is not None:
            placed.append((corp, OrderStatus.PREPARING, "Corporate (B2B) converted quote"))
            self.stdout.write(f"  + [{corp.order_number}] Corporate (B2B) converted quote")

        sub = self._place_subscription(products[0], customers[0])
        if sub is not None:
            placed.append((sub, OrderStatus.DELIVERED, "Subscription recurrence order"))
            self.stdout.write(f"  + [{sub.order_number}] Subscription recurrence order")

        self.stdout.write("Advancing statuses, recording payments, back-dating...")
        for i, (order, target, _label) in enumerate(placed):
            days_ago = i % 14
            created = self.now - timedelta(days=days_ago, hours=self.rng.randint(0, 12))
            Order.objects.filter(pk=order.pk).update(created_at=created)
            order.refresh_from_db()

            is_guest = order.customer_profile_id is None
            if not is_guest and target != OrderStatus.RECEIVED:
                self._advance(order, target, actor=None)
            self._record_payment(order, created)
            if order.order_status == OrderStatus.DELIVERED:
                self._record_pod(order, created)

        self._make_some_low_stock(products)

        self.stdout.write("Aggregating daily report tables...")
        self._aggregate_reports()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {len(placed)} orders now in the system "
                f"(total orders: {Order.objects.count()})."
            )
        )

    def _reset(self) -> None:
        qs = Order.objects.none()
        for prefix in SEED_KEY_PREFIXES:
            qs = qs | Order.objects.filter(idempotency_key__startswith=prefix)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.WARNING(f"Reset: deleted {count} previously seeded orders."))

    def _ensure_stock(self, products: list[Product]) -> None:
        Product.objects.filter(is_active=True).update(stock_quantity=250, low_stock_threshold=5)

    def _ensure_city(self) -> City:
        city = City.objects.filter(is_active=True).first()
        if city is None:
            from delivery.models import Country

            country = Country.objects.first()
            city = City.objects.create(
                country=country,
                name="Doha",
                slug="doha",
                delivery_charge_base=Decimal("25.00"),
                same_day_cutoff_hour=14,
            )
        return city

    def _ensure_slots(self) -> dict[str, DeliverySlot]:
        specs = [
            ("Morning 9am–12pm", time(9, 0), time(12, 0), DeliverySlotType.MORNING),
            ("Evening 6pm–9pm", time(18, 0), time(21, 0), DeliverySlotType.EVENING),
            ("Midnight 12am–2am", time(0, 0), time(2, 0), DeliverySlotType.MIDNIGHT),
        ]
        slots: dict[str, DeliverySlot] = {}
        for name, start, end, stype in specs:
            slot, _ = DeliverySlot.objects.get_or_create(
                name=name,
                defaults={
                    "start_time": start,
                    "end_time": end,
                    "slot_type": stype,
                    "max_capacity_per_day": 50,
                    "is_active": True,
                },
            )
            slots[stype] = slot
        return slots

    def _ensure_gift_options(self, products: list[Product]) -> None:
        GiftWrapOption.objects.get_or_create(
            name=GiftWrapName.STANDARD, defaults={"price_delta": Decimal("0.00")}
        )
        GiftWrapOption.objects.get_or_create(
            name=GiftWrapName.PREMIUM, defaults={"price_delta": Decimal("15.00")}
        )
        GiftWrapOption.objects.get_or_create(
            name=GiftWrapName.LUXURY_BOX, defaults={"price_delta": Decimal("30.00")}
        )
        RibbonOption.objects.get_or_create(
            name=RibbonName.RED, defaults={"price_delta": Decimal("5.00")}
        )
        RibbonOption.objects.get_or_create(
            name=RibbonName.GOLD, defaults={"price_delta": Decimal("8.00")}
        )
        GiftPhotoUploadOption.objects.get_or_create(
            name="Printed photo card", defaults={"price_delta": Decimal("12.00")}
        )
        ensure_gift_customization_config(
            product_instance=products[3 % len(products)],
            allows_personal_message=True,
            allows_greeting_card=True,
            allows_gift_wrap=True,
            allows_ribbon=True,
            allows_addons=True,
            allows_anonymous=True,
            allows_gift_receipt=True,
            allows_photo_upload=True,
            allows_midnight_delivery=True,
        )

    def _ensure_greeting_cards(self, products: list[Product]) -> dict[int, GreetingCardDesign]:
        cards: dict[int, GreetingCardDesign] = {}
        occasion_ids = {p.primary_occasion_id for p in products}
        for occ_id in occasion_ids:
            card = GreetingCardDesign.objects.filter(occasion_id=occ_id, is_active=True).first()
            if card is None:
                card = GreetingCardDesign.objects.create(
                    name=f"Classic card ({occ_id})",
                    occasion_id=occ_id,
                    image="gifting/greeting_cards/demo.jpg",
                    is_active=True,
                )
            cards[occ_id] = card
        return cards

    def _ensure_addons(self, products: list[Product]):
        addon_target = products[5 % len(products)]
        addons = [p for p in products if p.pk != addon_target.pk][:2]
        ct = ContentType.objects.get_for_model(Product)
        for addon in addons:
            GiftAddonEligibility.objects.get_or_create(
                content_type=ct,
                object_id=addon_target.pk,
                addon_product=addon,
            )
        return addons, addon_target

    def _ensure_variant(self, product: Product) -> ProductVariant:
        variant, _ = ProductVariant.objects.get_or_create(
            product=product,
            variant_type=VariantType.SIZE,
            name="Large",
            defaults={
                "price_delta": Decimal("40.00"),
                "sku_suffix": "LG",
                "stock_quantity": 100,
            },
        )
        if variant.stock_quantity < 10:
            variant.stock_quantity = 100
            variant.save(update_fields=["stock_quantity", "updated_at"])
        return variant

    def _ensure_customers(self, city: City) -> list[CustomerProfile]:
        specs = [
            ("aisha", "Aisha Rahman", "+97455500001"),
            ("omar", "Omar Khalid", "+97455500002"),
            ("lina", "Lina Haddad", "+97455500003"),
            ("yusuf", "Yusuf Ali", "+97455500004"),
            ("mariam", "Mariam Nasser", "+97455500005"),
            ("khalid", "Khalid Saleh", "+97455500006"),
        ]
        profiles: list[CustomerProfile] = []
        for handle, name, phone in specs:
            email = f"{handle}@{SEED_EMAIL_DOMAIN}"
            profile = CustomerProfile.objects.filter(user__email=email).first()
            if profile is None:
                profile = register_customer_email(email=email, password="seedpass123", name=name)
            profile.phone = phone
            profile.phone_verified = True
            profile.save(update_fields=["phone", "phone_verified", "updated_at"])

            address, _ = Address.objects.get_or_create(
                customer_profile=profile,
                label="Home",
                defaults={
                    "line1": f"{self.rng.randint(1, 99)} Pearl Street",
                    "line2": "Villa 12",
                    "city": city,
                    "is_default": True,
                },
            )
            if profile.default_address_id != address.pk:
                profile.default_address = address
                profile.save(update_fields=["default_address", "updated_at"])
            profiles.append(profile)
        return profiles

    def _ensure_coupons(self) -> None:
        window = {
            "valid_from": self.now - timedelta(days=1),
            "valid_until": self.now + timedelta(days=60),
            "is_active": True,
        }
        Coupon.objects.get_or_create(
            code="SAVE10",
            defaults={
                "discount_type": CouponDiscountType.PERCENTAGE,
                "discount_value": Decimal("10.00"),
                "min_order_value": Decimal("0.00"),
                **window,
            },
        )
        Coupon.objects.get_or_create(
            code="FLAT50",
            defaults={
                "discount_type": CouponDiscountType.FIXED,
                "discount_value": Decimal("50.00"),
                "min_order_value": Decimal("50.00"),
                **window,
            },
        )

    def _build_scenarios(
        self, *, products, customers, slots, cards_by_occasion, addon_products, addon_target
    ) -> list[dict]:
        p = products
        c = customers
        future = timezone.localdate() + timedelta(days=2)

        def gift(product, **sel):
            occ = product.primary_occasion_id
            base = {"personal_message": "With love and warm wishes on your special day!"}
            if sel.pop("card", False) and occ in cards_by_occasion:
                base["greeting_card_id"] = cards_by_occasion[occ].pk
            base.update(sel)
            return base

        variant_product = p[2 % len(p)]
        variant = self._ensure_variant(variant_product)
        midnight_product = p[3 % len(p)]

        scenarios: list[dict] = [
            {
                "label": "Standard single-item",
                "status": OrderStatus.DELIVERED,
                "place": {"profile": c[0], "lines": [(p[0], None, 1, None)]},
            },
            {
                "label": "Standard multi-item (3 products)",
                "status": OrderStatus.OUT_FOR_DELIVERY,
                "place": {
                    "profile": c[1],
                    "lines": [(p[1], None, 1, None), (p[2], None, 2, None), (p[4], None, 1, None)],
                },
            },
            {
                "label": "Order with product variant",
                "status": OrderStatus.READY,
                "place": {"profile": c[2], "lines": [(variant_product, variant, 1, None)]},
            },
            {
                "label": "Gift: message + greeting card",
                "status": OrderStatus.PACKAGING,
                "place": {"profile": c[3], "lines": [(p[0], None, 1, gift(p[0], card=True))]},
            },
            {
                "label": "Gift: message + premium wrap + gold ribbon",
                "status": OrderStatus.PREPARING,
                "place": {
                    "profile": c[4],
                    "lines": [
                        (
                            p[1],
                            None,
                            1,
                            gift(
                                p[1],
                                card=True,
                                gift_wrap_id=self._wrap(GiftWrapName.PREMIUM),
                                ribbon_id=self._ribbon(RibbonName.GOLD),
                            ),
                        )
                    ],
                },
            },
            {
                "label": "Gift: luxury wrap + add-ons",
                "status": OrderStatus.DELIVERED,
                "place": {
                    "profile": c[5],
                    "lines": [
                        (
                            addon_target,
                            None,
                            1,
                            gift(
                                addon_target,
                                gift_wrap_id=self._wrap(GiftWrapName.LUXURY_BOX),
                                addon_product_ids=[a.pk for a in addon_products],
                            ),
                        )
                    ],
                },
            },
            {
                "label": "Gift: anonymous + gift receipt",
                "status": OrderStatus.OUT_FOR_DELIVERY,
                "place": {
                    "profile": c[0],
                    "lines": [
                        (
                            p[6 % len(p)],
                            None,
                            1,
                            gift(
                                p[6 % len(p)],
                                card=True,
                                is_anonymous=True,
                                is_gift_receipt=True,
                                reveal_sender_after_delivery=True,
                            ),
                        )
                    ],
                },
            },
            {
                "label": "Gift: photo upload + midnight delivery",
                "status": OrderStatus.PREPARING,
                "place": {
                    "profile": c[1],
                    "lines": [
                        (
                            midnight_product,
                            None,
                            1,
                            gift(
                                midnight_product,
                                photo_upload_id=self._photo(),
                                delivery_slot_id=slots[DeliverySlotType.MIDNIGHT].pk,
                                delivery_date=future.isoformat(),
                                recipient_phone="+97455512345",
                                delivery_instructions="Please ring the bell twice.",
                            ),
                        )
                    ],
                },
            },
            {
                "label": "Coupon SAVE10 (10% off)",
                "status": OrderStatus.DELIVERED,
                "place": {
                    "profile": c[2],
                    "lines": [(p[7 % len(p)], None, 2, None)],
                    "coupon_code": "SAVE10",
                },
            },
            {
                "label": "Coupon FLAT50 (fixed) on larger order",
                "status": OrderStatus.PACKAGING,
                "place": {
                    "profile": c[3],
                    "lines": [(p[8 % len(p)], None, 3, None), (p[9 % len(p)], None, 2, None)],
                    "coupon_code": "FLAT50",
                },
            },
            {
                "label": "Scheduled delivery with booked slot",
                "status": OrderStatus.READY,
                "place": {
                    "profile": c[4],
                    "lines": [(p[10 % len(p)], None, 1, None)],
                    "address": c[4].default_address,
                    "delivery_date": future,
                    "delivery_slot": slots[DeliverySlotType.MORNING],
                },
            },
            {
                "label": "Scheduled evening slot + gift",
                "status": OrderStatus.OUT_FOR_DELIVERY,
                "place": {
                    "profile": c[5],
                    "lines": [(p[11 % len(p)], None, 1, gift(p[11 % len(p)], card=True))],
                    "address": c[5].default_address,
                    "delivery_date": future,
                    "delivery_slot": slots[DeliverySlotType.EVENING],
                },
            },
            {
                "label": "Guest checkout (no account)",
                "status": OrderStatus.RECEIVED,
                "place": {
                    "profile": None,
                    "session_key": uuid.uuid4().hex,
                    "lines": [(p[12 % len(p)], None, 1, None)],
                },
            },
            {
                "label": "Guest gift order",
                "status": OrderStatus.RECEIVED,
                "place": {
                    "profile": None,
                    "session_key": uuid.uuid4().hex,
                    "lines": [(p[13 % len(p)], None, 1, gift(p[13 % len(p)], card=True))],
                },
            },
            {
                "label": "Bulk quantity order",
                "status": OrderStatus.DELIVERED,
                "place": {"profile": c[0], "lines": [(p[14 % len(p)], None, 10, None)]},
            },
            {
                "label": "Cancelled order",
                "status": OrderStatus.CANCELLED,
                "place": {"profile": c[1], "lines": [(p[15 % len(p)], None, 1, None)]},
            },
            {
                "label": "Refunded order",
                "status": OrderStatus.REFUNDED,
                "place": {"profile": c[2], "lines": [(p[16 % len(p)], None, 1, None)]},
            },
            {
                "label": "Gift multi-item with wrap + ribbon + coupon",
                "status": OrderStatus.PREPARING,
                "place": {
                    "profile": c[3],
                    "lines": [
                        (
                            p[17 % len(p)],
                            None,
                            1,
                            gift(
                                p[17 % len(p)],
                                card=True,
                                gift_wrap_id=self._wrap(GiftWrapName.PREMIUM),
                                ribbon_id=self._ribbon(RibbonName.RED),
                            ),
                        ),
                        (p[18 % len(p)], None, 1, None),
                    ],
                    "coupon_code": "SAVE10",
                },
            },
        ]
        return scenarios

    def _wrap(self, name) -> int:
        return GiftWrapOption.objects.get(name=name).pk

    def _ribbon(self, name) -> int:
        return RibbonOption.objects.get(name=name).pk

    def _photo(self) -> int:
        return GiftPhotoUploadOption.objects.first().pk

    def _place(
        self,
        *,
        idem_key: str,
        profile,
        lines,
        session_key: str = "",
        coupon_code: str | None = None,
        address=None,
        delivery_date=None,
        delivery_slot=None,
    ) -> Order:
        existing = Order.objects.filter(idempotency_key=idem_key).first()
        if existing:
            return existing

        if profile is not None:
            cart = Cart.objects.create(customer_profile=profile, currency=self.currency)
        else:
            cart = Cart.objects.create(
                session_key=session_key or uuid.uuid4().hex, currency=self.currency
            )

        for product, variant, qty, gifts in lines:
            add_to_cart(
                cart=cart,
                product=product,
                variant=variant,
                quantity=qty,
                gift_selections=gifts,
            )

        if coupon_code and profile is not None:
            apply_coupon(cart=cart, code=coupon_code)

        session = create_checkout_session(
            cart=cart, customer_profile=profile, session_key=session_key or ""
        )
        if address or delivery_date or delivery_slot:
            update_checkout_session(
                checkout_session=session,
                address=address,
                delivery_date=delivery_date,
                delivery_slot_id=delivery_slot.pk if delivery_slot else None,
            )

        return place_order(
            checkout_session_id=session.pk,
            idempotency_key=idem_key,
            customer_profile=profile,
        )

    def _place_corporate(self, products, city) -> Order | None:
        try:
            email = f"corp@{SEED_EMAIL_DOMAIN}"
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    username="corp_seed", email=email, password="seedpass123"
                )
            account, _ = CorporateAccount.objects.get_or_create(
                user=user,
                defaults={
                    "company_name": "Doha Events Co.",
                    "trade_license_number": "TL-SEED-0001",
                    "approval_status": CorporateApprovalStatus.APPROVED,
                },
            )
            if account.approval_status != CorporateApprovalStatus.APPROVED:
                account.approval_status = CorporateApprovalStatus.APPROVED
                account.save(update_fields=["approval_status", "updated_at"])

            profile = ensure_customer_profile_for_user(user=user)
            addr, _ = Address.objects.get_or_create(
                customer_profile=profile,
                label="HQ",
                defaults={"line1": "1 Corniche Rd", "city": city, "is_default": True},
            )
            if profile.default_address_id != addr.pk:
                profile.default_address = addr
                profile.save(update_fields=["default_address", "updated_at"])

            items = [
                {
                    "product_id": products[0].pk,
                    "quantity": 15,
                    "unit_price": products[0].base_price,
                },
                {
                    "product_id": products[1].pk,
                    "quantity": 10,
                    "unit_price": products[1].base_price,
                },
            ]
            corporate_order = request_corporate_quote(
                corporate_account=account,
                items=items,
                notes="Seeded corporate bulk order for a company event.",
                created_by=user,
            )
            corporate_order.quote_status = CorporateQuoteStatus.APPROVED
            corporate_order.save(update_fields=["quote_status", "updated_at"])
            return approve_and_convert_to_order(corporate_order=corporate_order)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.WARNING(f"  ! Corporate order skipped: {exc}"))
            return None

    def _place_subscription(self, product, profile) -> Order | None:
        try:
            if profile.default_address_id is None:
                return None
            subscription = create_subscription(
                customer_profile=profile,
                product_id=product.pk,
                delivery_address_id=profile.default_address_id,
                frequency="weekly",
                next_run_date=timezone.localdate(),
                quantity=1,
                created_by=profile.user,
            )
            return execute_subscription_recurrence(schedule=subscription.recurring_schedule)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.WARNING(f"  ! Subscription order skipped: {exc}"))
            return None

    def _advance(self, order: Order, target: OrderStatus, *, actor) -> None:
        try:
            if target == OrderStatus.CANCELLED:
                transition_order_status(
                    order=order, new_status=OrderStatus.CANCELLED, actor=actor, note="Seed cancel"
                )
                return
            path = list(LINEAR_FLOW)
            if target == OrderStatus.REFUNDED:
                target_index = len(path) - 1
            else:
                target_index = path.index(target)
            for status in path[1 : target_index + 1]:
                transition_order_status(order=order, new_status=status, actor=actor, note="Seed")
            if target == OrderStatus.REFUNDED:
                transition_order_status(
                    order=order, new_status=OrderStatus.REFUNDED, actor=actor, note="Seed refund"
                )
        except (InvalidOrderStatusTransitionError, Exception) as exc:  # noqa: BLE001
            self.stderr.write(
                self.style.WARNING(f"  ~ status fallback for {order.order_number}: {exc}")
            )
            from_status = order.order_status
            Order.objects.filter(pk=order.pk).update(order_status=target)
            OrderStatusHistory.objects.create(
                order=order, from_status=from_status, to_status=target, note="Seed (forced)"
            )
            order.refresh_from_db()

    def _record_payment(self, order: Order, when) -> None:
        if order.payment_transactions.exists():
            return
        gateway = self.rng.choice(["card", "applepay", "gift_voucher", "benefit"])
        if order.order_status in {OrderStatus.CANCELLED}:
            status = PaymentStatus.FAILED
        elif order.order_status == OrderStatus.RECEIVED:
            status = self.rng.choice([PaymentStatus.PENDING, PaymentStatus.SUCCESS])
        else:
            status = PaymentStatus.SUCCESS
        tx = PaymentTransaction.objects.create(
            order=order,
            gateway_key=gateway,
            amount=order.total_amount,
            currency=order.currency or self.currency,
            status=status,
            external_transaction_id=f"seed_{uuid.uuid4().hex[:12]}",
            metadata={"seed": True},
        )
        PaymentTransaction.objects.filter(pk=tx.pk).update(created_at=when)

    def _record_pod(self, order: Order, when) -> None:
        ProofOfDelivery.objects.get_or_create(
            order=order,
            defaults={
                "delivered_at": when,
                "recipient_name": "Recipient",
                "photo_url": "https://example.com/pod/seed.jpg",
            },
        )

    def _make_some_low_stock(self, products: list[Product]) -> None:
        for product in products[-3:]:
            Product.objects.filter(pk=product.pk).update(stock_quantity=2, low_stock_threshold=5)

    def _aggregate_reports(self) -> None:
        from reports.services import aggregate_daily_reports

        today = timezone.localdate()
        for offset in range(0, 15):
            day = today - timedelta(days=offset)
            try:
                aggregate_daily_reports(report_date=day)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.WARNING(f"  ! aggregate {day} failed: {exc}"))
