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

"""Wakfu equipment stats, keyed by the client's characteristic names."""

# The four elements gear can buy, in the order Ankama uses to break ties.
ELEMENTS = ('FIRE', 'WATER', 'EARTH', 'AIR')

# Spells deal these too, but no gear sells a mastery or resistance for them
DAMAGE_ELEMENTS_NO_GEAR_SELLS = ('LIGHT', 'NEUTRAL')

# Stat categories
PRIMARY = 'primary'          # the resources a turn spends
MASTERY = 'mastery'          # what makes a hit bigger
RESISTANCE = 'resistance'    # what makes a hit smaller
SECONDARY = 'secondary'      # everything else gear sells

# Every characteristic equipment can carry
WAKFU_STATS = {
    'AP': PRIMARY,
    'MP': PRIMARY,
    'WP': PRIMARY,
    'RANGE': PRIMARY,
    'HP': PRIMARY,

    # Generic mastery, also used by the "in N elements" lines
    'DMG_IN_PERCENT': MASTERY,
    'DMG_FIRE_PERCENT': MASTERY,
    'DMG_WATER_PERCENT': MASTERY,
    'DMG_EARTH_PERCENT': MASTERY,
    'DMG_AIR_PERCENT': MASTERY,
    # Non elemental masteries
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
    # On no equipment today, only on older item revisions
    'CONTROL': SECONDARY,
}

# Allowed to be missing from the equipment data
NOT_ON_GEAR_TODAY = ('CONTROL',)

# "Mastery in N elements" lines never say which elements
SPREAD_MASTERY = 'DMG_IN_PERCENT'
SPREAD_RESISTANCE = 'RES_IN_PERCENT'

# The planner assumes those elements land where the build wants them
SPREAD_LANDS_WHERE_THE_BUILD_WANTS = True

# Best spell's base damage per AP, median over the classes
DAMAGE_PER_AP_AT_245 = 40

# Spell level of the number above, spell damage grows with level
DAMAGE_PER_AP_MEASURED_AT = 245

# Caps on base plus gear, out of combat only. Not in Ankama's data: they come
# from methodwakfu.com, credit them if they ever show on a page
OUT_OF_COMBAT_CAPS = {
    'AP': 16,
    'MP': 8,
    'WP': 20,
}

# Before any gear
BASE_VALUES = {
    'AP': 6,
    'MP': 3,
    'WP': 6,
}

# Equip condition on the build's total % critical hit, not a cap
CRITICAL_HIT_FLOOR_PERCENT = -9


def stats_of_kind(kind):
    return sorted(key for key, purpose in WAKFU_STATS.items()
                  if purpose == kind)


def is_known(key):
    return key in WAKFU_STATS
