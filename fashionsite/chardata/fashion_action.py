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

import copy
import logging
import time
from contextlib import contextmanager

from django.utils.translation import gettext_lazy
from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
import pickle
from chardata.char_blobs import read_char_blob
from chardata.data_versions import current_data_version

from chardata.lock_forbid import (get_inclusions_dict, get_all_exclusions_ids,
                                  get_empty_slots)
from chardata.inventory_solver import (get_inventory_solver_settings,
    apply_inventory_restriction, get_effective_stat_overrides)
from chardata.min_stats import get_min_stats_digested
from chardata.models import CharBaseStats
from chardata.presets import (balanced_weights, cross_reading, guard_minimums, guard_plan,
                              guard_reading)
from chardata.smart_build import get_char_aspects
from chardata.solution import set_minimal_solution
from chardata.solution_history import record_solution_generation
from chardata.solution_memory import DatabaseSolutionMemory
from chardata.stats_weights import get_stats_weights
from chardata.util import get_char_or_raise, get_base_stats_by_attr, \
    remove_cache_for_char, version_reverse
from chardata.util_views import error
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp import lpproblem, temporix
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.model_pool import create_model, borrow_model, return_model


if not settings.DEBUG:
    create_model()

logger = logging.getLogger(__name__)

MEMORY = DatabaseSolutionMemory()

#: Wall clock of all the solves of one guarded request; gunicorn and nginx cut a request at 120 s
GUARD_BUDGET_SECONDS = 95
BALANCED_SECONDS = 30
MIN_SOLVE_SECONDS = 10


def _warn_if_unproven(char, solved_status, proven):
    """Log when the solver stopped on time instead of proving the optimum; fresh solves only."""
    if solved_status != 'Optimal' or proven:
        return
    logger.warning(
        'solver stopped on time for char %s (%s): showing the best set it '
        'found, which is not a proven optimum',
        getattr(char, 'id', '?'), getattr(char, 'game_version', '?'))

@contextmanager
def _solver_time_limit(deadline):
    """CBC's limit cut to what is left before deadline, yielded; None keeps the usual one."""
    limit = None if deadline is None else max(int(deadline - time.monotonic()),
                                               MIN_SOLVE_SECONDS)
    if limit is None or limit >= lpproblem.TIME_LIMIT_SECONDS:
        yield None
        return
    # One solver object per process; gunicorn's sync workers serve one request at a time
    previous = lpproblem.SOLVER.timeLimit
    lpproblem.SOLVER.timeLimit = limit
    try:
        yield limit
    finally:
        lpproblem.SOLVER.timeLimit = previous

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
    model_options.update(temporix_model_option(options, char.game_version))
    return model_options


def temporix_model_option(options, game_version):
    """TemporiX flag for the cache key: Touch only, carrying the rule version."""
    if not temporix.version_has_temporix(game_version):
        return {}
    return {'temporix': (temporix.RULE_VERSION
                         if temporix.is_on(options, game_version) else False)}

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

    # An owned item's exo rides on the item, see Model._apply_stat_overrides

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

    def solve(model_input, deadline=None):
        solved_status = None
        stats = None
        result = None

        memoized_result = MEMORY.get(model_input)
        if memoized_result is not None:
            solved_status, stats, result = memoized_result
        else:
            # Wall clock of the solve alone
            started = time.monotonic()
            # A TemporiX model never comes from or goes back to the shared pool
            is_temporix = bool(model_options.get('temporix'))
            if stat_overrides or is_temporix:
                model = Model(stat_overrides=stat_overrides, temporix=is_temporix)
                model.setup(model_input)
                with _solver_time_limit(deadline) as time_limit:
                    model.run(2)
                solved_status = model.get_solved_status()
                proven = model.solution_is_proven()
                pool = model.get_candidate_pool()
                if solved_status == 'Optimal':
                    stats = model.get_stats()
                    result = model.get_result_minimal()
            else:
                model = borrow_model()
                model.setup(model_input)
                with _solver_time_limit(deadline) as time_limit:
                    model.run(2)
                solved_status = model.get_solved_status()
                # Read before return_model, like solved_status
                proven = model.solution_is_proven()
                pool = model.get_candidate_pool()
                if solved_status == 'Optimal':
                    stats = model.get_stats()
                    result = model.get_result_minimal()
                return_model(model)
            # solved_status, not model.get_solved_status(): the model is back in the shared queue
            _warn_if_unproven(char, solved_status, proven)
            if result is not None:
                # Carried on the pickled result, so no migration; older solutions lack them
                result.proven = proven
                result.solve_seconds = time.monotonic() - started
                result.candidate_pool = pool
                result.data_version = current_data_version(char.game_version)
                if time_limit is not None:
                    result.time_limit = time_limit
            # The memory key has no time limit, so a solve the shortened limit cut is not stored
            if time_limit is None or proven or solved_status == 'Infeasible':
                MEMORY.put(model_input, (solved_status, stats, result))
        return solved_status, stats, result

    plan = guard_plan(char)
    if plan is None:
        solved_status, stats, result = solve(model_input)
    else:
        solved_status, stats, result = _guarded_solve(char, model_input, plan, solve)

    if result is None:
        return HttpResponseRedirect(version_reverse(request, 'infeasible', char.id))

    if char.allow_points_distribution:
        set_stats(char, stats)
    char.solved_version = (getattr(result, 'data_version', '')
                           or current_data_version(char.game_version))
    char.solved_time = timezone.now()
    set_minimal_solution(char, result)
    record_solution_generation(char, result)

    if spells:
        return HttpResponseRedirect(version_reverse(request, 'spells', char.id))

    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))

