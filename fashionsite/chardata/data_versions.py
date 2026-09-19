# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Which item data a build was made with, and which patch that data is."""

from datetime import date

from django.conf import settings

import fashionista_version


def current_data_version(game_version):
    return settings.SITE_VERSIONS.get(game_version, '')


def patch_of(version):
    if not version:
        return None
    return '.'.join(version.split('.')[:2])


def patch_key(patch):
    return tuple(int(part) for part in patch.split('.'))


def patch_started(game_version):
    entry = fashionista_version.PATCH_STARTED.get(game_version)
    return date.fromisoformat(entry[1]) if entry else None
