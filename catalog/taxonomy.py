"""Stable Story of Flowers category taxonomy.

Excel rows describe sellable collections. The storefront groups those
collections beneath a small, permanent set of navigation parents.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from catalog.models import Category
from catalog.selectors import invalidate_category_tree_cache
from core.models import ArTranslationSource


@dataclass(frozen=True)
class CategoryGroup:
    slug: str
    name_en: str
    name_ar: str
    display_order: int
    collections: tuple[str, ...]


CATEGORY_GROUPS: tuple[CategoryGroup, ...] = (
    CategoryGroup(
        slug="flower-collections",
        name_en="Flower Collections",
        name_ar="مجموعات الزهور",
        display_order=10,
        collections=(
            "Flower Bouquets",
            "Bridal Bouquets",
            "Budget Flowers (Below 100 QR)",
            "Flower Bouquet Under 200 QR",
            "FLOWER VASE ARRANGEMENT",
            "Premium Flower Arrangements",
            "Rose Bundles",
            "Rose Petals",
            "Table Arrangements",
        ),
    ),
    CategoryGroup(
        slug="gift-collections",
        name_en="Gift Collections",
        name_ar="مجموعات الهدايا",
        display_order=20,
        collections=(
            "Flower Bouquets With Chocolates",
            "FLOWER WITH PERFUMES",
            "FLOWER WITH WATCH",
            "Flowers With Gifts",
            "ROSE WITH CYCLE AND TOYS",
        ),
    ),
    CategoryGroup(
        slug="occasions",
        name_en="Occasions",
        name_ar="المناسبات",
        display_order=30,
        collections=(
            "Anniversary Special",
            "Birthday Special",
            "Congratulations Bouquets",
            "FATHERS DAY SPECIAL",
            "GET WELL SOON",
            "GRADUATION FLOWER NECKLACE",
            "Graduation Special Arrangements",
            "Hajj and Umra Special Arrangement",
            "MOTHERS DAY SPECIAL ARRANGEMENT",
            "New Born Baby Flower Arrangements",
            "TEACHERS DAY SPECIAL",
            "Valentines Special",
        ),
    ),
    CategoryGroup(
        slug="seasonal-collections",
        name_en="Seasonal Collections",
        name_ar="المجموعات الموسمية",
        display_order=40,
        collections=(
            "Eid Al Adha Special",
            "Eid Special Arrangements",
            "GARANGAO SPECIAL",
            "Ramadan Special",
        ),
    ),
)

CATEGORY_PARENT_BY_CHILD: dict[str, CategoryGroup] = {
    child: group for group in CATEGORY_GROUPS for child in group.collections
}


@transaction.atomic
def sync_story_of_flowers_taxonomy() -> dict[str, int]:
    """Create permanent parent groups and attach every imported collection."""
    parents: dict[str, Category] = {}
    created_parents = 0
    assigned_collections = 0

    for group in CATEGORY_GROUPS:
        parent, created = Category.objects.update_or_create(
            slug=group.slug,
            defaults={
                "name": group.name_en,
                "name_en": group.name_en,
                "name_ar": group.name_ar,
                "parent": None,
                "display_order": group.display_order,
                "is_active": True,
                "ar_translation_source": ArTranslationSource.MANUAL,
                "meta_title": group.name_en[:70],
                "meta_title_en": group.name_en[:70],
                "meta_title_ar": group.name_ar[:70],
            },
        )
        parents[group.slug] = parent
        created_parents += int(created)

    for group in CATEGORY_GROUPS:
        parent = parents[group.slug]
        for child_order, child_name in enumerate(group.collections, start=1):
            updated = Category.objects.filter(name_en=child_name).update(
                parent=parent,
                display_order=child_order * 10,
            )
            assigned_collections += updated

    invalidate_category_tree_cache()
    return {
        "parent_count": len(parents),
        "parents_created": created_parents,
        "collections_assigned": assigned_collections,
    }
