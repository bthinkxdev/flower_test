"""Backfill *_en from residual original columns, then auto-translate to *_ar."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection

from core.translation.registry import (
    get_translated_json_fields,
    populate_registry,
    TRANSLATED_FIELDS,
)
from core.translation.service import translate_and_save


def _column_names(table: str) -> set[str]:
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return {col.name for col in description}


class Command(BaseCommand):
    help = (
        "Copy legacy original-field values into *_en, then run translate_and_save "
        "for every registered translatable model."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--translate-only",
            action="store_true",
            help="Skip EN backfill; only call translate_and_save.",
        )
        parser.add_argument(
            "--copy-only",
            action="store_true",
            help="Only copy original → *_en; do not call the translator.",
        )

    def handle(self, *args, **options) -> None:
        populate_registry()
        copy_only = options["copy_only"]
        translate_only = options["translate_only"]

        if not translate_only:
            self._copy_english_sources()

        if not copy_only:
            self._translate_all()

        self.stdout.write(self.style.SUCCESS("Content translation backfill complete."))

    def _copy_english_sources(self) -> None:
        for model, fields in TRANSLATED_FIELDS.items():
            table = model._meta.db_table
            columns = _column_names(table)
            json_fields = get_translated_json_fields(model)
            for field in fields + json_fields:
                en_col = f"{field}_en"
                if field not in columns or en_col not in columns:
                    self.stdout.write(
                        f"  skip {table}.{field} (missing column)"
                    )
                    continue
                if field in json_fields:
                    sql = (
                        f'UPDATE "{table}" SET "{en_col}" = "{field}" '
                        f'WHERE "{en_col}" IS NULL '
                        f'AND "{field}" IS NOT NULL'
                    )
                else:
                    sql = (
                        f'UPDATE "{table}" SET "{en_col}" = "{field}" '
                        f'WHERE ("{en_col}" IS NULL OR "{en_col}" = \'\') '
                        f'AND "{field}" IS NOT NULL AND "{field}" <> \'\''
                    )
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    self.stdout.write(
                        f"  copied {table}.{field} → {en_col} ({cursor.rowcount} rows)"
                    )

    def _translate_all(self) -> None:
        for model in TRANSLATED_FIELDS:
            qs = model.objects.all().iterator()
            count = 0
            for instance in qs:
                # Force AUTO path for backfill of empty Arabic; respect MANUAL.
                translate_and_save(instance)
                count += 1
            self.stdout.write(f"  translated {model.__name__}: {count} rows")
