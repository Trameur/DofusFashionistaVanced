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
import json
import logging
import math
import time
import zlib
from contextlib import contextmanager

from django.utils.translation import gettext_lazy
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.http import require_POST
import pickle
from chardata.char_blobs import read_char_blob
from chardata.data_versions import current_data_version

from chardata.lock_forbid import (get_inclusions_dict, get_all_exclusions_ids,
                                  get_empty_slots)
from chardata.inventory_solver import (get_inventory_solver_settings,
    apply_inventory_restriction, get_effective_stat_overrides)
from chardata.min_stats import get_min_stats_digested
from chardata.models import Char, CharBaseStats, SolutionMemory
from chardata.presets import (balanced_weights, cross_reading, guard_minimums, guard_plan,
                              guard_reading, guarded_stats, short_of_floors, stat_floors)
from chardata.smart_build import get_char_aspects
from chardata.solution import set_minimal_solution
from chardata.solution_history import record_solution_generation
from chardata.solution_memory import DatabaseSolutionMemory
from chardata.spell_modifier_values import (modifier_values, pays_at_the_true_turn,
                                            turn_changers)
from chardata.stats_weights import get_stats_weights
from chardata.util import get_char_or_raise, get_base_stats_by_attr, \
    remove_cache_for_char, version_reverse
from chardata.util_views import error
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp import lpproblem, temporix
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.model_pool import create_model, borrow_model, return_model
from fashionistapulp.structure import get_current_game_version, get_structure


if not settings.DEBUG:
    create_model()

logger = logging.getLogger(__name__)

MEMORY = DatabaseSolutionMemory()

#: Wall clock of all the solves of one guarded request; gunicorn and nginx cut a request at 120 s
GUARD_BUDGET_SECONDS = 95
BALANCED_SECONDS = 30
MIN_SOLVE_SECONDS = 10
#: Limits of the two solves looking for the set closest to the minimums
CLOSEST_SECONDS = 30
CLOSEST_TIE_BREAK_SECONDS = 30
#: Seconds a fresh model took to build and set up, per game version; FIRST_BUILD_SECONDS before the first
_BUILD_SECONDS = {}
FIRST_BUILD_SECONDS = 20


def _warn_if_unproven(char, solved_status, proven):
    """Log when the solver stopped on time instead of proving the optimum; fresh solves only."""
    if solved_status != 'Optimal' or proven:
        return
    logger.warning(
        'solver stopped on time for char %s (%s): showing the best set it '
        'found, which is not a proven optimum',
        getattr(char, 'id', '?'), getattr(char, 'game_version', '?'))

@contextmanager
def _solver_time_limit(deadline, longest=None):
    """CBC's limit cut to what is left before deadline and to longest seconds, yielded; None keeps the usual one."""
    limits = [] if deadline is None else [int(deadline - time.monotonic())]
    if longest is not None:
        limits.append(longest)
    limit = max(min(limits), MIN_SOLVE_SECONDS) if limits else None
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


def _model_input(request, char, weights):
    """The solver input of the build's current settings."""
    min_stats = get_min_stats_digested(char)
    model_options = get_options(request, char.id)

    inclusions_dic = get_inclusions_dict(char)
    exclusions = get_all_exclusions_ids(char)
    inv_mode, inv_folder = get_inventory_solver_settings(char)
    if inv_mode == 'only':
        exclusions = apply_inventory_restriction(char, exclusions, inv_folder)
    # Manual per-project overrides win over the inventory rolls.
    stat_overrides = get_effective_stat_overrides(char)

    # An owned item's exo rides on the item, see Model._apply_stat_overrides

    base_stats_by_attr = get_base_stats_by_attr(request, char.id)

    if char.allow_points_distribution:
        stat_points_to_distribute = 5 * (char.level -1)
    else:
        stat_points_to_distribute = 0

    # TODO: Sanity check input.
    return ModelInput(char.level,
                      base_stats_by_attr,
                      min_stats,
                      inclusions_dic,
                      set(exclusions),
                      weights,
                      model_options,
                      char.char_class,
                      stat_points_to_distribute,
                      get_empty_slots(char),
                      stat_overrides,
                      gender=char.gender or 0,
                      char_name=get_structure().name_a_piece_asks_for(
                          char.char_name or ''))


