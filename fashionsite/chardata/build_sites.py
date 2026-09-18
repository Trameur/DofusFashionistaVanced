# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Other build sites the import reads and the export writes to, one switch each."""
import os

from django.conf import settings

DOFUSBOOK = 'dofusbook'
DOFUS_STUFFER = 'dofus-stuffer'
DOFUSCREATOR = 'dofuscreator'
ALL = (DOFUSBOOK, DOFUS_STUFFER, DOFUSCREATOR)


def enabled(site):
    if site not in getattr(settings, 'BUILD_SITES_ENABLED', ()):
        return False
    # FASHIONISTA_BUILD_SITES=none, or a comma list, narrows the settings
    kept = os.environ.get('FASHIONISTA_BUILD_SITES')
    return kept is None or site in [name.strip() for name in kept.split(',')]


def any_enabled():
    return any(enabled(site) for site in ALL)
