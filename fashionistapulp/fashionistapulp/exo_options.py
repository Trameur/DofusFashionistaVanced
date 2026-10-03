# Copyright (C) 2026 The Dofus Fashionista
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

"""The AP, MP and Range exo options, and the pieces that can carry an exo."""

from .dofus_constants import SLOT_NAME_TO_TYPE, slots_for
from .game_versions import get_game_version

EXO_OPTIONS = (('ap', 'ap_exo'), ('mp', 'mp_exo'), ('range', 'range_exo'))

# Without forgeable_items: the types a smithmagic skill works on
FORGEABLE_TYPES = ('Hat', 'Cloak', 'Amulet', 'Ring', 'Belt', 'Boots')
FORGEABLE_WEAPON_TYPES = ('hammer', 'axe', 'shovel', 'staff', 'sword', 'dagger',
                          'bow', 'wand')


def exo_per_item(game_version):
    return get_game_version(game_version).exo_per_item


def exo_count(value):
    """Pieces an exo option asks for: True is 1; False, None and 'gelano' are 0."""
    if value is True:
        return 1
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def forgeable_slot_count(structure):
    """How many of the version's slots a forgeable piece can fill."""
    count = getattr(structure, '_forgeable_slot_count', None)
    if count is None:
        types = {structure.get_type_name_by_id(item.type)
                 for item in structure.get_concatenated_items_lists()
                 if item.forgeable}
        count = sum(1 for slot in slots_for(structure.game_version)
                    if SLOT_NAME_TO_TYPE[slot] in types)
        structure._forgeable_slot_count = count
    return count