def _prices_spell_modifiers():
    return bool(getattr(settings, 'PRICE_SPELL_MODIFIERS', False))


def _solution_of(char, result):
    from chardata.solution import get_solution_from_minimal
    return get_solution_from_minimal(char, pickle.loads(pickle.dumps(result)),
                                     refresh_base_stats=False)


def _priced_input(char, solve_input, reference):
    """solve_input with its spell-modifier pieces priced on reference, a solution of the build, None when none pays."""
    game_version = get_current_game_version()
    if reference is None or not turn_changers(game_version, solve_input.char_class,
                                              solve_input.char_level):
        return None
    from chardata.spells_view import _weapon_castable
    values, overlaps = modifier_values(game_version, solve_input.char_class,
                                       solve_input.char_level, solve_input.objective_values,
                                       dict(reference.get_stats_total()),
                                       temporix=bool(solve_input.options.get('temporix')),
                                       weapon=_weapon_castable(reference))
    if not values:
        return None
    priced = copy.copy(solve_input)
    priced.modifier_values = values
    priced.modifier_overlaps = overlaps
    return priced


def _priced_solve(char, solve_input, unpriced, solve, deadline):
    """unpriced, a solve of solve_input, or the solve with its spell-modifier pieces priced on that set when both are proven and the pieces pay at the true turn."""
    if (not _prices_spell_modifiers() or unpriced[2] is None
            or not getattr(unpriced[2], 'proven', False)):
        return unpriced
    try:
        reference = _solution_of(char, unpriced[2])
        priced_input = _priced_input(char, solve_input, reference)
    except Exception:
        logger.exception('could not price the spell modifiers of char %s', getattr(char, 'id', '?'))
        return unpriced
    if priced_input is None or deadline - time.monotonic() < MIN_SOLVE_SECONDS:
        return unpriced
    priced = solve(priced_input, deadline)
    if priced[2] is None or not getattr(priced[2], 'proven', False):
        return unpriced
    try:
        pays = pays_at_the_true_turn(char, priced_input, _solution_of(char, priced[2]), reference)
    except Exception:
        logger.exception('could not check the priced set of char %s', getattr(char, 'id', '?'))
        return unpriced
    return priced if pays else unpriced


def fashion(request, char_id, spells=False, seed=None):
    started = time.monotonic()
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

    model_input = _model_input(request, char, weights)
    model_options = model_input.options
    stat_overrides = model_input.stat_overrides

    def run(model):
        if seed is None:
            model.run(2)
        else:
            model.run(2, seed=seed)

    def solve(model_input, deadline=None, longest=None):
        solved_status = None
        stats = None
        result = None

        memoized_result = MEMORY.get(model_input)
        # Only 'Infeasible' is a proof; a stored search that ran out of time is solved again
        stale = (memoized_result is not None and memoized_result[2] is None
                 and memoized_result[0] != 'Infeasible')
        if memoized_result is not None and not stale:
            solved_status, stats, result = memoized_result
        else:
            # Wall clock of the solve alone
            started = time.monotonic()
            # A TemporiX model never comes from or goes back to the shared pool
            is_temporix = bool(model_options.get('temporix'))
            if stat_overrides or is_temporix:
                model = Model(stat_overrides=stat_overrides, temporix=is_temporix)
                model.setup(model_input)
                with _solver_time_limit(deadline, longest) as time_limit:
                    run(model)
                solved_status = model.get_solved_status()
                proven = model.solution_is_proven()
                pool = model.get_candidate_pool()
                state = None if proven else _search_state(model)
                if solved_status == 'Optimal':
                    stats = model.get_stats()
                    result = model.get_result_minimal()
            else:
                model = borrow_model()
                model.setup(model_input)
                with _solver_time_limit(deadline, longest) as time_limit:
                    run(model)
                solved_status = model.get_solved_status()
                # Read before return_model, like solved_status
                proven = model.solution_is_proven()
                pool = model.get_candidate_pool()
                state = None if proven else _search_state(model)
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
                search = _new_search(state, model_input,
                                     time_limit or lpproblem.SOLVER.timeLimit)
                if search is not None:
                    result.search = search
            # The memory key has no time limit, so a solve the shortened limit cut is not stored
            if ((time_limit is None or proven or solved_status == 'Infeasible')
                    and (result is not None or solved_status == 'Infeasible')):
                if stale and result is None:
                    _overwrite_memory(model_input, (solved_status, stats, result))
                elif stale:
                    MEMORY.keep_better(model_input, (solved_status, stats, result), False)
                else:
                    MEMORY.put(model_input, (solved_status, stats, result))
        return solved_status, stats, result

    plan = guard_plan(char)
    if plan is None:
        solved_status, stats, result = _priced_solve(char, model_input, solve(model_input), solve,
                                                     started + GUARD_BUDGET_SECONDS)
    else:
        solved_status, stats, result = _guarded_solve(char, model_input, plan, solve)

    if result is None:
        return _without_a_set(request, char, model_input,
                              'proof' if solved_status == 'Infeasible' else 'time',
                              int(round(time.monotonic() - started)), seed,
                              started + GUARD_BUDGET_SECONDS, spells)

    _bind_search(result, model_input, plan)
    _store_set(char, stats, result)
    return _to_the_set(request, char, spells)


