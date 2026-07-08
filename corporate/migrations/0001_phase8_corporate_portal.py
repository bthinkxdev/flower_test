# Phase 8 — corporate portal models

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0002_phase7_notification_preferences"),
        ("catalog", "0001_phase3_product_catalog"),
        ("orders", "0003_phase7_delivery_order_tracking"),
        ("recurring", "0001_phase8_recurring_engine"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorporateOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("is_recurring", models.BooleanField(default=False)),
                (
                    "quote_status",
                    models.CharField(
                        choices=[
                            ("requested", "Requested"),
                            ("quoted", "Quoted"),
                            ("approved", "Approved"),
                            ("ordered", "Ordered"),
                        ],
                        db_index=True,
                        default="requested",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "corporate_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="corporate_orders",
                        to="accounts.corporateaccount",
                    ),
                ),
                (
                    "recurring_schedule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="corporate_orders",
                        to="recurring.recurringschedule",
                    ),
                ),
                (
                    "retail_order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="corporate_orders",
                        to="orders.order",
                    ),
                ),
            ],
            options={"verbose_name": "Corporate order", "verbose_name_plural": "Corporate orders"},
        ),
        migrations.CreateModel(
            name="CorporateOrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "corporate_order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="corporate.corporateorder",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="corporate_order_items",
                        to="catalog.product",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="corporate_order_items",
                        to="catalog.productvariant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Corporate order item",
                "verbose_name_plural": "Corporate order items",
            },
        ),
        migrations.CreateModel(
            name="CorporateInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("pdf_url", models.URLField()),
                ("generated_at", models.DateTimeField()),
                (
                    "corporate_order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoices",
                        to="corporate.corporateorder",
                    ),
                ),
            ],
            options={
                "verbose_name": "Corporate invoice",
                "verbose_name_plural": "Corporate invoices",
                "ordering": ["-generated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="corporateorder",
            index=models.Index(
                fields=["corporate_account", "quote_status"],
                name="corp_order_account_status_idx",
            ),
        ),
    ]
