"""Corporate application configuration."""

from __future__ import annotations

from django.apps import AppConfig


class CorporateConfig(AppConfig):
    """Django app config for B2B corporate accounts and bulk ordering."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "corporate"
    verbose_name = "Corporate"

    def ready(self) -> None:
        """Import signal modules when Django starts."""
        import corporate.signals  # noqa: F401
