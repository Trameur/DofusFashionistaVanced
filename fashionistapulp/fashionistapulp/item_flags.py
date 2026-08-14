# -*- coding: utf-8 -*-

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

"""What the game says about an item beyond its stats."""
from django.utils.translation import gettext as _

_ICONS = {'Hunting Weapon': 'chardata/hunting_weapon.png'}

_LABELS = ('Hunting Weapon')


def flag_lines(flags):
    """[(label, icon key or None)] for the flags worth reading."""
    return [(_(flag), _ICONS.get(flag))
            for flag in flags or [] if flag in _LABELS]