def _to_the_set(request, char, spells=False):
    if spells:
        return HttpResponseRedirect(version_reverse(request, 'spells', char.id))

    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))


def _store_set(char, stats, result):
    if char.allow_points_distribution:
        set_stats(char, stats)
    char.solved_version = (getattr(result, 'data_version', '')
                           or current_data_version(char.game_version))
    char.solved_time = timezone.now()
    set_minimal_solution(char, result)
    record_solution_generation(char, result)


def solve_budget_seconds(char):
    """The longest a /fashion/ request of the build may take, what the waiting screen counts towards."""
    budget = GUARD_BUDGET_SECONDS
    options = read_char_blob(char.options, {}, 'options', char)
    if get_effective_stat_overrides(char) or temporix.is_on(options, char.game_version):
        budget = max(budget, lpproblem.TIME_LIMIT_SECONDS
                     + _BUILD_SECONDS.get(char.game_version, FIRST_BUILD_SECONDS))
    return int(math.ceil(budget))


def _asks_a_minimum(minimum_stats):
    values = [value for name, value in minimum_stats.items() if name != 'adv_mins']
    values += list((minimum_stats.get('adv_mins') or {}).values())
    return any(isinstance(value, (int, float)) and not isinstance(value, bool)
               for value in values)


def _without_a_set(request, char, model_input, cause, seconds, attempt, deadline, spells=False,
                   reuse=True):
    """Looks for the set closest to the minimums, then shows the failure page, or the set when it meets them all."""
    from chardata.closest_set import read_failure, remember_failure
    key = model_input.cache_key()
    known = read_failure(request, char, model_input) if reuse else None
    if _settled(known):
        closest = known
        if known.get('cause') == 'proof':
            cause = 'proof'
    else:
        closest = _closest_solve(char, model_input, cause, deadline)
    if closest['state'] == 'locks':
        cause = 'proof'
    elif (closest['state'] == 'found' and cause == 'time' and closest['meets_all']
          and closest.get('tie_break')):
        _store_set(char, closest['stats'], _answer_of(char, model_input, closest))
        return _to_the_set(request, char, spells)
    remember_failure(request, char, key, dict(closest, cause=cause, seconds=seconds,
                                              attempt=attempt or 0))
    return HttpResponseRedirect(version_reverse(request, 'infeasible', char.id))


def _settled(entry):
    """Whether a remembered closest solve already answers the same settings: locks, or a set short of the minimums."""
    if entry is None:
        return False
    return (entry.get('state') == 'locks'
            or (entry.get('state') == 'found' and not entry.get('meets_all')))


