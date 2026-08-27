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
from chardata.char_blobs import read_char_blob
from fashionistapulp.dofus_constants import get_stat_maximum
from fashionistapulp.structure import get_structure

def get_min_stats(char):
    return read_char_blob(char.minimum_stats, {}, 'minimum_stats', char)

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
    # AP/MP/Range cap at 12/6/6 on modern and Touch. Retro (1.29) has no cap, so
    # get_stat_maximum omits those keys there and 17 AP stands.
    caps = get_stat_maximum(getattr(char, 'game_version', 'dofus3'))
    for stat_name, stat_value in minimum_values.items():
        # A min that was never set is stored as None or ''.
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

def minimums_above_their_cap(char):
    """The minimums this version can never reach, each with the value it stops at.

    set_min_stats clamps AP/MP/Range when they are saved, but get_stat_maximum
    also bounds Summon and the five percent resistances, and model.py gives the
    LP variable that bound. A minimum above it has no solution, and the failure
    page offered five tips, none of which was the reason.

    The cap is read here instead of being named, so this stays right when the
    number changes and version by version: Retro never got the PA/PM/PO
    limitation, get_stat_maximum omits those keys there, and a 17 AP minimum is
    not an offence on that version.
    """
    caps = get_stat_maximum(getattr(char, 'game_version', 'dofus3'))
    over = []
    for stat_name, value in get_min_stats_digested(char).items():
        cap = caps.get(stat_name)
        if cap is not None and isinstance(value, int) and value > cap:
            over.append({'name': stat_name, 'max': cap})
    over.sort(key=lambda entry: entry['name'])
    return over

