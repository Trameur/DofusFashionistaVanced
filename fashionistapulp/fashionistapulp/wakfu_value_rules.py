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
ANKAMA_CLIENT = ('Ankama, the Wakfu game client (spell table 66), read from '
                 'https://cytrus.cdn.ankama.com')
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
    'damage_floor': Rule(
        {'pvm': 0.05, 'pvp': 0.05}, CHOICE,
        'a damage preset keeps its turn damage within this share of the most damage of every '
        'set its search saw; the top of the turn-for-life trades measured on Dofus 3 '
        '(+2.6 to +4.7 %)'),
    'damage_floor_seconds': Rule(
        8.0, CHOICE,
        'a floored solve ends by the deadline it was given plus these seconds: the 95 s of a '
        'guarded request less the 85 s a picking solve is given, less 2 s for a probe that '
        'overruns, the judging after the search and the landing after the solve'),
    'damage_floor_weight_least': Rule(
        0.05, CHOICE,
        'the first weight of the life term on each piece set the floor probes: damage first, '
        'life breaking the ties the damage leaves'),
    'damage_floor_weight_step': Rule(
        0.0625, CHOICE,
        'the search on the weight of the life term stops narrowing a piece set at this '
        'width: 4 bisection probes from the least weight to 1'),
    'damage_floor_weight_sets': Rule(
        3, CHOICE,
        'piece sets the search on the weight of the life term probes: the time left to it '
        'holds 2 to 9 probes'),
    'damage_floor_probe_seconds': Rule(
        1.2, CHOICE,
        'seconds the damage set probe is given, and the time left a first probe needs to '
        'start: a solve on pinned pieces took 0.2 to 1.1 s'),
    'range_floor_at_distance': Rule(
        0, CHOICE,
        'a distance role keeps range at 0 or more, since distance mastery '
        'counts from 3 cells (' + METHODWAKFU + ')'),
    'resources_kept_at_base': Rule(
        ('MP', 'WP'), CHOICE,
        'gear never takes MP or WP below a bare character'),
    'melee_mastery_up_to_cells': Rule(
        2, FAN, METHODWAKFU),
    'side_hit_multiplier': Rule(
        1.10, FAN, METHODWAKFU),
    'rear_hit_multiplier': Rule(
        1.25, FAN, METHODWAKFU),
    'light_uses_best_element_mastery': Rule(
        True, ASSUMPTION,
        'a Light damage row takes the highest of the four element masteries'),
    'casts_per_spell_per_turn': Rule(
        3, ASSUMPTION,
        'the encyclopedia states no per-turn cast limit for damage spells, so '
        'a turn casts one spell at most this many times'),
    'wp_spent_per_turn': Rule(
        1, ASSUMPTION,
        'a turn meant to repeat spends at most this many WP of the pool'),
    'later_event_rows_count': Rule(
        False, CHOICE,
        'a damage row that lands on a later event (the start or end of a turn, '
        'a trigger) stays out of the turn, whether the text states the timing '
        'before or after the figure'),
    'caster_does_not_move': Rule(
        True, ASSUMPTION,
        'a role that states no movement share spends every MP on spells, and a '
        'row that needs the caster not to have moved counts; False keeps the MP '
        'on spells and leaves those rows out'),
    'spells_castable_at_every_level': Rule(
        False, FACT,
        'a spell is castable from the unlock level of its row in the client spell '
        'table (client_spells.unlock_level); a spell the client table lacks has none '
        'and is castable at every level; ' + ANKAMA_CLIENT),
    'client_spell_level_offset': Rule(
        1, FACT,
        'measured on the build tables: the encyclopedia value at displayed level L '
        'equals the client curve at L - 1, floored, at every level sampled; '
        + ANKAMA_CLIENT),
    'critical_resistance_adds_to_raw': Rule(
        True, FAN,
        'critical resistance joins the raw resistance on a critical hit, under the '
        'same cap; ' + METHODWAKFU),
    'rear_resistance_adds_to_raw': Rule(
        True, FAN,
        'rear resistance joins the raw resistance on a hit from behind, under the '
        'same cap; ' + METHODWAKFU),
    'received_critical_share': Rule(
        {'pvm': 0.03, 'pvp': 0.25}, ASSUMPTION,
        'share of the hits received that are critical: pvm is the base critical '
        'chance (monsters carry no ferocity in our data), pvp is a choice'),
    'received_rear_share': Rule(
        {'pvm': 0.10, 'pvp': 0.20}, CHOICE,
        'share of the hits received that land on the rear'),
    'received_side_share': Rule(
        0.20, CHOICE,
        'share of the hits received that land on the side'),
    'armor_cap_share_of_life': Rule(
        0.5, FAN,
        'armor is capped at half of the maximum health points; ' + METHODWAKFU),
    'armor_turns_held': Rule(
        1, CHOICE,
        'a role holds one turn of the armor its class gives itself'),
    'critical_mastery_heals': Rule(
        True, ASSUMPTION,
        'a critical heal adds the critical mastery, as a critical hit does; '
        + METHODWAKFU + ' says masteries add to heals without naming it'),
    'percent_heals_use_heal_mastery': Rule(
        True, ASSUMPTION,
        'a heal given as a share of the maximum health points takes the heal mastery like '
        'any other heal; no source says it is exempt, and none says it is not'),
    'berserk_mastery_heals': Rule(
        False, ASSUMPTION,
        'berserk mastery does not add to a heal; no source states it does'),
    'self_heal_uses_melee_mastery': Rule(
        True, FAN,
        'a heal a spell can aim only at its caster takes the melee mastery, never the '
        'rear one; ' + METHODWAKFU),
    'removal_share_at_equal_willpower': Rule(
        {'at_equal': 0.5, 'per_point': 1 / 200}, FAN,
        'equal willpower removes half of the AP, MP or range asked; each 10 points of '
        'difference moves the share by 1/20, so +100 removes all and -100 none; '
        + METHODWAKFU),
    'target_willpower': Rule(
        0, ASSUMPTION,
        'the target of a removal has no willpower: the data holds no monster stats'),
    'teleport_cells': Rule(
        2, CHOICE,
        'a teleport or a switch of places counts as moving a unit by this many cells'),
    'unknown_recipient_rows_count': Rule(
        False, CHOICE,
        'an armor row whose recipient the database cannot name stays out of the armor of '
        'the caster and of the allies and shows in the notes; True counts it on both'),
    'possibly_caster_rows_count_on_the_life_side': Rule(
        False, CHOICE,
        'an armor row that may reach the caster (its area turns with the cast direction) '
        'counts on the side of the allies only and shows in the notes; True counts it on the '
        'side of the caster too'),
    'area_targets': Rule(
        2, CHOICE,
        'an area role counts every area damage row this many times: the data holds no '
        'monster groups, so the number of units an area spell reaches is a choice'),
}
