# Copyright (C) 2020 The Dofus Fashionista
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

"""Smithmagic (forgemagie) rune data per game version.

Four rulesets cover the five game versions served by the site:

- 'modern': Dofus 3 and its beta.
- 'dofus2': the modern weights, but the smaller rune roster of the 2.x client.
- 'touch': Dofus Touch, forked from Dofus 2.14. Wisdom weighs 1 per point
  against the PC's 3. Forking before 2.29 does NOT mean it kept the pre-2.29
  weights: the Cri, So and Vi runes were read in the game's own smithmagic
  interface on 2026-09-03 and give 10, 10 and 0.2, the modern figures. The
  version note used to tell Touch readers the opposite, which were the Retro
  column's numbers.
- 'retro': Dofus 1.29. Smaller stat roster, older densities.

Rune names are the ones each version's own item table publishes, checked
against it: 105 runes on Dofus 3 and the beta, 98 on Dofus 2, 86 on Touch,
57 on Retro.

Each stat entry:
- density: sink weight of one point of the stat.
- rune: in-game short rune name ('' when the stat has no rune and can only
  appear or be lost through item rolls).
- tiers: (tier_prefix, bonus) pairs, e.g. ('Pa', 3) is the 'Rune Pa Xxx'
  giving +3. The rune's weight is bonus * density.
- approx: True when the density is a best guess taken from the modern
  values (only affects stats without runes).

  ON RETRO THE SIX APPROXIMATED DENSITIES APPLY TO NOTHING, measured
  2026-08-25: neutdam, earthdam, firedam, waterdam, airdam and dodge are
  carried by zero items and zero set bonuses in items_retro.db. Five of them
  looked carried until that day, by twelve weapons whose OWN HIT the transform
  had stored as a flat bonus; those hits went back where they belong. So no
  Retro result rests on a modern figure, and there is no Retro source to go
  looking for. That is only true while the count stays at zero: a 1.29 update
  putting one of these on gear would make the guess matter again, and
  ARetroWeaponWithFixedDamageStillHitsTests fails when it does.
"""

# Per-stat weight of over/exo bonuses cannot exceed this in every version.
OVER_WEIGHT_CAP = 101

# Extra weight on one line past which a point only lands on a critical, ~1%
# a throw: AP 100, MP 90, range 51, summon 30, % spell damage from 2 x 15.
# Measured on the modern game; Retro keeps the same number for want of a Retro
# measurement, which there makes an over-crit or an over-reflect (both weigh
# 30) a 1% throw as well.
_ONE_PERCENT_OVER_WEIGHT = {
    'modern': 30,
    'dofus2': 30,
    'touch': 30,
    'retro': 30,
}

MAGEABLE_TYPES = ['Weapon', 'Shield', 'Hat', 'Cloak', 'Amulet', 'Ring',
                  'Belt', 'Boots']


def _stat(density, rune, tiers, approx=False):
    return {
        'density': density,
        'rune': rune,
        'tiers': tiers,
        'approx': approx,
    }


_STANDARD_TIERS = [('', 1), ('Pa', 3), ('Ra', 10)]

