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

The numbers come from community references, cross-checked against several
sources (Ankama tutorials, JeuxOnLine, Dofus pour les Noobs, dofastuces,
Dofuzion's 1.29 table, Touch-specific rune lists), plus the corrections a
player who mages daily sent in 2026-06: the Ra tier of the five elemental
resists, of Ré Cri, Ré Pou and Do Pou, the Pa tier of Do Ren, and the density
of Ré Per Mé and Ré Per Di, which is 10 and not 15. Three rulesets cover the
five game versions served by the site:

- 'modern': Dofus 3, beta and Dofus 2. Current rune roster and densities
  (post-2.29: Vi runes give 5/15/50 at 0.2 weight per vitality, Cri weighs
  10, So weighs 10).
- 'touch': Dofus Touch, forked from Dofus 2.14, keeps the older values
  (Vi runes give 3/10/30 at 0.25 per vitality, Cri weighs 30, So weighs 20)
  and has no %-damage-per-attack-type stats.
- 'retro': Dofus 1.29. Smaller stat roster, old densities (fixed resists
  weigh 5, % resists 4, reflects 30, trap damage 15).

Each stat entry:
- density: sink weight of one point of the stat.
- rune: in-game short rune name ('' when the stat has no rune and can only
  appear or be lost through item rolls).
- tiers: (tier_prefix, bonus) pairs, e.g. ('Pa', 3) is the 'Rune Pa Xxx'
  giving +3. The rune's weight is bonus * density.
- approx: True when no era-specific source confirmed the density and the
  modern value is used as a best guess (only affects stats without runes).
"""

# Per-stat weight of over/exo bonuses cannot exceed this in every version.
OVER_WEIGHT_CAP = 101

# Exo runes for these stats only land on critical success, ~1% per attempt.
ONE_PERCENT_EXO_STATS = ('ap', 'mp', 'range')

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
    'ap': _stat(100, 'Ga PA', [('', 1)]),
    'mp': _stat(90, 'Ga PME', [('', 1)]),
    'range': _stat(51, 'Ga PO', [('', 1)]),
    'summon': _stat(30, 'Invo', [('', 1)]),
    'dam': _stat(20, 'Do', [('', 1)]),
    'heals': _stat(10, 'So', [('', 1), ('Pa', 3)]),
    'ch': _stat(10, 'Cri', [('', 1)]),
    'ref': _stat(10, 'Do Ren', [('', 1), ('Pa', 3)]),
    'apred': _stat(7, 'Ret PA', [('', 1), ('Pa', 3)]),
    'mpred': _stat(7, 'Ret PME', [('', 1), ('Pa', 3)]),
    'apres': _stat(7, 'Ré PA', [('', 1), ('Pa', 3)]),
    'mpres': _stat(7, 'Ré PME', [('', 1), ('Pa', 3)]),
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
    'trapdamper': _stat(2, 'Pi Per', _STANDARD_TIERS),
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
    # The stat itself is kept (used by builds and item display) but rune-less.
    'resperwea': _stat(15, '', [], approx=True),
}

# Touch froze the pre-2.29 values and never received the per-attack-type
# percentage stats.
_TOUCH_STATS = dict(_MODERN_STATS)
for _key in ('permedam', 'perrandam', 'perweadam', 'perspedam',
             'respermee', 'resperran', 'resperwea'):
    del _TOUCH_STATS[_key]
_TOUCH_STATS.update({
    'vit': _stat(0.25, 'Vi', [('', 3), ('Pa', 10), ('Ra', 30)]),
    'ch': _stat(30, 'Cri', [('', 1)]),
    'heals': _stat(20, 'So', [('', 1)]),
    # The Ra resist runes and the Pa Do Ren are confirmed for the modern game
    # only, so Touch keeps the roster it forked with.
    'neutres': _stat(2, 'Ré Neutre', [('', 1), ('Pa', 3)]),
    'earthres': _stat(2, 'Ré Terre', [('', 1), ('Pa', 3)]),
    'fireres': _stat(2, 'Ré Feu', [('', 1), ('Pa', 3)]),
    'waterres': _stat(2, 'Ré Eau', [('', 1), ('Pa', 3)]),
    'airres': _stat(2, 'Ré Air', [('', 1), ('Pa', 3)]),
    'crires': _stat(2, 'Ré Cri', [('', 1), ('Pa', 3)]),
    'pshres': _stat(2, 'Ré Pou', [('', 1), ('Pa', 3)]),
    'pshdam': _stat(5, 'Do Pou', [('', 1), ('Pa', 3)]),
    'ref': _stat(10, 'Do Ren', [('', 1)]),
})

# 1.29: no Power/Lock/AP-MP reduction or dodge runes existed; resists and a
# few weights differ. '% Do' (the pre-2.0 % damage line) is kept under 'pow'
# for the reference table even though almost no 1.29 item rolls it.
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
    'ap': _stat(100, 'PA', [('', 1)]),
    'mp': _stat(90, 'PM', [('', 1)]),
    'range': _stat(51, 'PO', [('', 1)]),
    'summon': _stat(30, 'Invo', [('', 1)]),
    'dam': _stat(20, 'Do', [('', 1)]),
    'pow': _stat(2, '% Do', _STANDARD_TIERS),
    'heals': _stat(20, 'So', [('', 1)]),
    'ch': _stat(30, 'Cri', [('', 1)]),
    'ref': _stat(30, 'Do Ren', [('', 1)]),
    'trapdam': _stat(15, 'Do Pi', [('', 1)]),
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

_RULESET_BY_VERSION = {
    'dofus3': 'modern',
    'beta': 'modern',
    'dofus2': 'modern',
    'touch': 'touch',
    'retro': 'retro',
}

_STATS_BY_RULESET = {
    'modern': _MODERN_STATS,
    'touch': _TOUCH_STATS,
    'retro': _RETRO_STATS,
}


def get_ruleset(game_version):
    return _RULESET_BY_VERSION.get(game_version, 'modern')


def get_fm_stats(game_version):
    """Stat key -> {density, rune, tiers, approx} for this game version."""
    return _STATS_BY_RULESET[get_ruleset(game_version)]


def get_fm_stat(game_version, stat_key):
    return get_fm_stats(game_version).get(stat_key)
