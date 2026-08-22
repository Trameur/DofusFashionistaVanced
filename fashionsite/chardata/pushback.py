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

"""What a push is worth when the target stops against something.

Ankama published the formula in the 2.17 changelog, 10 December 2013:

    ([caster level]/2 + [pushback damage - the target's pushback resistance]
     + 32) * [remaining push distance] / (4 * 2^[intermediate targets])

and stated in the same section that the damage stopped being random. The "/4"
and "/8" that circulate are not two versions of the rule: the divisor is
4 * 2^n, so /4 is the target hitting a wall and /8 is the fighter that was used
as the wall taking the collateral.

Three things this deliberately does not pretend to know:

- **The board.** "Remaining push distance" is the cells the target did NOT
  travel, so a push into open ground is worth nothing and a push into a wall
  right behind the target is worth the whole distance. The simulator has no
  map, so it reports the maximum and says so, rather than inventing an average.
- **The target.** Its pushback resistance is subtracted, and we do not know it.
  Zero is assumed, which is what the rest of the turn panel already does: every
  damage figure there is computed before the target's resistances.
- **The rounding.** Ankama publishes no floor or ceiling operator, so nothing
  here rounds; the caller rounds once, for display.

Not every version follows it. Dofus Touch only aligned on the modern formula in
its August 2021 balancing, and Dofus Retro is still on the pre-2.17 random one,
so Retro gets nothing from this module rather than a number from another game.
"""

# Retro (1.29) never received the 2.17 rewrite and still rolls a die for it.
VERSIONS_WITH_THE_PUBLISHED_FORMULA = ('dofus3', 'beta', 'dofus2', 'touch')


def uses_the_published_formula(game_version):
    return game_version in VERSIONS_WITH_THE_PUBLISHED_FORMULA


def pushback_damage(caster_level, pushback_stat, cells,
                    target_resistance=0, intermediates=0,
                    game_version='dofus3'):
    """The damage a push of `cells` deals when all of it is stopped at once.

    Returns None for a version this formula does not describe, and 0.0 when
    nothing would be dealt.
    """
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
    """A push along a diagonal covers half the distance, rounded up.

    Ankama added this after the 2.17 text, so the changelog formula alone is
    incomplete for a diagonal push.
    """
    if not cells or cells <= 0:
        return 0
    return -(-cells // 2)
