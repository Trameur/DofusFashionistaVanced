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

from django.conf import settings
from django.contrib.staticfiles import finders

from fashionistapulp.fashion_util import normalize_name
from fashionistapulp.structure import get_current_game_version


def _static_exists(path):
    if finders.find(path):
        return True
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        return os.path.exists(os.path.join(static_root, path))
    return False


def get_image_url(type, name, game_version=None):
    if game_version is None:
        game_version = get_current_game_version()
    type_dir = 'items' if type != 'Pet' else 'pets'
    dofus3_path = 'chardata/%s/60x60/%s-60-60.png' % (type_dir, normalize_name(name))
    if game_version in ('dofus3', 'touch'):
        return dofus3_path
    versioned_path = 'chardata/%s/%s/60x60/%s-60-60.png' % (type_dir, game_version, normalize_name(name))
    return versioned_path if _static_exists(versioned_path) else dofus3_path