def _answer_of(char, model_input, closest):
    """The closest set meeting every minimum after a stop on time, as a solve's result of model_input."""
    tie_break = closest['tie_break']
    result = closest['minimal']
    result.proven = tie_break['proven']
    result.solve_seconds = closest['solve_seconds']
    result.candidate_pool = closest['pool']
    result.data_version = current_data_version(char.game_version)
    if tie_break['limit'] is not None:
        result.time_limit = tie_break['limit']
    if not tie_break['proven']:
        search = _new_search(tie_break['state'], model_input,
                             tie_break['limit'] or lpproblem.SOLVER.timeLimit)
        if search is not None:
            result.search = search
            _bind_search(result, model_input, guard_plan(char))
    return result


def _closest_solve(char, model_input, cause, deadline):
    """The set nearest the build's minimums with every other rule kept, on a model of its own, by deadline."""
    if not _asks_a_minimum(model_input.minimum_stats):
        return {'state': 'locks' if cause == 'proof' else 'skipped'}
    version = get_current_game_version()
    solve_input = copy.copy(model_input)
    solve_input.objective_values = dict(model_input.objective_values)

    def left():
        return deadline - time.monotonic()

    if left() < MIN_SOLVE_SECONDS + _BUILD_SECONDS.get(version, FIRST_BUILD_SECONDS):
        return {'state': 'no_time'}
    try:
        started = time.monotonic()
        model = Model(stat_overrides=solve_input.stat_overrides,
                      temporix=bool(solve_input.options.get('temporix')))
        model.setup(solve_input)
        shortfalls = model.add_elastic_minimums(solve_input.minimum_stats,
                                                solve_input.char_level)
        _BUILD_SECONDS[version] = time.monotonic() - started
        if not shortfalls:
            return {'state': 'locks' if cause == 'proof' else 'skipped'}
        if left() < MIN_SOLVE_SECONDS:
            return {'state': 'no_time'}
        model.minimise_shortfall(shortfalls)
        with _solver_time_limit(deadline, CLOSEST_SECONDS) as limit:
            model.run(2)
        status = model.get_solved_status()
        if status == 'Infeasible':
            return {'state': 'locks'}
        if status != 'Optimal':
            return {'state': 'stopped'}
        closeness = {'closest_proven': model.solution_is_proven(),
                     'closest_seconds': limit or lpproblem.SOLVER.timeLimit}
        found = dict(_closest_found(model, shortfalls), **closeness)
        if left() >= MIN_SOLVE_SECONDS:
            model.hold_shortfall(shortfalls, found['shortfall'])
            with _solver_time_limit(deadline, CLOSEST_TIE_BREAK_SECONDS) as tie_limit:
                model.run(2, warm_start=found['values'])
            if model.get_solved_status() == 'Optimal':
                found = dict(_closest_found(model, shortfalls), **closeness)
                found['tie_break'] = {'proven': model.solution_is_proven(), 'limit': tie_limit,
                                      'state': model.get_search_state()}
        found.pop('values', None)
        found['solve_seconds'] = time.monotonic() - started
        return found
    except Exception:
        logger.exception('could not look for the closest set of char %s', getattr(char, 'id', '?'))
        return {'state': 'error'}


def _closest_found(model, shortfalls):
    minimal = model.get_result_minimal()
    shortfall = model.get_shortfall(shortfalls)
    return {'state': 'found', 'minimal': minimal,
            'items': [item_id for item_id in minimal.item_per_slot.values()
                      if item_id is not None],
            'stats': dict(model.get_stats()), 'shortfall': shortfall,
            'meets_all': shortfall <= 1e-6, 'pool': model.get_candidate_pool(),
            'values': model.get_search_state()['values']}

