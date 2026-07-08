# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import re

from django.conf import settings
from django.contrib.staticfiles import finders

from fashionistapulp.fashion_util import normalize_name, safe_icon_name
from fashionistapulp.structure import get_current_game_version


def _static_exists(path):
    if finders.find(path):
        return True
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        return os.path.exists(os.path.join(static_root, path))
    return False


RETRO_PLACEHOLDER = 'chardata/QuestionMark-lighttheme.png'

# Variant items produced by the data pipeline ("Nomoon 2", "Animagi (GM)",
# "Boune (+80 Agility)") reuse the base item's artwork; only the base icon
# exists on disk. The fallback only applies when the exact icon is missing.
_VARIANT_SUFFIX = re.compile(r' (?:\d+|\([^)]*\))$')


def _icon_path(type_dir, name, version_dir=None):
    fname = safe_icon_name(normalize_name(name))
    if version_dir:
        return 'chardata/%s/%s/60x60/%s-60-60.png' % (type_dir, version_dir, fname)
    return 'chardata/%s/60x60/%s-60-60.png' % (type_dir, fname)


def get_image_url(type, name, game_version=None):
    if game_version is None:
        game_version = get_current_game_version()
    type_dir = 'items' if type != 'Pet' else 'pets'
    base_name = _VARIANT_SUFFIX.sub('', name)
    dofus3_path = _icon_path(type_dir, name)
    if game_version == 'dofus3':
        # Only variant names pay the existence check; regular names keep the
        # unconditional fast path.
        if base_name != name and not _static_exists(dofus3_path):
            fallback = _icon_path(type_dir, base_name)
            if _static_exists(fallback):
                return fallback
        return dofus3_path
    versioned_path = _icon_path(type_dir, name, game_version)
    if _static_exists(versioned_path):
        return versioned_path
    if base_name != name:
        versioned_base = _icon_path(type_dir, base_name, game_version)
        if _static_exists(versioned_base):
            return versioned_base
    # Beta/Dofus 2 items look like Dofus 3, so fall back to the Dofus 3 icon. Retro
    # items are visually distinct, so the Dofus 3 icon would be the wrong item (and
    # most names don't even match) -- show a neutral placeholder until we have real
    # Retro icons in chardata/items/retro/60x60/.
    if game_version == 'retro':
        return RETRO_PLACEHOLDER
    if base_name != name and not _static_exists(dofus3_path):
        fallback = _icon_path(type_dir, base_name)
        if _static_exists(fallback):
            return fallback
    return dofus3_path
