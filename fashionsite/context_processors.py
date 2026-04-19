"""Custom template context processors for the fashionsite project."""
from __future__ import annotations

from django.conf import settings


def site_version(request):
    """Expose the configured SITE_VERSION to every template."""
    return {"SITE_VERSION": getattr(settings, "SITE_VERSION", "")}