def _guarded_solve(char, model_input, plan, solve):
    """The priority solve under floors taken from the balanced solve, all within GUARD_BUDGET_SECONDS."""
    kind, percent = plan
    started = time.monotonic()
    budget_end = started + GUARD_BUDGET_SECONDS
    balanced_input = copy.copy(model_input)
    balanced_input.objective_values = balanced_weights(char, model_input.objective_values)
    if balanced_input.objective_values == model_input.objective_values:
        return _priced_solve(char, model_input, solve(model_input), solve, budget_end)
    facts = {'kind': kind, 'percent': percent, 'balanced': None, 'kept': None,
             'fallback': False, 'no_reference': False, 'balanced_out_of_time': False,
             'no_turn': False, 'out_of_time': False, 'other_seconds': 0.0, 'time_limit': None,
             'floors': {}, 'short': []}
    calls = []

    def timed_solve(solve_input, deadline, longest=None):
        call_started = time.monotonic()
        solved = solve(solve_input, deadline, longest)
        calls.append((solved, getattr(solved[2], 'solve_seconds', None)
                      or time.monotonic() - call_started))
        return solved

    def has_time():
        return budget_end - time.monotonic() >= MIN_SOLVE_SECONDS

    balanced = timed_solve(balanced_input, budget_end - MIN_SOLVE_SECONDS, BALANCED_SECONDS)
    reading = None
    solved = None
    if balanced[2] is None:
        facts.update(fallback=True, no_reference=True,
                     balanced_out_of_time=balanced[0] != 'Infeasible')
        solved = _priced_solve(char, model_input, timed_solve(model_input, budget_end),
                               timed_solve, budget_end)
    else:
        reading = guard_reading(char, balanced[2], kind)
        if reading['value'] and reading['value'] > 0:
            facts['balanced'] = reading['value']
        else:
            facts['no_turn'] = True
        if has_time():
            facts['floors'] = stat_floors(kind, percent, reading['totals'],
                                          guarded_stats(char, balanced_input.objective_values))
            guarded_input = copy.copy(model_input)
            guarded_input.minimum_stats = guard_minimums(model_input.minimum_stats, kind, percent,
                                                         reading, get_char_aspects(char),
                                                         facts['floors'])
            solved = _priced_solve(char, guarded_input, timed_solve(guarded_input, budget_end),
                                   timed_solve, budget_end)
            if solved[2] is None:
                logger.warning('the %s safeguard left char %s without a set, solving without it',
                               kind, getattr(char, 'id', '?'))
                facts['fallback'] = True
                solved = (_priced_solve(char, model_input, timed_solve(model_input, budget_end),
                                        timed_solve, budget_end) if has_time() else None)
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
        if not facts['fallback']:
            facts['short'] = short_of_floors(facts['floors'], kept['totals'])
        if facts['kept'] is not None and facts['balanced'] is not None:
            trails = facts['kept'] < facts['balanced']
            # _guard_after_search reads it on the set a continued search finds
            if trails or getattr(result, 'search', None):
                facts['other_balanced'] = cross_reading(char, reading, kind)
            if trails:
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


def _search_state(model):
    reader = getattr(model, 'get_search_state', None)
    return reader() if reader is not None else None


def _pack_start(values):
    return zlib.compress(json.dumps(values, sort_keys=True).encode('ascii'))


def _unpack_start(packed):
    return json.loads(zlib.decompress(packed).decode('ascii'))


def _new_search(state, solve_input, limit):
    """What continuing a solve stopped on time needs, None when the model gave nothing to start from."""
    if not state or state.get('objective') is None:
        return None
    return {'objective': state['objective'], 'bound': state['bound'],
            'start': _pack_start(state['values']), 'limit': limit,
            'minimum_stats': solve_input.minimum_stats,
            'objective_values': solve_input.objective_values}


def _bind_search(result, model_input, plan):
    """Ties a stopped solve's search to the build settings it answers, keeping only what differs from them."""
    search = getattr(result, 'search', None)
    if not search:
        return
    search = dict(search, key=model_input.cache_key(), plan=plan)
    for field in ('minimum_stats', 'objective_values'):
        if search.get(field) == getattr(model_input, field):
            search[field] = None
    result.search = search


def search_gap(search):
    """How much more the best set can score than this one, as a fraction; None when unknown."""
    objective, bound = (search or {}).get('objective'), (search or {}).get('bound')
    if objective is None or bound is None or objective <= 0:
        return None
    return max(bound - objective, 0.0) / objective


