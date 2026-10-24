"""Custom template context processors for the fashionsite project."""
from __future__ import annotations

from django.conf import settings

from chardata.data_versions import current_data_version
from fashionistapulp.game_versions import GAME_VERSIONS


def site_version(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    known = GAME_VERSIONS.get(game_version)
    if known is not None and not known.dofus:
        return {"SITE_VERSION": current_data_version(game_version)}
    default = getattr(settings, 'SITE_VERSION', '')
    version = getattr(settings, 'SITE_VERSIONS', {}).get(game_version, default)
    return {"SITE_VERSION": version}
