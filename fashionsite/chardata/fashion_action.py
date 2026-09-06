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

import logging

from django.utils.translation import gettext_lazy
from django.conf import settings
from django.http import HttpResponseRedirect
import pickle
from chardata.char_blobs import read_char_blob

from chardata.lock_forbid import (get_inclusions_dict, get_all_exclusions_ids,
                                  get_empty_slots)
from chardata.inventory_solver import (get_inventory_solver_settings,
    apply_inventory_restriction, get_effective_stat_overrides)
from chardata.min_stats import get_min_stats_digested
from chardata.models import CharBaseStats
from chardata.solution import set_minimal_solution
from chardata.solution_history import record_solution_generation
from chardata.solution_memory import DatabaseSolutionMemory
from chardata.stats_weights import get_stats_weights
from chardata.util import get_char_or_raise, get_base_stats_by_attr, \
    remove_cache_for_char, version_reverse
from chardata.util_views import error
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.model_pool import create_model, borrow_model, return_model


if not settings.DEBUG:
    create_model()

logger = logging.getLogger(__name__)

MEMORY = DatabaseSolutionMemory()


def _warn_if_unproven(char, solved_status, proven):
    """Say so when the solver ran out of time instead of closing the gap.

    A set found in ninety seconds is still worth showing, and this does not
    stop it being shown. What it stops is showing it SILENTLY. Every solver
    runs with timeLimit=90, and PuLP reports a run CBC stopped on time as
    'Optimal' all the same (LpProblem2.get_solution_status says how), so
    without this line the two are the same event everywhere: in the code, in
    the logs, and to anyone deciding whether the site may promise a proven
    optimum on a public page.

    Only fresh solves reach here. A cache hit returns the earlier answer
    without re-solving, and counting it again would inflate the frequency.
    """
    if solved_status != 'Optimal' or proven:
        return
    logger.warning(
        'solver stopped on time for char %s (%s): showing the best set it '
        'found, which is not a proven optimum',
        getattr(char, 'id', '?'), getattr(char, 'game_version', '?'))

def get_options(request, char_id):
    char = get_char_or_raise(request, char_id)
    options = read_char_blob(char.options, {}, 'options', char)
    model_options = {'ap_exo': options.get('ap_exo', False),
                     'range_exo': options.get('range_exo', False),
                     'mp_exo': options.get('mp_exo', False),
                     'dofus': options.get('dofus', True),
                     'dragoturkey': options.get('dragoturkey', True),
                     'seemyool': options.get('seemyool', True),
                     'rhineetle': options.get('rhineetle', True),
                     'prysmaradite': options.get('prysmaradite', False),
                     'shields': options.get('shields', True),
                     'trophies': options.get('trophies', True)}
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
                     gettext_lazy('Characteristics Weights'),
                     version_reverse(request, 'stats', char_id),
                     char_id,
                     char)
        
    min_stats = get_min_stats_digested(char)
    model_options = get_options(request, char_id)
    
    inclusions_dic = get_inclusions_dict(char)
    exclusions = get_all_exclusions_ids(char)
    inv_mode, inv_folder = get_inventory_solver_settings(char)
    if inv_mode == 'only':
        exclusions = apply_inventory_restriction(char, exclusions, inv_folder)
    # Manual per-project overrides win over the inventory rolls.
    stat_overrides = get_effective_stat_overrides(char)

    # An exo recorded on an owned item used to switch the global option on,
    # which adds +1 to the character whether or not the item is worn. The point
    # now rides on the item itself (Model._apply_stat_overrides), so it counts
    # only when the solver equips it. The option stays what the wizard means by
    # it: assume an exo somewhere, on every build.

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
                             stat_points_to_distribute,
                             get_empty_slots(char),
                             stat_overrides)

    solved_status = None
    stats = None
    result = None

    memoized_result = MEMORY.get(model_input)
    if memoized_result is not None:
        solved_status, stats, result = memoized_result
    else:
        if stat_overrides:
            model = Model(stat_overrides=stat_overrides)
            model.setup(model_input)
            model.run(2)
            solved_status = model.get_solved_status()
            proven = model.solution_is_proven()
            if solved_status == 'Optimal':
                stats = model.get_stats()
                result = model.get_result_minimal()
        else:
            model = borrow_model()
            model.setup(model_input)
            model.run(2)
            solved_status = model.get_solved_status()
            # Lu ici pour la meme raison que `solved_status` juste au-dessus :
            # apres `return_model` le modele appartient a la file.
            proven = model.solution_is_proven()
            if solved_status == 'Optimal':
                stats = model.get_stats()
                result = model.get_result_minimal()
            return_model(model)
        # `solved_status` et non `model.get_solved_status()` : le modele
        # vient d etre remis dans la file partagee, et le relire ensuite
        # est une lecture apres liberation. Avec les workers synchrones
        # d aujourd hui rien ne peut s intercaler, donc la valeur est la
        # meme -- mais un `--threads` ajoute a gunicorn armerait la course
        # sans que personne relie les deux, et la memoire garderait le
        # statut d une AUTRE requete.
        _warn_if_unproven(char, solved_status, proven)
        MEMORY.put(model_input, (solved_status, stats, result))

    if result is None:
        return HttpResponseRedirect(version_reverse(request, 'infeasible', char.id))

    if char.allow_points_distribution:
        set_stats(char, stats)
    set_minimal_solution(char, result)
    record_solution_generation(char, result)

    if spells:
        return HttpResponseRedirect(version_reverse(request, 'spells', char.id))

    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))

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
