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

"""What a Wakfu character's gear can carry, and what it is worth.

Wakfu is not a Dofus version. It has no Strength or Intelligence, no Power, no
elemental damage percentage; it has masteries, and a mastery is both the damage
statistic and the thing gear competes over. The keys below are the client's own
characteristic names, taken from the `[#charac X]` marker each action carries,
so they can be checked against the game rather than argued about.

THE ONE RULE THAT SHAPES EVERYTHING: a line reads "232 Mastery with 2 elements"
and the catalogue never says which two. Verified in build 1.92.1.60: all 5719
such lines carry a count of 1, 2 or 3 and nothing else, because the elements
belong to the copy a player holds, not to the item. The client has a second
form of the same line for an identified copy, where the element is filled in.

So the planner has to decide what those lines are worth, and it assumes THE
ELEMENTS LAND WHERE THE BUILD WANTS THEM. That is what a build planner is for:
a player chasing a build seeks the roll they want, and every Wakfu planner
works this way. It also keeps the line linear, which keeps the solver a solver.
The alternative, averaging over a random roll, would answer a question nobody
asks. The assumption is named here so it can be changed in one place, and it
must be said plainly wherever a build is shown.

Old sources disagree about how a roll is obtained, and one of them is provably
stale: every transmutation stone, the item that used to re-roll elements, now
reads "This is an old item that can no longer be used" in Ankama's own
encyclopedia, up to and including the level 170 one. How a roll is chosen in
1.92 is not settled here, and nothing in this file depends on it.
"""

# The four elements, in the order Ankama uses to break ties. Confirmed by an
# Ankama developer on their forum, 2017-08-29, for chromatic damage.
ELEMENTS = ('FIRE', 'WATER', 'EARTH', 'AIR')

# What a stat is for, which is what decides how the model may treat it.
PRIMARY = 'primary'          # the resources a turn spends
MASTERY = 'mastery'          # what makes a hit bigger
RESISTANCE = 'resistance'    # what makes a hit smaller
SECONDARY = 'secondary'      # everything else gear sells

# Every characteristic the 1.92 catalogue puts on equipment, by the client's
# own name. A Wakfu update that invents one fails the guard rather than
# dropping the line in silence.
WAKFU_STATS = {
    'AP': PRIMARY,
    'MP': PRIMARY,
    'WP': PRIMARY,
    'RANGE': PRIMARY,
    'HP': PRIMARY,

    # The generic mastery, and the one that carries the "in N elements" spread.
    'DMG_IN_PERCENT': MASTERY,
    'DMG_FIRE_PERCENT': MASTERY,
    'DMG_WATER_PERCENT': MASTERY,
    'DMG_EARTH_PERCENT': MASTERY,
    'DMG_AIR_PERCENT': MASTERY,
    # Masteries that apply to a way of fighting rather than an element.
    'MELEE_DMG': MASTERY,
    'RANGED_DMG': MASTERY,
    'BERSERK_DMG': MASTERY,
    'CRITICAL_BONUS': MASTERY,
    'BACKSTAB_BONUS': MASTERY,
    'HEAL_IN_PERCENT': MASTERY,

    'RES_IN_PERCENT': RESISTANCE,
    'RES_FIRE_PERCENT': RESISTANCE,
    'RES_WATER_PERCENT': RESISTANCE,
    'RES_EARTH_PERCENT': RESISTANCE,
    'RES_AIR_PERCENT': RESISTANCE,
    'RES_BACKSTAB': RESISTANCE,
    'CRITICAL_RES': RESISTANCE,
    'ARMOR_GIVEN_PERCENT': RESISTANCE,
    'ARMOR_RECEIVED_PERCENT': RESISTANCE,

    'FEROCITY': SECONDARY,       # critical hit chance
    'BLOCK': SECONDARY,
    'DODGE': SECONDARY,
    'TACKLE': SECONDARY,         # lock
    'INIT': SECONDARY,
    'WILLPOWER': SECONDARY,      # force of will
    'WISDOM': SECONDARY,
    'PROSPECTION': SECONDARY,
    # Real in the game and on nothing gear sells in 1.92: zero equipment lines
    # grant it. Kept because a stat missing from the catalogue is a stat the
    # importer would drop the day a patch puts it on an item, and because
    # absence from the data has never proved absence from the game. The
    # encyclopedia's Gobball set page even claims a Control bonus that none of
    # its eight items carry.
    'CONTROL': SECONDARY,
}

# Catalogue entries no equipment carries today. The guard allows these to be
# absent from the data and nothing else.
NOT_ON_GEAR_TODAY = ('CONTROL',)

# The line whose elements the data never names. It is a mastery like any other
# once the planner has decided where the elements land.
SPREAD_MASTERY = 'DMG_IN_PERCENT'
SPREAD_RESISTANCE = 'RES_IN_PERCENT'

# Stated so that a page can say it out loud rather than quietly assuming it.
SPREAD_LANDS_WHERE_THE_BUILD_WANTS = True

# THE CAP ON AP AND MP IS NOT SETTLED, AND IT BINDS HARD. Nothing here holds a
# number, on purpose: guessing one would be worse than having none.
#
# Measured on build 1.92.1.60, taking the best item in each of the twelve slots
# and ignoring the relic and epic limits, so these are ceilings and not builds:
#
#     AP    +18   best single item +3
#     MP    +15   best single item +2
#     WP    +16   best single item +2
#     RANGE +14   best single item +2
#
# A character starts with a handful of AP, so gear alone reaches roughly three
# times whatever the cap turns out to be. An optimizer that does not know the
# cap will therefore spend EVERY slot buying AP that the game refuses to grant,
# and the build it returns will be wrong in a way no test of the data can see.
#
# What is known and what is not:
#
# - The devblog that introduced the rule, 2013-07-17, says 12 AP and 7 MP, and
#   says the limit applies OUTSIDE combat only, gains during a fight being
#   unlimited. That article is thirteen years old and other things it promises
#   have since been reversed, so it cannot be trusted on its own.
# - Ankama's own forum carries a thread titled "Limite PA PM 14Pa 8PM", which
#   is exactly the shape of a later change. The forum answers a scripted
#   request with 202 and an empty body, so it cannot be read from here to find
#   out whether that title is a question or an answer.
#
# Settling it takes five seconds in front of the game and no amount of reading.
# Until somebody does, the solver must treat the cap as an input it is given,
# never a constant it knows.
AP_AND_MP_CAP_IS_UNKNOWN = True


def stats_of_kind(kind):
    return sorted(key for key, purpose in WAKFU_STATS.items()
                  if purpose == kind)


def is_known(key):
    return key in WAKFU_STATS
