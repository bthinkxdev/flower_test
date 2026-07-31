"""Synchronize the permanent parent/collection catalog taxonomy."""

from django.core.management.base import BaseCommand

from catalog.taxonomy import sync_story_of_flowers_taxonomy


class Command(BaseCommand):
    help = "Create navigation parents and attach Story of Flowers collections."

    def handle(self, *args, **options):
        result = sync_story_of_flowers_taxonomy()
        self.stdout.write(
            self.style.SUCCESS(
                "Taxonomy synchronized: "
                f"{result['parent_count']} parents, "
                f"{result['collections_assigned']} collections assigned."
            )
        )