_MODERN_STATS = {
    'vit': _stat(0.2, 'Vi', [('', 5), ('Pa', 15), ('Ra', 50)]),
    'str': _stat(1, 'Fo', _STANDARD_TIERS),
    'int': _stat(1, 'Ine', _STANDARD_TIERS),
    'cha': _stat(1, 'Cha', _STANDARD_TIERS),
    'agi': _stat(1, 'Age', _STANDARD_TIERS),
    'wis': _stat(3, 'Sa', _STANDARD_TIERS),
    'pow': _stat(2, 'Pui', _STANDARD_TIERS),
    'init': _stat(0.1, 'Ini', [('', 10), ('Pa', 30), ('Ra', 100)]),
    'pod': _stat(0.25, 'Pod', [('', 10), ('Pa', 30), ('Ra', 100)]),
    'pp': _stat(3, 'Prospe', [('', 1), ('Pa', 3)]),
    'ap': _stat(100, 'Ga Pa', [('', 1)]),
    'mp': _stat(90, 'Ga Pme', [('', 1)]),
    'range': _stat(51, 'Po', [('', 1)]),
    'summon': _stat(30, 'Invo', [('', 1)]),
    'dam': _stat(20, 'Do', [('', 1)]),
    'heals': _stat(10, 'So', [('', 1), ('Pa', 3)]),
    'ch': _stat(10, 'Cri', [('', 1)]),
    'ref': _stat(10, 'Do Ren', [('', 1), ('Pa', 3)]),
    'apred': _stat(7, 'Ret Pa', [('', 1), ('Pa', 3)]),
    'mpred': _stat(7, 'Ret Pme', [('', 1), ('Pa', 3)]),
    'apres': _stat(7, 'Ré Pa', [('', 1), ('Pa', 3)]),
    'mpres': _stat(7, 'Ré Pme', [('', 1), ('Pa', 3)]),
    'neutresper': _stat(6, 'Ré Per Neutre', [('', 1)]),
    'earthresper': _stat(6, 'Ré Per Terre', [('', 1)]),
    'fireresper': _stat(6, 'Ré Per Feu', [('', 1)]),
    'waterresper': _stat(6, 'Ré Per Eau', [('', 1)]),
    'airresper': _stat(6, 'Ré Per Air', [('', 1)]),
    'neutdam': _stat(5, 'Do Neutre', [('', 1), ('Pa', 3)]),
    'earthdam': _stat(5, 'Do Terre', [('', 1), ('Pa', 3)]),
    'firedam': _stat(5, 'Do Feu', [('', 1), ('Pa', 3)]),
    'waterdam': _stat(5, 'Do Eau', [('', 1), ('Pa', 3)]),
    'airdam': _stat(5, 'Do Air', [('', 1), ('Pa', 3)]),
    'cridam': _stat(5, 'Do Cri', [('', 1), ('Pa', 3)]),
    'pshdam': _stat(5, 'Do Pou', _STANDARD_TIERS),
    'trapdam': _stat(5, 'Do Pi', [('', 1), ('Pa', 3)]),
    'trapdamper': _stat(2, 'Per Pi', _STANDARD_TIERS),
    'neutres': _stat(2, 'Ré Neutre', _STANDARD_TIERS),
    'earthres': _stat(2, 'Ré Terre', _STANDARD_TIERS),
    'fireres': _stat(2, 'Ré Feu', _STANDARD_TIERS),
    'waterres': _stat(2, 'Ré Eau', _STANDARD_TIERS),
    'airres': _stat(2, 'Ré Air', _STANDARD_TIERS),
    'crires': _stat(2, 'Ré Cri', _STANDARD_TIERS),
    'pshres': _stat(2, 'Ré Pou', _STANDARD_TIERS),
    'lock': _stat(4, 'Tac', [('', 1), ('Pa', 3)]),
    'dodge': _stat(4, 'Fui', [('', 1), ('Pa', 3)]),
    'permedam': _stat(15, 'Do Per Mé', [('', 1)]),
    'perrandam': _stat(15, 'Do Per Di', [('', 1)]),
    'perweadam': _stat(15, 'Do Per Ar', [('', 1)]),
    'perspedam': _stat(15, 'Do Per So', [('', 1)]),
    'respermee': _stat(10, 'Ré Per Mé', [('', 1)]),
    'resperran': _stat(10, 'Ré Per Di', [('', 1)]),
    # No "Ré Per Ar" rune exists in game: % weapon resist cannot be maged.
    'resperwea': _stat(15, '', [], approx=True),
}

# Touch has no per-attack-type percentage stats, no trap damage, trap power or
# reflect, and no Ra tier for the resists, So or the elemental damages.
_TOUCH_STATS = dict(_MODERN_STATS)
for _key in ('permedam', 'perrandam', 'perweadam', 'perspedam',
             'respermee', 'resperran', 'resperwea',
             'ref', 'trapdam', 'trapdamper'):
    del _TOUCH_STATS[_key]
