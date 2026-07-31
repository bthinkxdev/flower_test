"""Build and write the full 1212-product Excel↔image mapping JSON."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from catalog.import_mapping import DEFAULT_MAP_JSON, write_mapping_json


class Command(BaseCommand):
    help = "Regenerate data/import/product_image_mapping_report.json for all Excel products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--xlsx",
            type=str,
            default="",
            help="Optional path to Excel workbook.",
        )
        parser.add_argument(
            "--out",
            type=str,
            default="",
            help="Optional output JSON path.",
        )

    def handle(self, *args, **options):
        xlsx = Path(options["xlsx"]) if options["xlsx"] else None
        out = Path(options["out"]) if options["out"] else DEFAULT_MAP_JSON
        path = write_mapping_json(out_path=out, xlsx_path=xlsx)
        data = path.read_text(encoding="utf-8")
        # Avoid loading huge JSON twice for print — read summary via write return path
        import json

        report = json.loads(data)
        summary = report["summary"]
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
        self.stdout.write(
            f"products={summary['product_count']} "
            f"matched={summary['matched_any']} "
            f"rate={summary['match_rate_pct']}% "
            f"statuses={summary['status_counts']}"
        )
