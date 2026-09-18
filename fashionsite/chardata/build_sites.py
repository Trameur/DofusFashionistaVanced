# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The other build sites the import reads links from and the export sends
builds to, one switch each.

Thibaud, 2026-09-18: the TemporiX release goes to production without them,
and each site comes back once its creator has agreed. The switches live in the
settings (`BUILD_SITES_ENABLED`): production lists the agreed sites,
`BUILD_SITES_AGREED`, empty that day; a local run (DEBUG) lists all three, so
the features stay visible and tested where they are built.
"""
from django.conf import settings

DOFUSBOOK = 'dofusbook'
DOFUS_STUFFER = 'dofus-stuffer'
DOFUSCREATOR = 'dofuscreator'
ALL = (DOFUSBOOK, DOFUS_STUFFER, DOFUSCREATOR)


def enabled(site):
    return site in getattr(settings, 'BUILD_SITES_ENABLED', ())


def any_enabled():
    return any(enabled(site) for site in ALL)