def continuation_input(request, char, minimal):
    """The input the stored set was solved on, when its search can go on; None otherwise."""
    search = getattr(minimal, 'search', None)
    if (getattr(minimal, 'proven', None) is not False or not isinstance(search, dict)
            or not search.get('start') or 'key' not in search):
        return None
    if getattr(minimal, 'data_version', None) != current_data_version(char.game_version):
        return None
    weights = get_stats_weights(char, persist=False)
    if not any(value != 0 for value in weights.values()):
        return None
    model_input = _model_input(request, char, weights)
    if model_input.cache_key() != search['key'] or guard_plan(char) != search.get('plan'):
        return None
    solve_input = copy.copy(model_input)
    for field in ('minimum_stats', 'objective_values'):
        if search.get(field) is not None:
            setattr(solve_input, field, search[field])
    return solve_input


@require_POST
def continue_search(request, char_id):
    """Searches on from the stored set of a solve stopped on time and keeps the better set."""
    started = time.monotonic()
    char = get_char_or_raise(request, char_id)
    blob = char.minimal_solution
    minimal = read_char_blob(blob, None, 'minimal_solution', char)
    solve_input = continuation_input(request, char, minimal)
    if solve_input is not None:
        _continue_search(request, char, blob, minimal, solve_input,
                         started + GUARD_BUDGET_SECONDS)
        remove_cache_for_char(char.id)
    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))


@require_POST
def keep_closest_set(request, char_id):
    """Stores the closest set the failure page shows as the build's set."""
    from chardata.closest_set import closest_minimal, current_input, forget_failure, read_failure
    char = get_char_or_raise(request, char_id)
    model_input = current_input(request, char)
    entry = read_failure(request, char, model_input) if model_input is not None else None
    if entry is None or entry.get('state') != 'found':
        return HttpResponseRedirect(version_reverse(request, 'infeasible', char.id) + '?gone=1')
    _store_set(char, entry['stats'], closest_minimal(entry, model_input))
    forget_failure(request, char)
    remove_cache_for_char(char.id)
    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))


@require_POST
def search_again(request, char_id):
    """Solves the build again on another search path."""
    from chardata.closest_set import read_failure
    char = get_char_or_raise(request, char_id)
    previous = read_failure(request, char) or {}
    return fashion(request, char_id, seed=previous.get('attempt', 0) + 1)


@require_POST
def find_closest_set(request, char_id):
    """Looks for the closest set on a budget of its own, when the failed solve left it no time."""
    from chardata.closest_set import current_input, read_failure
    started = time.monotonic()
    char = get_char_or_raise(request, char_id)
    model_input = current_input(request, char)
    previous = read_failure(request, char, model_input) if model_input is not None else None
    if previous is None:
        return fashion(request, char_id)
    remove_cache_for_char(char.id)
    return _without_a_set(request, char, model_input, previous.get('cause', 'time'),
                          previous.get('seconds'), previous.get('attempt', 0),
                          started + GUARD_BUDGET_SECONDS, reuse=False)


