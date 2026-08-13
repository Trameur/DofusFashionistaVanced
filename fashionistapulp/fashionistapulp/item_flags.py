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

"""What the game says about an item beyond its stats, worded once for the
solution page and the encyclopedia.

Only Hunting Weapon was ever shown. The other four were read from the source,
stored, translated into the four other languages, and then dropped on the floor:
468 Dofus 3 items carry one.
"""
from django.utils.translation import gettext as _

_ICONS = {'Hunting Weapon': 'chardata/hunting_weapon.png'}

# Trophy and -special spell- stay out: the first is a slot marker the solver
# uses, the second only says that a description follows, which is already shown.
# Exchangeable is out too. The source writes "Exchangeable: 0" and nothing else,
# on all 123 items that carry it, so the field says nothing; read as a boolean
# it printed "Not exchangeable" on the Crimson, Emerald, Turquoise, Cawwot and
# Vulbis Dofus, which are traded every day.
_LABELS = ('Hunting Weapon', 'Fertile', 'Linked to the character',
           'Cooperative crafting impossible')


def flag_lines(flags):
    """[(label, icon key or None)] for the flags worth reading."""
    return [(_(flag), _ICONS.get(flag))
            for flag in flags or [] if flag in _LABELS]
