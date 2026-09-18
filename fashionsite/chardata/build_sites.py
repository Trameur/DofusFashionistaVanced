# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Other build sites the import reads and the export writes to, one switch each."""
from django.conf import settings

DOFUSBOOK = 'dofusbook'
DOFUS_STUFFER = 'dofus-stuffer'
DOFUSCREATOR = 'dofuscreator'
ALL = (DOFUSBOOK, DOFUS_STUFFER, DOFUSCREATOR)


def enabled(site):
    return site in getattr(settings, 'BUILD_SITES_ENABLED', ())


def any_enabled():
    return any(enabled(site) for site in ALL)
