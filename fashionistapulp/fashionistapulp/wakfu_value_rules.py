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

"""Constants of Wakfu's damage and defence formulas, each with its source."""

from collections import namedtuple

Rule = namedtuple('Rule', 'value status source')

FACT = 'fact'
FAN = 'fan'
ASSUMPTION = 'assumption'
CHOICE = 'choice'

STATUSES = (FACT, FAN, ASSUMPTION, CHOICE)

ANKAMA_1_59 = ('Ankama, patch notes 1.59, https://www.wakfu.com/fr/mmorpg/'
               'actualites/maj/863091-confrerie/details')
ANKAMA_1_68 = ('Ankama, patch notes 1.68, https://www.wakfu.com/fr/mmorpg/'
               'actualites/maj/1204906-osamosa/details')
ANKAMA_1_91 = ('Ankama, patch notes 1.91, https://www.wakfu.com/fr/mmorpg/'
               'actualites/maj/1767729-mise-jour-1-91/details')
ANKAMA_SPELLS = ('Ankama, encyclopedia spell pages, critical damage column, '
                 'https://www.wakfu.com/fr/mmorpg/encyclopedie/classes')
METHODWAKFU = ('MethodWakfu, General information, 3.2 Damage calculation, '
               'https://methodwakfu.com/en/getting-started/general-information/')
WAKFORGE = ('WakForge, src/models/useStats.js, '
            'https://github.com/Tmktahu/WakForge')
WAKAUTOSOLVER = ('wakautosolver, wakautosolver/solver.py, '
                 'https://github.com/mikeshardmind/wakfu-utils')

RULES = {
    'mastery_percent_per_point': Rule(
        1, FAN, METHODWAKFU),
    'critical_multiplier': Rule(
        1.25, FACT, ANKAMA_SPELLS + '; ' + ANKAMA_1_59 + '; ' + METHODWAKFU),
    'critical_hit_cap_percent': Rule(
        100, FAN, METHODWAKFU),
    'base_critical_hit_percent': Rule(
        3, FAN, WAKFORGE + '; ' + WAKAUTOSOLVER),
    'damage_inflicted_floor_percent': Rule(
        -50, FACT, ANKAMA_1_91 + '; ' + METHODWAKFU),
    'resistance_base': Rule(
        0.8, FAN, METHODWAKFU + ", after Ectawem's calculator"),
    'resistance_cap_percent': Rule(
        90, FACT, ANKAMA_1_68 + '; ' + METHODWAKFU),
    'block_multiplier': Rule(
        0.8, FAN, METHODWAKFU),
    'base_life': Rule(
        50, FAN, WAKFORGE),
    'life_per_level': Rule(
        10, FAN, WAKFORGE),
    'turn_damage_follows_ap': Rule(
        True, ASSUMPTION,
        'a turn spends every AP on spells with the same base damage per AP'),
    'elements_cast_equally': Rule(
        True, CHOICE,
        'a multi-element role casts each of its elements equally often'),
    'incoming_elements_equally': Rule(
        True, ASSUMPTION,
        'hits taken come from the four elements equally often'),
    'defense_weight': Rule(
        0.25, CHOICE,
        'value = log(turn damage) + defense x log(effective life): a damage '
        'role values 1% of effective life as a quarter of 1% of turn damage'),
    'range_floor_at_distance': Rule(
        0, CHOICE,
        'a distance role keeps range at 0 or more, since distance mastery '
        'counts from 3 cells (' + METHODWAKFU + ')'),
    'resources_kept_at_base': Rule(
        ('MP', 'WP'), CHOICE,
        'gear never takes MP or WP below a bare character'),
}
