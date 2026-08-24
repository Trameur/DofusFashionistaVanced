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
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.structure import get_current_game_version


def _static_exists(path):
    if finders.find(path):
        return True
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        return os.path.exists(os.path.join(static_root, path))
    return False


def list_static_dir(path):
    """File names inside a static directory, from the app statics or STATIC_ROOT."""
    directory = finders.find(path)
    if not directory or not os.path.isdir(directory):
        static_root = getattr(settings, 'STATIC_ROOT', None)
        candidate = os.path.join(static_root, path) if static_root else None
        directory = candidate if candidate and os.path.isdir(candidate) else None
    if not directory:
        return []
    return os.listdir(directory)


# Named for Retro, which was the first version with no artwork of its own; it
# now stands for any game whose picture is missing, Wakfu included. The name is
# kept because the site refers to it by that name in several places.
RETRO_PLACEHOLDER = 'chardata/QuestionMark-lighttheme.png'

# Wakfu artwork is stored under Ankama's gfx id rather than the item's name:
# half the gear shares a drawing, and a name is a different string in each of
# the five languages. 64 is the size Ankama serves closest to the 60 the site
# shows.
_PICTURE_PATH = 'chardata/items/%s/64/%d.webp'

# Variant items from the data pipeline ("Nomoon 2", "Animagi (GM)", "Boune (+80
# Agility)") reuse the base item's artwork; only the base icon exists on disk.
_VARIANT_SUFFIX = re.compile(r' (?:\d+|\([^)]*\))$')


def _icon_path(type_dir, name, version_dir=None):
    fname = safe_icon_name(normalize_name(name))
    if version_dir:
        return 'chardata/%s/%s/60x60/%s-60-60.png' % (type_dir, version_dir, fname)
    return 'chardata/%s/60x60/%s-60-60.png' % (type_dir, fname)


def get_image_url(type, name, game_version=None, picture=None):
    """The static path of an item's icon.

    `picture` is Ankama's gfx id, which only the games that store their
    artwork that way have; passing it for a Dofus version changes nothing.
    """
    if game_version is None:
        game_version = get_current_game_version()
    # A game that is not Dofus must never end up on a Dofus 3 icon. The names
    # collide across games, so the fallback at the end of this function would
    # have shown a Dofus item under a Wakfu one's name: a page that looks
    # right and belongs to another game.
    if not get_game_version(game_version).dofus:
        if picture:
            path = _PICTURE_PATH % (game_version, picture)
            if _static_exists(path):
                return path
        return RETRO_PLACEHOLDER
    type_dir = 'items' if type != 'Pet' else 'pets'
    base_name = _VARIANT_SUFFIX.sub('', name)
    dofus3_path = _icon_path(type_dir, name)
    if game_version == 'dofus3':
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
    # Beta/Dofus 2 items look like Dofus 3; Retro items are visually distinct, so a
    # Dofus 3 icon would show the wrong item.
    if game_version == 'retro':
        return RETRO_PLACEHOLDER
    if base_name != name and not _static_exists(dofus3_path):
        fallback = _icon_path(type_dir, base_name)
        if _static_exists(fallback):
            return fallback
    return dofus3_path
