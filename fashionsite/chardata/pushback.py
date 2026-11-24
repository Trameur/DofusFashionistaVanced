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

"""Pushback damage per Ankama's 2.17 formula, ([level]/2 + pushback damage - target pushback resistance + 32) * remaining distance / (4 * 2^intermediate targets), rounded as each client rounds it; Retro keeps its random one."""

import math

# Retro (1.29) never received the 2.17 rewrite and still rolls a die for it.
PUBLISHED_FORMULA_BY_VERSION = {'dofus3': True, 'beta': True, 'dofus2': True, 'touch': True,
                                'retro': False}
PUBLISHED_FORMULA_BY_VERSION['touchbeta'] = PUBLISHED_FORMULA_BY_VERSION['touch']
PUBLISHED_FORMULA_BY_VERSION['retrobeta'] = PUBLISHED_FORMULA_BY_VERSION['retro']
VERSIONS_WITH_THE_PUBLISHED_FORMULA = tuple(
    version for version, published in PUBLISHED_FORMULA_BY_VERSION.items() if published)

# Dofus 2 casts the result to an int after flooring [level]/2; Touch truncates the result only.
ROUNDING_BY_VERSION = {'dofus3': {'floors_half_level': False, 'truncates': False},
                       'beta': {'floors_half_level': False, 'truncates': False},
                       'dofus2': {'floors_half_level': True, 'truncates': True},
                       'touch': {'floors_half_level': False, 'truncates': True},
                       'retro': {'floors_half_level': False, 'truncates': False}}
ROUNDING_BY_VERSION['touchbeta'] = ROUNDING_BY_VERSION['touch']
ROUNDING_BY_VERSION['retrobeta'] = ROUNDING_BY_VERSION['retro']


def uses_the_published_formula(game_version):
    return game_version in VERSIONS_WITH_THE_PUBLISHED_FORMULA


def pushback_damage(caster_level, pushback_stat, cells,
                    target_resistance=0, intermediates=0,
                    game_version='dofus3'):
    if not uses_the_published_formula(game_version):
        return None
    if not cells or cells <= 0:
        return 0.0
    rounding = ROUNDING_BY_VERSION[game_version]
    divisor = 4.0 * (2 ** max(0, intermediates))
    half_level = caster_level / 2.0
    if rounding['floors_half_level']:
        half_level = float(math.floor(half_level))
    base = (half_level
            + (pushback_stat - target_resistance)
            + 32)
    dealt = max(0.0, base * cells / divisor)
    if rounding['truncates']:
        return float(int(dealt))
    return dealt


def diagonal_cells(cells):
    if not cells or cells <= 0:
        return 0
    return -(-cells // 2)
