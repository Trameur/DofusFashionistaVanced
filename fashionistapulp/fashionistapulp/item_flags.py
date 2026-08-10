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
_LABELS = ('Hunting Weapon', 'Fertile', 'Linked to the character',
           'Cooperative crafting impossible', 'Exchangeable')


def flag_lines(flags):
    """[(label, icon key or None)] for the flags worth reading."""
    lines = []
    for flag in flags or []:
        if flag not in _LABELS:
            continue
        if flag == 'Exchangeable':
            # The source only ever writes "Exchangeable: 0", on the quest Dofus,
            # the Flute and the pets, and the value is lost by the time it is a
            # flag. Printing "Exchangeable" would say the opposite of the truth.
            label = _('Not exchangeable')
        else:
            label = _(flag)
        lines.append((label, _ICONS.get(flag)))
    return lines