def _continue_search(request, char, blob, minimal, solve_input, deadline):
    search = minimal.search
    rounds = search.get('rounds', 0) + 1
    started = time.monotonic()
    is_temporix = bool(solve_input.options.get('temporix'))
    pooled = not (solve_input.stat_overrides or is_temporix)
    if pooled:
        model = borrow_model()
    else:
        model = Model(stat_overrides=solve_input.stat_overrides, temporix=is_temporix)
    model.setup(solve_input)
    with _solver_time_limit(deadline) as time_limit:
        # CBC is deterministic: the same start and seed replay the same search
        model.run(2, warm_start=_unpack_start(search['start']),
                  seed=rounds if rounds > 1 else None)
    proven = model.solution_is_proven()
    state = model.get_search_state()
    found = stats = None
    if model.get_solved_status() == 'Optimal':
        stats = model.get_stats()
        found = model.get_result_minimal()
    if pooled:
        return_model(model)
    if state.get('start_accepted') is False:
        logger.warning('CBC did not take the stored set of char %s as its start', char.id)

    before = state['start_objective']
    if before is None:
        before = search['objective']
    after = state['objective']
    tolerance = 1e-6 * max(1.0, abs(before))
    if after is None or after < before - tolerance:
        logger.warning('the search continued for char %s reached %s under the stored %s; '
                       'the stored set stays', char.id, after, before)
        minimal.search = dict(search, rounds=rounds)
        _save_search(request, char, blob, minimal)
        return
    bounds = [bound for bound in (search.get('bound'), after if proven else state['bound'])
              if bound is not None]
    bound = min(bounds) if bounds else None
    proven = proven or (bound is not None and bound <= after + tolerance)
    seconds = (getattr(minimal, 'solve_seconds', None) or 0) + time.monotonic() - started
    limit = (search.get('limit') or 0) + (time_limit or lpproblem.SOLVER.timeLimit)

    if after <= before + tolerance:
        minimal.proven = proven
        minimal.solve_seconds = seconds
        if proven:
            minimal.search = None
            _keep_in_memory(solve_input, minimal.stats, minimal, True)
        else:
            minimal.search = dict(search, objective=before, bound=bound, limit=limit,
                                  rounds=rounds)
        _save_search(request, char, blob, minimal)
        return

    found.proven = proven
    found.solve_seconds = seconds
    found.candidate_pool = getattr(minimal, 'candidate_pool', None)
    found.data_version = minimal.data_version
    if not proven:
        found.search = dict(search, objective=after, bound=bound, limit=limit, rounds=rounds,
                            start=_pack_start(state['values']))
    if isinstance(getattr(minimal, 'guard', None), dict):
        found.guard = _guard_after_search(char, minimal.guard, found)
    _keep_in_memory(solve_input, stats, found, proven or time_limit is None)
    _save_search(request, char, blob, found, stats)


def _save_search(request, char, blob, solution, stats=None):
    """Stores what a continued search left, as a new set when stats are given, unless the build changed meanwhile."""
    with transaction.atomic():
        current = Char.objects.select_for_update().filter(pk=char.pk).first()
        if current is None or bytes(current.minimal_solution) != bytes(blob):
            current = None
        else:
            stored = read_char_blob(current.minimal_solution, None, 'minimal_solution', current)
            if continuation_input(request, current, stored) is None:
                current = None
        if current is None:
            logger.info('the build of char %s changed during its search, which is dropped',
                        char.id)
            return
        if stats is None:
            current.minimal_solution = pickle.dumps(solution)
            current.save(update_fields=['minimal_solution'])
            return
        if current.allow_points_distribution:
            set_stats(current, stats)
        current.solved_time = timezone.now()
        set_minimal_solution(current, solution)
        record_solution_generation(current, solution)


def _guard_after_search(char, facts, result):
    """The safeguard facts read again on the set a continued search found."""
    facts = dict(facts)
    if facts.get('no_reference') or facts.get('out_of_time') or facts.get('kept') is None:
        return facts
    kept = guard_reading(char, result, facts['kind'])
    facts['kept'] = kept['value']
    if not facts.get('fallback') and facts.get('floors'):
        facts['short'] = short_of_floors(facts['floors'], kept['totals'])
    facts.pop('other_kept', None)
    if (facts.get('other_balanced') is not None and facts['kept'] is not None
            and facts.get('balanced') is not None and facts['kept'] < facts['balanced']):
        facts['other_kept'] = cross_reading(char, kept, facts['kind'])
    return facts


def _keep_in_memory(solve_input, stats, result, create):
    """Offers the solution memory a set found for solve_input, without the build's own facts."""
    shared = copy.copy(result)
    shared.__dict__.pop('guard', None)
    if getattr(shared, 'search', None):
        shared.search = dict(
            {key: value for key, value in shared.search.items() if key not in ('key', 'plan')},
            minimum_stats=solve_input.minimum_stats,
            objective_values=solve_input.objective_values)
    MEMORY.keep_better(solve_input, ('Optimal', stats, shared), create)


def _overwrite_memory(model_input, result_tuple):
    """Writes result_tuple over the remembered one; put never overwrites and keep_better keeps a row without a set."""
    if isinstance(MEMORY, DatabaseSolutionMemory):
        SolutionMemory.objects.filter(input_hash=model_input.cache_key()).update(
            stored=pickle.dumps(result_tuple))
    else:
        MEMORY.put(model_input, result_tuple)
