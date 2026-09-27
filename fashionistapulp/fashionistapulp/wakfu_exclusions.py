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

"""Wakfu items a new build starts with forbidden; they stay in the catalogue."""

from .wakfu_slots import LEGACY_RARITY


def legacy_items(structure):
    """Ids of every item in the legacy rarity tier."""
    return sorted(item.id for item in structure.get_items_list()
                  if item.rarity == LEGACY_RARITY)


def default_exclusions(structure):
    """Item ids forbidden by default; the player can allow any of them."""
    return legacy_items(structure)