def _guarded_solve(char, model_input, plan, solve):
    """The priority solve under a floor taken from the balanced solve, all within GUARD_BUDGET_SECONDS."""
    kind, percent = plan
    started = time.monotonic()
    budget_end = started + GUARD_BUDGET_SECONDS
    balanced_input = copy.copy(model_input)
    balanced_input.objective_values = balanced_weights(char, model_input.objective_values)
    if balanced_input.objective_values == model_input.objective_values:
        return solve(model_input)
    facts = {'kind': kind, 'percent': percent, 'balanced': None, 'kept': None,
             'fallback': False, 'no_reference': False, 'no_turn': False, 'out_of_time': False,
             'other_seconds': 0.0, 'time_limit': None}
    calls = []

    def timed_solve(solve_input, deadline):
        call_started = time.monotonic()
        solved = solve(solve_input, deadline)
        calls.append((solved, getattr(solved[2], 'solve_seconds', None)
                      or time.monotonic() - call_started))
        return solved

    def has_time():
        return budget_end - time.monotonic() >= MIN_SOLVE_SECONDS

    balanced = timed_solve(balanced_input, started + BALANCED_SECONDS)
    reading = None
    solved = None
    if balanced[2] is None:
        facts.update(fallback=True, no_reference=True)
        solved = timed_solve(model_input, budget_end)
    else:
        reading = guard_reading(char, balanced[2], kind)
        facts['balanced'] = reading['value']
        if not reading['value'] or reading['value'] <= 0:
            facts.update(fallback=True, no_turn=True)
            reading = None
            solved = timed_solve(model_input, budget_end)
        elif has_time():
            guarded_input = copy.copy(model_input)
            guarded_input.minimum_stats = guard_minimums(model_input.minimum_stats, kind, percent,
                                                         reading, get_char_aspects(char))
            solved = timed_solve(guarded_input, budget_end)
            if solved[2] is None:
                logger.warning('the %s safeguard left char %s without a set, solving without it',
                               kind, getattr(char, 'id', '?'))
                facts['fallback'] = True
                solved = timed_solve(model_input, budget_end) if has_time() else None
        if solved is None:
            facts.update(fallback=True, out_of_time=True)
            solved = balanced
    result = solved[2]
    if result is None:
        return solved
    facts['other_seconds'] = sum(seconds for call, seconds in calls if call is not solved)
    facts['time_limit'] = getattr(result, 'time_limit', None)
    if reading is not None and not facts['out_of_time']:
        kept = guard_reading(char, result, kind)
        facts['kept'] = kept['value']
        if facts['kept'] is not None and facts['kept'] < facts['balanced']:
            facts['other_balanced'] = cross_reading(char, reading, kind)
            facts['other_kept'] = cross_reading(char, kept, kind)
    result.guard = facts
    return solved

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
