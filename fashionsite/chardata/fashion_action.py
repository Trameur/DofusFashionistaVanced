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

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect
import pickle

from chardata.lock_forbid import get_all_exclusions_en_names, get_all_inclusions_en_names,\
    get_inclusions_dict, get_all_exclusions_ids
from chardata.min_stats import get_min_stats_digested
from chardata.models import CharBaseStats
from chardata.solution import set_minimal_solution
from chardata.solution_memory import DatabaseSolutionMemory
from chardata.stats_weights import get_stats_weights
from chardata.util import get_char_or_raise, get_base_stats_by_attr, \
    remove_cache_for_char
from chardata.util_views import error
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import ModelInput
from fashionistapulp.model_pool import create_model, borrow_model, return_model


if not settings.DEBUG:
    create_model()

MEMORY = DatabaseSolutionMemory()

def get_options(request, char_id):
    char = get_char_or_raise(request, char_id)
    options = {}
    if char.options:
        options = pickle.loads(char.options)
    model_options = {'ap_exo': options.get('ap_exo', False),
                     'range_exo': options.get('range_exo', False),
                     'mp_exo': options.get('mp_exo', False),
                     'dofus': options.get('dofus', True),
                     'dragoturkey': options.get('dragoturkey', True),
                     'seemyool': options.get('seemyool', True),
                     'rhineetle': options.get('rhineetle', True),
                     'prysmaradite': options.get('prysmaradite', False)}
    return model_options

def fashion(request, char_id, spells=False):
    char = get_char_or_raise(request, char_id)
    remove_cache_for_char(char_id)
        
    if char.stats_weight:
        weights = get_stats_weights(char)
        load_error = True
        for _, value in weights.items():
            if value != 0:
                load_error = False
                break
    else: 
        load_error = True
    if load_error:
        return error(request,
                     'characteristics weights',
                     reverse('stats', args=(char_id,)),
                     char_id,
                     char)
        
    min_stats = get_min_stats_digested(char)
    model_options = get_options(request, char_id)
    
    inclusions_dic = get_inclusions_dict(char)
    exclusions = get_all_exclusions_ids(char)

    base_stats_by_attr = get_base_stats_by_attr(request, char_id)   
     
    if char.allow_points_distribution:
        stat_points_to_distribute = 5 * (char.level -1)
    else:
        stat_points_to_distribute = 0
        
    # TODO: Sanity check input.
    model_input = ModelInput(char.level,
                             base_stats_by_attr,
                             min_stats,
                             inclusions_dic,
                             set(exclusions),
                             weights,
                             model_options,
                             char.char_class,
                             stat_points_to_distribute)

    solved_status = None
    stats = None
    result = None

    memoized_result = MEMORY.get(model_input)
    if memoized_result is not None:
        solved_status, stats, result = memoized_result
    else:
        model = borrow_model()
        model.setup(model_input)
    
        model.run(2)
        solved_status = model.get_solved_status()
        if solved_status == 'Optimal':
            stats = model.get_stats()
            result = model.get_result_minimal()

        return_model(model)
        MEMORY.put(model_input, (model.get_solved_status(), stats, result))

    if result is None: 
        return HttpResponseRedirect(reverse('infeasible', args=(char.id,)))

    if char.allow_points_distribution:
        set_stats(char, stats)
    set_minimal_solution(char, result)
    
    if spells:
        return HttpResponseRedirect(reverse('spells', args=(char.id,)))
    
    return HttpResponseRedirect(reverse('solution_2', args=(char.id,)))

def set_stats(char, stats):
    for element_name, abr in STATS_NAMES:
        basestats_list = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats_list) == 0:
            basestats = CharBaseStats()
        else:
            basestats = basestats_list[0]
        basestats.char = char
        basestats.stat = element_name
        basestats.total_value = stats[abr]
        if basestats.scrolled_value:
            basestats.total_value += basestats.scrolled_value
        assert 0 <= basestats.total_value and basestats.total_value <= 3000
        basestats.save()
