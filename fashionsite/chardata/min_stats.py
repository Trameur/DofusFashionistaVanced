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

import pickle
from fashionistapulp.dofus_constants import get_stat_maximum
from fashionistapulp.structure import get_structure

def get_min_stats(char):
    mins = {}
    if char.minimum_stats:
        mins = pickle.loads(char.minimum_stats)
        
    return mins

def convert_dict_index_name_to_key(mins):
    s = get_structure()
    new_mins = {}
    if 'HP' in mins:
        new_mins['hp'] = mins['HP']
    for min_stat, min_value in mins.items():
        stat = s.get_stat_by_name(min_stat)
        if stat is not None:
            stat_key = stat.key
            new_mins[stat_key] = min_value
        elif min_stat == 'adv_mins':
            new_mins['adv_mins'] = {}
            for adv_min_stat, adv_min_value in mins['adv_mins'].items():
                stat = s.get_adv_min_stat_by_name(adv_min_stat)
                if stat is not None:
                    stat_key = stat['key']
                    new_mins['adv_mins'][stat_key] = adv_min_value
    return new_mins


def get_min_stats_by_key(char):
    return convert_dict_index_name_to_key(get_min_stats(char))

def set_min_stats(char, minimum_values):
    if 'Range' in minimum_values:
        if minimum_values['Range'] == 0:
            del minimum_values['Range']
    # AP/MP/Range minimums are clamped to the version's hard cap (12/6/6 on modern
    # and Touch). Retro (1.29) has no such cap, so get_stat_maximum omits those
    # keys there and the minimum is left as the player asked (17 AP is legal there).
    caps = get_stat_maximum(getattr(char, 'game_version', 'dofus3'))
    for stat_name, stat_value in minimum_values.items():
        # A min that was never set comes back as None (or '') from the char's stored
        # values; skip it so the caps below never do min(cap, None). A GET on this
        # POST view (bots, crawlers) reaches here with those stored mins.
        if not isinstance(stat_value, int):
            continue
        if stat_name in ('AP', 'MP', 'Range') and stat_name in caps:
            minimum_values[stat_name] = min(caps[stat_name], stat_value)
        if stat_value and stat_name != 'adv_mins':
            assert type(stat_value) == int
    char.minimum_stats = pickle.dumps(minimum_values)
    char.save()

def get_min_stats_digested(char):
    min_stats = get_min_stats(char)
    return {k: v for k, v in min_stats.items() if v != '' and v is not None}

def get_min_stats_digested_by_key(char):
    return convert_dict_index_name_to_key(get_min_stats_digested(char))