_TOUCH_STATS.update({
    # These first three are the modern values, restated on purpose: Touch
    # forked at 2.14 and the obvious guess is that it kept the pre-2.29 crit
    # 30, heal 20 and Vi +3/+10/+30. It did not. Read in game 2026-09-03.
    'vit': _stat(0.2, 'Vi', [('', 5), ('Pa', 15), ('Ra', 50)]),
    'wis': _stat(1, 'Sa', _STANDARD_TIERS),
    'ch': _stat(10, 'Cri', [('', 1)]),
    'heals': _stat(10, 'So', [('', 1), ('Pa', 3)]),
    'neutres': _stat(2, 'Ré Neutre', [('', 1), ('Pa', 3)]),
    'earthres': _stat(2, 'Ré Terre', [('', 1), ('Pa', 3)]),
    'fireres': _stat(2, 'Ré Feu', [('', 1), ('Pa', 3)]),
    'waterres': _stat(2, 'Ré Eau', [('', 1), ('Pa', 3)]),
    'airres': _stat(2, 'Ré Air', [('', 1), ('Pa', 3)]),
    'crires': _stat(2, 'Ré Cri', [('', 1), ('Pa', 3)]),
    'pshres': _stat(2, 'Ré Pou', [('', 1), ('Pa', 3)]),
    'pshdam': _stat(5, 'Do Pou', [('', 1), ('Pa', 3)]),
    'neutdam': _stat(5, 'Do Neutre', [('', 1), ('Pa', 3)]),
    'earthdam': _stat(5, 'Do Terre', [('', 1), ('Pa', 3)]),
    'firedam': _stat(5, 'Do Feu', [('', 1), ('Pa', 3)]),
    'waterdam': _stat(5, 'Do Eau', [('', 1), ('Pa', 3)]),
    'airdam': _stat(5, 'Do Air', [('', 1), ('Pa', 3)]),
    'cridam': _stat(5, 'Do Cri', [('', 1), ('Pa', 3)]),
})

# Dofus 2 shares the modern weights but not the modern rune roster: its own
# item table has no Ra rune for the elemental resists or for critical resist,
# and no Pa rune for reflect. Pushback resist does have its Ra rune there.
_DOFUS2_STATS = dict(_MODERN_STATS)
_DOFUS2_STATS.update({
    'ref': _stat(10, 'Do Ren', [('', 1)]),
    'neutres': _stat(2, 'Ré Neutre', [('', 1), ('Pa', 3)]),
    'earthres': _stat(2, 'Ré Terre', [('', 1), ('Pa', 3)]),
    'fireres': _stat(2, 'Ré Feu', [('', 1), ('Pa', 3)]),
    'waterres': _stat(2, 'Ré Eau', [('', 1), ('Pa', 3)]),
    'airres': _stat(2, 'Ré Air', [('', 1), ('Pa', 3)]),
    'crires': _stat(2, 'Ré Cri', [('', 1), ('Pa', 3)]),
})

