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
# two. Whether the SAME ring may be worn twice is NOT in the data: no item and
# no item type carries a uniqueness flag, and the only "one at a time" rule
# Ankama states is the relic/epic one below. The two 2013 devblogs that set the
# equipment rules are silent on it too.
#
# So the model wears one copy, which is the safe way to be wrong: refusing a
# legal double costs a slightly worse build, allowing an illegal one hands the
# player a build the game will not let them wear. Today that holds for a
# reason worth knowing, because it is not a decision anyone wrote down:
# `model.create_item_number_variables` doubles a ring only when its type is
# NAMED 'Ring', and no Wakfu type is. A guard in the test suite holds that
# name still, so renaming a slot cannot quietly legalise doubles.
BOTH_HANDS = ('LEFT_HAND', 'RIGHT_HAND')

# Seven weapon types carry `equipmentDisabledPositions: ['SECOND_WEAPON']`,
# covering 508 weapons: axes, shovels, hammers, bows, two-handed swords,
# two-handed staffs, and the generic two-handed type.
BLOCKED_BY_TWO_HANDED = 'SECOND_WEAPON'

# From `itemProperties.json`. Both say, in Ankama's own words, "Il ne peut y
# avoir qu'un seul Item ayant cette propriété équipé à la fois": at most one
# equipped at a time, and they are two independent groups rather than one rule
# about rarity. 97 items carry the first and 115 the second, all of them gear.
#
# The names below are not the community's guess: every one of the 97 items
# carrying property 8 is rarity 5 (relic) and every one of the 115 carrying
# property 12 is rarity 7 (epic), with no mixing. Ankama's own names,
# `EXCLUSIVE_EQUIPMENT_ITEM` and `..._2`, say nothing, and their descriptions
# call both of them "[Relique]".
#
# The converse does NOT hold, which is the whole reason the model must read the
# property and never the rarity: exactly two items sit at those rarities
# without the property, the Suni Belt (32500, epic) and the Nox Greatcoat
# (32501, relic). Two items out of 212 are enough to make "epic means one at a
# time" a wrong rule, and they are named here so that a future reader who
# rediscovers the near-perfect overlap does not simplify it away.
#
# The relic rule is confirmed outside the data by the devblog that introduced
# it on 2013-07-30: a relic "can be of any type of equipment slot (epaulettes,
# boots, etc.) but you will only be able to wear one at a time". That article
# is old enough that other things it announces have since been reversed (it
# promises no new sets would ever ship, and 195 exist), so the live catalogue
# is what this file trusts; the devblog only corroborates.
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
