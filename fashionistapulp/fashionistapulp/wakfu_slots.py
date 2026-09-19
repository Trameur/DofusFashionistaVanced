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

"""Wakfu slot rules, from Ankama's data."""

# Character sheet order, from equipmentItemTypes.json equipmentPositions
SLOTS = (
    'HEAD',
    'NECK',
    'CHEST',
    'SHOULDERS',
    'BACK',
    'BELT',
    'LEGS',
    'LEFT_HAND',
    'RIGHT_HAND',
    'FIRST_WEAPON',
    'SECOND_WEAPON',
    'ACCESSORY',
)

# Carried through as data, not gear a build optimizes.
NOT_GEAR = ('PET', 'MOUNT', 'COSTUME')

# Rings fit either hand; the data doesn't say if the same ring can be worn twice
BOTH_HANDS = ('LEFT_HAND', 'RIGHT_HAND')

# Two-handed types list it in equipmentDisabledPositions
BLOCKED_BY_TWO_HANDED = 'SECOND_WEAPON'

# One equipped at a time per property, not per rarity (Suni Belt, Nox Greatcoat)
EXCLUSIVE_PROPERTIES = {
    8: 'relic',
    12: 'epic',
}

# Ordered tiers, as the data numbers them
RARITIES = {
    0: 'common',
    1: 'unusual',
    2: 'rare',
    3: 'mythical',
    4: 'legendary',
    5: 'relic',
    6: 'souvenir',
    7: 'epic',
}


def blocks_the_off_hand(disabled_positions):
    return BLOCKED_BY_TWO_HANDED in (disabled_positions or ())


def exclusivity_of(properties):
    """'relic', 'epic' or None for one item's property list."""
    for number, group in EXCLUSIVE_PROPERTIES.items():
        if number in (properties or ()):
            return group
    return None