# 1.29 has no Power, Lock, AP/MP reduction or dodge runes. 'pow' holds the
# pre-2.0 % damage line, whose rune the game calls Do Per.
_RETRO_STATS = {
    'vit': _stat(0.25, 'Vi', [('', 3), ('Pa', 10), ('Ra', 30)]),
    'str': _stat(1, 'Fo', _STANDARD_TIERS),
    'int': _stat(1, 'Ine', _STANDARD_TIERS),
    'cha': _stat(1, 'Cha', _STANDARD_TIERS),
    'agi': _stat(1, 'Age', _STANDARD_TIERS),
    'wis': _stat(3, 'Sa', _STANDARD_TIERS),
    'init': _stat(0.1, 'Ini', [('', 10), ('Pa', 30), ('Ra', 100)]),
    'pod': _stat(0.25, 'Pod', [('', 10), ('Pa', 30), ('Ra', 100)]),
    'pp': _stat(3, 'Prospe', [('', 1), ('Pa', 3)]),
    'ap': _stat(100, 'Ga Pa', [('', 1)]),
    'mp': _stat(90, 'Ga Pme', [('', 1)]),
    'range': _stat(51, 'Po', [('', 1)]),
    'summon': _stat(30, 'Invo', [('', 1)]),
    'dam': _stat(20, 'Do', [('', 1)]),
    'pow': _stat(2, 'Do Per', _STANDARD_TIERS),
    'heals': _stat(20, 'So', [('', 1)]),
    'ch': _stat(30, 'Cri', [('', 1)]),
    'ref': _stat(30, 'Do Ren', [('', 1)]),
    # Rune Pa Pi exists in 1.29 at power 3, the same shape every other Pa rune
    # has; only this line was missing it.
    'trapdam': _stat(15, 'Pi', [('', 1), ('Pa', 3)]),
    'trapdamper': _stat(2, 'Pi Per', _STANDARD_TIERS),
    'neutresper': _stat(4, 'Ré Per Neutre', [('', 1)]),
    'earthresper': _stat(4, 'Ré Per Terre', [('', 1)]),
    'fireresper': _stat(4, 'Ré Per Feu', [('', 1)]),
    'waterresper': _stat(4, 'Ré Per Eau', [('', 1)]),
    'airresper': _stat(4, 'Ré Per Air', [('', 1)]),
    'neutres': _stat(5, 'Ré Neutre', [('', 1)]),
    'earthres': _stat(5, 'Ré Terre', [('', 1)]),
    'fireres': _stat(5, 'Ré Feu', [('', 1)]),
    'waterres': _stat(5, 'Ré Eau', [('', 1)]),
    'airres': _stat(5, 'Ré Air', [('', 1)]),
    'neutdam': _stat(5, '', [], approx=True),
    'earthdam': _stat(5, '', [], approx=True),
    'firedam': _stat(5, '', [], approx=True),
    'waterdam': _stat(5, '', [], approx=True),
    'airdam': _stat(5, '', [], approx=True),
    'dodge': _stat(4, '', [], approx=True),
}

# Runes that change an item without giving it a characteristic. They are not in
# the item tables the site ships, so their presence was read from each version's
# own item file: ankama ids 10057 and 7508 exist in the Dofus 3, beta, Dofus 2,
# Touch and Retro data alike. The hunting rune costs 5 of weight on Dofus 3 and
# 2 on Touch; nothing states it for Retro, so that one stays unstated and its
# rune cannot be thrown in the simulator.
_HUNTING = {'key': 'hunting', 'weight': 5, 'mageable': True}
# Touch weighs 2. No first-party source states it: the item table carries only
# the carry weight, and dofustouch.com is a parked domain now. It comes from a
# Touch player who checked the rest of this table against their own game, so it
# is the one figure here resting on a report rather than on a file.
_HUNTING_TOUCH = {'key': 'hunting', 'weight': 2, 'mageable': True}
_HUNTING_UNKNOWN = {'key': 'hunting', 'weight': None, 'mageable': True}
# The signature rune goes in with the ingredients at craft time and never
# touches smithmagic, so it weighs nothing anywhere.
_SIGNATURE = {'key': 'signature', 'weight': 0, 'mageable': False}

_NO_STAT_RUNES = {
    'modern': [_HUNTING, _SIGNATURE],
    'dofus2': [_HUNTING, _SIGNATURE],
    'touch': [_HUNTING_TOUCH, _SIGNATURE],
    'retro': [_HUNTING_UNKNOWN, _SIGNATURE],
}

_RULESET_BY_VERSION = {
    'dofus3': 'modern',
    'beta': 'modern',
    'dofus2': 'dofus2',
    'touch': 'touch',
    'retro': 'retro',
}

_STATS_BY_RULESET = {
    'modern': _MODERN_STATS,
    'dofus2': _DOFUS2_STATS,
    'touch': _TOUCH_STATS,
    'retro': _RETRO_STATS,
}


def get_ruleset(game_version):
    return _RULESET_BY_VERSION.get(game_version, 'modern')


def get_one_percent_over_weight(game_version):
    """Extra weight on a line past which only a critical success grants it."""
    return _ONE_PERCENT_OVER_WEIGHT[get_ruleset(game_version)]


def get_fm_stats(game_version):
    """Stat key -> {density, rune, tiers, approx} for this game version."""
    return _STATS_BY_RULESET[get_ruleset(game_version)]


def get_fm_stat(game_version, stat_key):
    return get_fm_stats(game_version).get(stat_key)


def get_no_stat_runes(game_version):
    """[{key, weight}] for the runes of this version that raise no stat."""
    return _NO_STAT_RUNES[get_ruleset(game_version)]
