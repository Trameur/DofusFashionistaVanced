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

"""Where Wakfu gear goes, and what stops it going there.

Every rule below is in Ankama's own data rather than in anyone's memory of the
game, which is why each one names the file it comes from. Measured against
build 1.92.1.60.
"""

# The slots a build fills, in the order a character sheet reads. From
# `equipmentItemTypes.json`, field `equipmentPositions`.
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

# A ring fits either hand: item type 103 lists both positions, so a build wears
# two. Whether the SAME ring may be worn twice is NOT in the data and is not
# guessed here; the model must settle it before it doubles a ring.
BOTH_HANDS = ('LEFT_HAND', 'RIGHT_HAND')

# Seven weapon types carry `equipmentDisabledPositions: ['SECOND_WEAPON']`,
# covering 508 weapons: axes, shovels, hammers, bows, two-handed swords,
# two-handed staffs, and the generic two-handed type.
BLOCKED_BY_TWO_HANDED = 'SECOND_WEAPON'

# From `itemProperties.json`. Both say, in Ankama's own words, "Il ne peut y
# avoir qu'un seul Item ayant cette propriété équipé à la fois": at most one
# equipped at a time, and they are two independent groups rather than one rule
# about rarity. 97 items carry the first, 111 the second, spread across every
# slot including weapons.
EXCLUSIVE_PROPERTIES = {
    8: 'relic',
    12: 'epic',
}

# Rarity as the data numbers it. The names are the community's and the game's;
# what matters to the model is that the number is an ordered tier, and that
# relic and epic exclusivity is a PROPERTY, not a rarity: an item can be rare
# without being exclusive.
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
