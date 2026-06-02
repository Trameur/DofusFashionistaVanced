"""Custom template context processors for the fashionsite project."""
from __future__ import annotations

from django.conf import settings


def site_version(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    default = getattr(settings, 'SITE_VERSION', '')
    version = getattr(settings, 'SITE_VERSIONS', {}).get(game_version, default)
    return {"SITE_VERSION": version}
