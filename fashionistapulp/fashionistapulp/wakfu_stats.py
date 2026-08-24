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

# The four elements gear can buy, in the order Ankama uses to break ties.
# Confirmed by an Ankama developer on their forum, 2017-08-29, for chromatic
# damage.
ELEMENTS = ('FIRE', 'WATER', 'EARTH', 'AIR')

# A FIFTH DAMAGE ELEMENT EXISTS AND NO GEAR TOUCHES IT. Ankama's own
# actions.json declares action 1083 "Dommage : Lumiere" and 1084 "Soin :
# Lumiere", both marked [el6], beside action 1 "Dommage : Neutre" marked [el0].
# Not one item in 1.92 uses any of the four: of the 71 actions the file
# declares, items use 63, and these are among the eight left over.
#
# The spells do use it. 39 of the 715 spells collected from the encyclopedia
# deal Light damage, spread over 12 of the 18 classes, so this is a general
# mechanic and not one class's quirk. The Huppermage is simply the class where
# it shows most: eight of its spells sit in a fire, water, earth or air branch
# and deal Light, which is why a spell's branch and its damage element
# genuinely disagree there and no parser is at fault.
#
# What it means for a damage model: Light damage cannot be raised by any of the
# four elemental masteries, because none exists for it, and cannot be reduced
# by any elemental resistance either. Whatever scales it, gear is not it.
#
# Kept here rather than in ELEMENTS because a build has nothing to spend on it.
# Zero items carrying a stat proves that no gear sells it, never that the game
# lacks the mechanic.
DAMAGE_ELEMENTS_NO_GEAR_SELLS = ('LIGHT', 'NEUTRAL')

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

# WHAT A CHARACTER MAY CARRY OUT OF COMBAT. These caps bind hard and the
# optimizer is wrong without them.
#
# Measured on build 1.92.1.60, taking the best item in each of the twelve slots
# and ignoring the relic and epic limits, so these are ceilings and not builds:
#
#     AP    +18 from gear   best single item +3
#     MP    +15             best single item +2
#     WP    +16             best single item +2
#     RANGE +14             best single item +2
#
# Gear alone therefore passes every cap below by a wide margin. An optimizer
# that did not know them would spend EVERY slot buying AP the game refuses to
# grant, and the build it returned would be wrong in a way no check of the data
# could catch.
OUT_OF_COMBAT_CAPS = {
    'AP': 16,
    'MP': 8,
    'WP': 20,
}

# What a character has before a single piece of gear. The cap applies to the
# TOTAL, so these are what make it bind: gear alone would leave the WP cap
# untouched, and 6 + 16 passes it.
#
#     AP  6 + 18 from gear = 24, capped at 16
#     MP  3 + 15           = 18, capped at 8
#     WP  6 + 16           = 22, capped at 20
BASE_VALUES = {
    'AP': 6,
    'MP': 3,
    'WP': 6,
}

# The floor on critical hit, which is an EQUIP condition and not a cap: 87
# items in 1.92 carry a negative % critical hit, from -2 to -20, and they pay
# for it with more of everything else. A character may not go below this total,
# so those items have to be bought back with critical hit from elsewhere. The
# Weakened Kel'Dwa alone is -20, which is why the rule is about the total and
# not about one piece.
CRITICAL_HIT_FLOOR_PERCENT = -9

# WHERE THESE NUMBERS COME FROM, because they are not in Ankama's data and the
# history matters. The cap has been raised twice, so any source must be dated:
#
#   2013-07-17  Ankama devblog "Les nouvelles regles d'equipement": 12 AP, 7 MP,
#               and it states the limit applies OUT OF COMBAT only.
#   2016-11-06  Ankama forum, thread 401578: "c'est limite a 14 PA de toute
#               facon". So 12 was already gone.
#   2019-01-03  Ankama forum, thread 416086: 14 AP and 8 MP, with the base
#               values 6 AP and 3 MP spelled out piece by piece.
#   2026-06-01  methodwakfu.com, "Informations generales": 16 AP, 8 MP, 20 WP,
#               and the -9 % critical hit floor. It names what exceeds the caps
#               IN combat: the Osamodas' Piqure motivante (+2 AP), the Steamer's
#               Moderateur d'energie (+1 MP), the Engouement velocity bonus
#               (+2 AP), the Maniement:Bouclier sublimation (+1 MP).
#
# The last one is a fan site, which this project uses only as a last resort:
# the caps are enforced by the client and appear in no file Ankama publishes.
# It is dated, it is the reference site for Wakfu theorycraft, and its critical
# hit rule was checked here against Ankama's own catalogue rather than taken on
# trust. IF THESE NUMBERS EVER REACH A PAGE, THE SITE MUST BE CREDITED.
#
# In combat there is no cap: spells, passives, velocity bonuses and
# sublimations all push past it, which is why the dictionary above says out of
# combat in its name.


def stats_of_kind(kind):
    return sorted(key for key, purpose in WAKFU_STATS.items()
                  if purpose == kind)


def is_known(key):
    return key in WAKFU_STATS
