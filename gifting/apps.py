"""Gifting application configuration."""

from __future__ import annotations

from django.apps import AppConfig


class GiftingConfig(AppConfig):
    """Django app config for plug-and-play gift customization via ContentType."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "gifting"
    verbose_name = "Gifting"

    def ready(self) -> None:
        """Import signal modules when Django starts."""
        import gifting.signals  # noqa: F401
