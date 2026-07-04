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

from chardata.smart_build import get_standard_weights
from chardata.util import remove_cache_for_char
from fashionistapulp.dofus_constants import STAT_KEY_TO_NAME, DEPRECATED_STATS
from fashionistapulp.structure import get_structure


def get_stats_weights(char):
    weights = {}
    
    if char.stats_weight:
        weights = pickle.loads(char.stats_weight)
        
    # Fill in 0 for all stats that exist but have no weight, or a default value
    # from smart_build if it's in STATS_TO_FILL_DEFAULT.
    stats_to_calculate = []
    changed = False
    for stat in get_structure().get_stats_list():
        if stat.key not in weights:
            if stat.key in STATS_TO_FILL_DEFAULT:
                stats_to_calculate.append(stat.key)
            else:
                changed = True
                weights[stat.key] = 0

    # Call smart_build if necessary
    if stats_to_calculate:
        changed = True
        stan_w = get_standard_weights(char)
        for stat_key in stats_to_calculate:
            weights[stat_key] = stan_w[stat_key]
    
    # Filter out all non-existent stats.
    for stat_key in list(weights.keys()):
        if stat_key in DEPRECATED_STATS:
            changed = True
            del weights[stat_key]
        elif stat_key not in get_structure().get_stats_list() and stat_key != 'meleeness':
            assert stat_key in STAT_KEY_TO_NAME, '%s is not a stat' % stat_key

    # Save if anything was changed
    if changed:
        set_stats_weights(char, weights)

    return weights

STATS_TO_FILL_DEFAULT = {
    'permedam',
    'perrandam',
    'perweadam',
    'perspedam',
    'resperran',
    'respermee',
    'resperwea',
}

def _fill_defaults(char, weights):
    stats_to_calculate = []
    for e in STATS_TO_FILL_DEFAULT:
        if e not in weights:
            stats_to_calculate.append(e)
            break
    if stats_to_calculate:
        stan_w = get_standard_weights(char)
        for e in stats_to_calculate:
            weights[e] = stan_w[e]
        char.stats_weight = pickle.dumps(stan_w)

# Weights become objective coefficients for the solver. High-end crit or
# multi-element builds (dam is a sum, cridam scales with it) and manually tuned
# weights can legitimately exceed the old 5k guard, and _set_weights stores such
# weights without any check. Re-saving one (which a plain wizard GET can trigger)
# must not 500 the character's own pages, so clamp to a generous ceiling instead
# of asserting. The ceiling only guards against truly runaway values.
MAX_STAT_WEIGHT = 50000

def set_stats_weights(char, weights):
    for stat_key in list(weights.keys()):
        if stat_key in DEPRECATED_STATS or stat_key == 'meleeness':
            continue
        assert stat_key in STAT_KEY_TO_NAME, '%s is not a stat' % stat_key
        stat_weight = int(weights[stat_key])
        weights[stat_key] = max(-MAX_STAT_WEIGHT, min(MAX_STAT_WEIGHT, stat_weight))

    char.stats_weight = pickle.dumps(weights)
    char.save()
    remove_cache_for_char(char.id)

