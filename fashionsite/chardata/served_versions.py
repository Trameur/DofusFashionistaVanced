# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The versions the site answers for: the Dofus ones, and an experimental one whose flag is on."""

from django.conf import settings

from fashionistapulp.game_versions import GAME_VERSIONS, version_keys


def enabled_experimental_versions():
    """Experimental versions whose EXPERIMENTS flag, the key in capitals, is on."""
    experiments = getattr(settings, 'EXPERIMENTS', {})
    return [key for key in version_keys(include_experimental=True)
            if GAME_VERSIONS[key].experimental and experiments.get(key.upper())]


def served_versions():
    """The versions the site answers for, in page order."""
    enabled = enabled_experimental_versions()
    return [key for key in version_keys(include_experimental=True)
            if not GAME_VERSIONS[key].experimental or key in enabled]


def version_by_prefix():
    """{url prefix: version key} for the served versions that have a prefix."""
    return {GAME_VERSIONS[key].prefix: key for key in served_versions()
            if GAME_VERSIONS[key].prefix}
