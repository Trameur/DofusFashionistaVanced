"""Custom template context processors for the fashionsite project."""
from __future__ import annotations

from django.conf import settings


def site_version(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    if game_version == 'beta':
        version = getattr(settings, 'SITE_VERSION_BETA', getattr(settings, 'SITE_VERSION', ''))
    else:
        version = getattr(settings, 'SITE_VERSION', '')
    return {"SITE_VERSION": version}
