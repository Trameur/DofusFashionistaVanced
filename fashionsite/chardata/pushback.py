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

"""Pushback damage per Ankama's 2.17 formula, ([level]/2 + pushback damage + 32) * remaining distance / (4 * 2^intermediate targets), target resistance taken as zero; Retro keeps its random one."""

# Retro (1.29) never received the 2.17 rewrite and still rolls a die for it.
VERSIONS_WITH_THE_PUBLISHED_FORMULA = ('dofus3', 'beta', 'dofus2', 'touch')


def uses_the_published_formula(game_version):
    return game_version in VERSIONS_WITH_THE_PUBLISHED_FORMULA


def pushback_damage(caster_level, pushback_stat, cells,
                    target_resistance=0, intermediates=0,
                    game_version='dofus3'):
    if not uses_the_published_formula(game_version):
        return None
    if not cells or cells <= 0:
        return 0.0
    divisor = 4.0 * (2 ** max(0, intermediates))
    base = (caster_level / 2.0
            + (pushback_stat - target_resistance)
            + 32)
    return max(0.0, base * cells / divisor)


def diagonal_cells(cells):
    if not cells or cells <= 0:
        return 0
    return -(-cells // 2)
