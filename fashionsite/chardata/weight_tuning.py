# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Tunes the default weights of a version on the sets the site's own doors give.

A weight is a ratio of the played characteristic's weight. Each round reads, on the set the door returned, what a
point of every stat is worth to the best turn and to the effective HP, blends it into the ratios and solves again.
A cell ships only when it also gains on the credited score, which counts the effect-table items the reader cannot see.

    py fashionsite/manage.py tune_weights --version dofus3 --out <folder outside the repository>
"""
import hashlib
import json
import logging
import math
import os
import statistics
import subprocess
import time
from collections import Counter, namedtuple
from datetime import date

from chardata.weapon_terms import CHARACTERISTIC_STEP
from chardata.weight_table import (BANDS, DAMAGE_STATS, GRID_LEVEL, RESIST_STATS, SCENARIOS, SHARE_STATS, TABLE_STATS,
                                   cell_table, element_key, engine_ratios, grid_element_sets, override_weight_table,
                                   unit_of)
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.item_effects import (COST_ONLY_STATUSES, ELEMENT_KEYS, PLAYED_SHARE, is_valued,
                                          load_effect_table, played_characteristics)

logger = logging.getLogger(__name__)

#: bumped by hand when the reader, the score, the instances or the acceptance change
GENERATOR_VERSION = 1

STEP = CHARACTERISTIC_STEP
MAX_ROUNDS = 4
TIME_LIMIT = 90
RETRY_FACTOR = 2
TRUST_FACTOR = 2
BOUNDS = (0.25, 4)
FOLD_AGREEMENT = 1.25
MIN_DEV_RUNS = 4
MAX_LOSS = 0.01
CEILING_FACTOR = 1.5
CEILING_MARGIN = 0.05
BLIND_SHARE = 0.75
SPLIT_TOLERANCE = 0.10
SHARE_MARGIN = 0.02
SHARD_WEAK_LIMIT = 0.25
SHARD_MIN_CELLS = 8
SWITCH_SHARE = 0.5
DRY_ROUNDS = 2
PROBE_RUNS = 3
#: for the projection of --plan: seconds of one door call, of the reads after it, and of the reads of a guarded pair
CALL_SECONDS = 18.7
READ_SECONDS = 2.5
GUARDED_READ_SECONDS = 3
EXPECTED_ROUNDS = 3
RESOLVE_MARGIN = 1.1
DEV_INSTANCES = 4

#: scenario: the lambda of the fit and the two ends the acceptance is read at
SCENARIO_LAMBDA = {'plain': {'lo': 0.25, 'fit': 0.25, 'hi': 0.4},
                   'glasscannon': {'lo': 0.15, 'fit': 0.15, 'hi': 0.29},
                   'tank': {'lo': 0.8, 'fit': 1.0, 'hi': 1.2}}
#: scenario: the style of the door and its priority
SCENARIO_DOOR = {'plain': (None, 'balanced'), 'glasscannon': ('solo_pvm', 'balanced'),
                 'tank': ('group_pvm', 'balanced')}
#: scenario: the priority of its guarded door, which has no style
GUARDED_PRIORITY = {'glasscannon': 'damage', 'tank': 'defense'}
#: (minimums, tier, split) of the five instances of a cell
INSTANCE_PLAN = (('door', 'high', 'dev_a'), ('meta', 'mid', 'dev_a'), ('meta', 'high', 'dev_b'),
                 ('door', 'mid', 'dev_b'), ('door', 'low', 'test'))
DEV_SPLITS = ('dev_a', 'dev_b')
#: tier: how many of the heaviest pieces of the first engine set it forbids
TIER_FORBIDDEN = {'high': 0, 'mid': 3, 'low': 6}
META_MINIMUMS = {'AP': 12, 'MP': 6}
SMOKE_INSTANCES = (('Iop', ('str',), 'glasscannon', 'door', 'high'), ('Cra', ('agi',), 'plain', 'meta', 'high'))

#: the equivalents of an effect-table item that reach the panel's turn
CREDITED_STATS = ELEMENT_KEYS + ('pow', 'dam', 'perspedam', 'ch', 'ap')
TURN_STATS = ('pow',) + DAMAGE_STATS + ('perspedam', 'perweadam')
LIFE_STATS = ('hp', 'vit')
PERCENT_RESIST_KEYS = RESIST_STATS
#: every stat a cell can hold: the table's, and a duo's shares on its characteristics
READ_STATS = TABLE_STATS + SHARE_STATS

Cell = namedtuple('Cell', 'char_class elements scenario band')
Instance = namedtuple('Instance', 'char_class elements scenario band minimums tier split')
Read = namedtuple('Read', 'ratios switched turn ehp g_char')
Credit = namedtuple('Credit', 'turn ehp')


def cell_key(cell):
    return '/'.join((cell.char_class, element_key(cell.elements), cell.scenario, cell.band))


def instance_key(instance):
    return '/'.join((cell_key(instance), instance.minimums, instance.tier))


def lot1_cells(classes=None, elements=None, scenarios=None):
    """The cells of the grid, one or two elements, filtered by class, element key and scenario."""
    cells = []
    for char_class in CHARACTER_CLASSES:
        for played in grid_element_sets():
            for scenario in SCENARIOS:
                if ((classes and char_class not in classes) or (elements and element_key(played) not in elements)
                        or (scenarios and scenario not in scenarios)):
                    continue
                cells.append(Cell(char_class, played, scenario, BANDS[0]))
    return cells


def instances_for(cell):
    return [Instance(cell.char_class, cell.elements, cell.scenario, cell.band, minimums, tier, split)
            for minimums, tier, split in INSTANCE_PLAN]


def split_digest(instances):
    """sha1 of the instances and their splits: a pure function of the instance keys."""
    rows = sorted(list(map(str, instance)) for instance in instances)
    return hashlib.sha1(json.dumps(rows).encode('utf-8')).hexdigest()


def groups_of(cells):
    """The cells grouped by class, number of elements and scenario, in order: the unit a worker runs."""
    groups = {}
    for cell in cells:
        groups.setdefault((cell.char_class, len(cell.elements), cell.scenario), []).append(cell)
    return list(groups.values())


def integer_weights(ratios, unit):
    return {stat: int(round(value * unit)) for stat, value in ratios.items()}


# The reader

def effective_hp(totals):
    from chardata.presets import effective_hp as site_effective_hp
    return site_effective_hp(totals)


def _order_counts(order):
    return Counter(name for name, _damage in order)


def read_gains(view, keys, step=STEP):
    """({stat: best-turn gain per point}, the stats whose raise changes the cast list), each raised alone by `step`."""
    base, order = view.reader.cast(view.worn)
    names = _order_counts(order)
    gains, switched = {}, set()
    for key in keys:
        total, raised = view.reader.cast(view.worn, {key: step})
        gains[key] = (total - base) / float(step)
        if _order_counts(raised) != names:
            switched.add(key)
    return gains, switched


def _ap_read(view):
    base, order = view.reader.cast(view.worn)
    raised, raised_order = view.reader.cast(view.worn, None, view.reader.ap + 1)
    return raised - base, _order_counts(order) != _order_counts(raised_order)


def ap_gain(view):
    """The secant of one more AP: the turn on ap + 1 less the turn on ap."""
    return _ap_read(view)[0]


def clamp_shares(shares):
    """A duo's shares kept far enough apart that both stay played once the weights are whole."""
    if len(shares) != 2:
        return dict(shares)
    low = 2 * PLAYED_SHARE / (1 + PLAYED_SHARE) + SHARE_MARGIN
    first, second = sorted(shares)
    value = min(max(shares[first], low), 2 - low)
    return {first: value, second: 2 - value}


def element_split(view, played):
    """{element: share}: each element's own gain sets its share, equal unless the single gains miss the joint one."""
    count = len(played)
    equal = {key: 1.0 for key in played}
    if count != 2:
        return equal
    base = view.reader.full(view.worn)
    joint = view.reader.full(view.worn, {key: STEP for key in played}) - base
    single = {key: view.reader.full(view.worn, {key: STEP}) - base for key in played}
    total = sum(single.values())
    if joint <= 0 or total <= 0 or abs(total - joint) > SPLIT_TOLERANCE * joint:
        return equal
    return clamp_shares({key: count * gain / total for key, gain in single.items()})


def read_ratios(view, totals, played, lam):
    """Read(ratios, switched, turn, ehp, g_char) on one set, None when it has no turn to read.

    r_k = (g_k + lam * (T / E) * e_k) / g_char, with e the gain in effective HP of a point of the stat.
    """
    ehp = effective_hp(totals)
    hp = totals.get('hp', 0)
    turn = view.reader.full(view.worn)
    g_char = view.per_point(played)
    if not (turn > 0 and g_char > 0 and ehp > 0 and hp > 0):
        return None
    gains, switched = read_gains(view, TURN_STATS, STEP)
    gains['ap'], ap_switched = _ap_read(view)
    if ap_switched:
        switched.add('ap')
    mean = sum(totals.get(key, 0) for key in PERCENT_RESIST_KEYS) / 5.0
    life = lam * turn / ehp * (ehp / hp) / g_char
    resist = lam * turn / ehp * (ehp / (5 * (100 - mean))) / g_char
    ratios = {stat: gain / g_char for stat, gain in gains.items()}
    ratios.update({stat: life for stat in LIFE_STATS})
    ratios.update({stat: resist for stat in PERCENT_RESIST_KEYS})
    if len(played) == 2:
        ratios.update(element_split(view, played))
    return Read(ratios, switched, turn, ehp, g_char)


def fit_score(view, totals, lam):
    """ln T + lam * ln E on the set, None when either is not positive."""
    turn = view.reader.full(view.worn)
    ehp = effective_hp(totals)
    if not (turn > 0 and ehp > 0):
        return None
    return math.log(turn) + lam * math.log(ehp)


# The credited score

class _CreditedSolution(object):
    """A solution whose totals carry extra stats, for reading the panel's turn on them."""

    def __init__(self, solution, extra):
        self._solution = solution
        self._extra = extra

    def get_stats_total(self):
        totals = dict(self._solution.get_stats_total())
        for stat, amount in self._extra.items():
            totals[stat] = totals.get(stat, 0) + amount
        return totals

    def __getattr__(self, name):
        return getattr(self._solution, name)


_EFFECT_INDEX = {}


def _effect_entries(effect_table):
    """{site item id: effect-table entry} of the valued entries."""
    key = id(effect_table)
    if key not in _EFFECT_INDEX:
        # The table stays referenced beside its index so that its id is not handed to another table
        entries = ((effect_table or {}).get('items') or {}).values()
        _EFFECT_INDEX[key] = (effect_table, {item_id: entry for entry in entries
                                              if is_valued(entry) for item_id in entry.get('site_ids') or ()})
    return _EFFECT_INDEX[key][1]


def worn_equivalents(char, solution, effect_table, weights):
    """(extra stats, % final damage, hp points) of the valued effect-table items the set wears."""
    played = played_characteristics(weights)
    entries = _effect_entries(effect_table)
    extra, final, hp_points = {}, 0, 0
    for result_item in solution.item_list:
        entry = entries.get(result_item.id) if result_item.item_added else None
        if entry is None:
            continue
        equivalents = entry['equivalents']
        by_count = (entry.get('equivalents_by_elements') or {}).get(str(len(played)))
        if by_count is not None:
            equivalents = by_count
        cost_only = entry.get('status') in COST_ONLY_STATUSES
        for stat, amount in equivalents.items():
            if stat == 'sets' or (amount > 0 and cost_only):
                continue
            if stat == 'final':
                final += amount
            elif stat == 'hp':
                hp_points += amount * char.level / 200.0
            elif stat == 'played_char':
                for key in played:
                    extra[key] = extra.get(key, 0) + amount
            elif stat in CREDITED_STATS:
                extra[stat] = extra.get(stat, 0) + amount
    return extra, final, hp_points


def credited_turn(char, solution, effect_table, weights=None, deltas=None):
    """The panel's best turn plus the equivalents of the worn effect-table items, times 1 + final / 100."""
    from chardata.presets import _panel_turn
    from chardata.stats_weights import get_stats_weights
    weights = weights if weights is not None else get_stats_weights(char, persist=False)
    extra, final, _hp = worn_equivalents(char, solution, effect_table, weights)
    for stat, amount in (deltas or {}).items():
        extra[stat] = extra.get(stat, 0) + amount
    if not extra and not final:
        return _panel_turn(char, solution)
    turn = _panel_turn(char, _CreditedSolution(solution, extra))
    return turn * (1 + final / 100.0) if turn else turn


def credited_parts(char, solution, effect_table):
    """Credit(turn, effective HP) of the set with the worn effect-table items counted, None without a turn."""
    from chardata.stats_weights import get_stats_weights
    weights = get_stats_weights(char, persist=False)
    turn = credited_turn(char, solution, effect_table, weights)
    if not turn or turn <= 0:
        return None
    _extra, _final, hp_points = worn_equivalents(char, solution, effect_table, weights)
    totals = dict(solution.get_stats_total())
    totals['hp'] = totals.get('hp', 0) + hp_points
    ehp = effective_hp(totals)
    return Credit(turn, ehp) if ehp > 0 else None


def credited_score(char, solution, lam, effect_table=None):
    """ln T_acc + lam * ln E_acc, None when the set has no credited turn."""
    effect_table = load_effect_table(char.game_version) if effect_table is None else effect_table
    credit = credited_parts(char, solution, effect_table)
    if credit is None:
        return None
    return math.log(credit.turn) + lam * math.log(credit.ehp)


def power_share(char, solution, effect_table=None):
    """The share of the credited turn that power brings: credited gain per power point times the power worn."""
    from chardata.stats_weights import get_stats_weights
    effect_table = load_effect_table(char.game_version) if effect_table is None else effect_table
    weights = get_stats_weights(char, persist=False)
    turn = credited_turn(char, solution, effect_table, weights)
    if not turn or turn <= 0:
        return None
    raised = credited_turn(char, solution, effect_table, weights, {'pow': STEP})
    return (raised - turn) / float(STEP) * solution.get_stats_total().get('pow', 0) / turn


def visible_damage_share(char_class, level, game_version):
    """Share of the class's damage that best_turn evaluates, None when the data cannot say."""
    from chardata.spell_combo import castable_spells
    from chardata.spell_reference import get_spell_reference
    entries = (get_spell_reference(game_version) or {}).get(char_class)
    if not entries:
        return None
    # The reference says the class places summons; their damage is not in the data
    if any(entry.get('summon_push') for entry in entries):
        return None

    def worth(effect):
        return (getattr(effect, 'min_dam', 0) + getattr(effect, 'max_dam', 0)) / 2.0

    seen = waiting = 0.0
    for castable in castable_spells(char_class, level, game_version):
        cost = castable.cost or 1
        seen += (sum(worth(effect) for effect in castable.hits)
                 + sum(worth(row[0]) for row in castable.delayed_plain or [])) / cost
        waiting += sum(worth(row[0]) for row in castable.waiting_plain or []) / cost
    return seen / (seen + waiting) if seen + waiting else None


# The door

def database_is_in_memory(database):
    """Whether a DATABASES entry is the in-memory sqlite the tuner needs."""
    return (database.get('ENGINE') == 'django.db.backends.sqlite3'
            and 'memory' in str(database.get('NAME') or '').lower())


def path_is_inside(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return os.path.commonpath([path, folder]) == folder


class DoorResult(object):
    """A solve through a door and what the tuner reads from the set."""

    def __init__(self, instance, ratios, **facts):
        self.instance = instance
        self.ratios = ratios
        self.set_ids = ()
        self.slots = {}
        self.totals = {}
        self.weights = {}
        self.proven = None
        self.seconds = None
        self.wall = None
        self.view = None
        self.credit = None
        self.power_share = None
        self.contributions = {}
        self.guard = None
        self.guarded = False
        self.infeasible = False
        self.notes = []
        self.__dict__.update(facts)

    @property
    def turn(self):
        return self.view.reader.full(self.view.worn) if self.view is not None else None

    @property
    def ehp(self):
        return effective_hp(self.totals) if self.totals else None

    def u_fit(self, lam):
        return fit_score(self.view, self.totals, lam) if self.view is not None else None

    def read(self, lam):
        if self.view is None:
            return None
        return read_ratios(self.view, self.totals, list(self.instance.elements), lam)

    def u_acc(self, lam):
        if self.credit is None:
            return None
        return math.log(self.credit.turn) + lam * math.log(self.credit.ehp)

    def evaluation(self):
        """What the acceptance reads: the credited score at both ends of lambda, the power share, the facts."""
        ends = SCENARIO_LAMBDA[self.instance.scenario]
        return {'valid': self.credit is not None and (self.proven is True or self.guarded), 'proven': self.proven,
                'T': self.credit.turn if self.credit else None, 'E': self.credit.ehp if self.credit else None,
                'u_acc': {end: self.u_acc(ends[end]) for end in ('lo', 'hi')}, 'pow_share': self.power_share,
                'seconds': self.seconds, 'set': list(self.set_ids)}


class DoorRunner(object):
    """Builds and solves instances through the site's doors on an in-memory test database."""

    def __init__(self, game_version):
        import django
        from django.conf import settings
        from django.contrib.auth.models import User
        from django.db import connection
        from django.test import RequestFactory
        from django.test.utils import setup_test_environment
        from django.utils import translation
        from chardata import fashion_action
        from chardata.solution_memory import EmptySolutionMemory
        from fashionistapulp.structure import get_structure, set_current_game_version
        django.setup()
        if not database_is_in_memory(settings.DATABASES['default']):
            raise RuntimeError('the tuner runs on an in-memory sqlite database only')
        setup_test_environment()
        self.connection = connection
        self.old_name = connection.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
        if 'memory' not in str(connection.settings_dict.get('NAME')).lower():
            raise RuntimeError('the test database is not in memory')
        self.game_version = game_version
        set_current_game_version(game_version)
        translation.activate('en')
        self.structure = get_structure(game_version)
        self.effect_table = load_effect_table(game_version)
        self.user = User.objects.create_user('tuner', 'tuner@example.invalid', 'tuner')
        request = RequestFactory().get('/')
        request.user = self.user
        request.game_version = game_version
        request.LANGUAGE_CODE = 'en'
        request.session = {}
        self.request = request
        self.retries = 0
        self._count_retries()
        self._memory = fashion_action.MEMORY
        fashion_action.MEMORY = EmptySolutionMemory()

    def _count_retries(self):
        from fashionistapulp.model import Model
        original = Model.run
        if getattr(original, 'tuner_counts_retries', False):
            return
        runner = self

        def run(model, retries=0, change_of=False, *args, **kwargs):
            if change_of:
                runner.retries += 1
            return original(model, retries, change_of, *args, **kwargs)
        run.tuner_counts_retries = True
        Model.run = run

    def close(self):
        from chardata import fashion_action
        from django.test.utils import teardown_test_environment
        fashion_action.MEMORY = self._memory
        self.connection.creation.destroy_test_db(self.old_name, verbosity=0)
        teardown_test_environment()

    def _build(self, instance, forbid, guarded):
        from chardata.coaching_view import create_build
        from chardata.lock_forbid import add_items_to_exclusions
        from chardata.min_stats import get_min_stats, set_min_stats
        from chardata.presets import STYLE_BY_KEY, apply_setup_choices
        style, priority = SCENARIO_DOOR[instance.scenario]
        if guarded:
            style, priority = None, GUARDED_PRIORITY[instance.scenario]
        boxes = set(instance.elements) | (set(STYLE_BY_KEY[style].aspects) if style else set())
        char = create_build(self.request, instance.char_class, GRID_LEVEL, set(boxes), self.game_version,
                            name='tuner %s' % instance_key(instance))
        apply_setup_choices(char, set(boxes), priority=priority, reset=True, set_minimums=False)
        if instance.minimums == 'meta':
            minimums = dict(get_min_stats(char))
            minimums.update(META_MINIMUMS)
            set_min_stats(char, minimums)
        if forbid:
            add_items_to_exclusions(char, sorted(forbid))
        return char

    def _solve(self, char, time_limit):
        from fashionistapulp import lpproblem
        from chardata.fashion_action import fashion
        previous = lpproblem.SOLVER.timeLimit
        lpproblem.SOLVER.timeLimit = time_limit
        retries = self.retries
        started = time.monotonic()
        try:
            response = fashion(self.request, char.id)
        finally:
            lpproblem.SOLVER.timeLimit = previous
        return (time.monotonic() - started, 'infeasible' in str(getattr(response, 'url', '')),
                self.retries - retries)

    def run(self, instance, ratios=None, forbid=(), time_limit=TIME_LIMIT, guarded=False):
        """DoorResult of the instance with `ratios` as its cell (the engine's weights when None)."""
        table = cell_table(instance.char_class, instance.elements, instance.scenario, ratios) if ratios else None
        with override_weight_table(self.game_version, table):
            char = self._build(instance, forbid, guarded)
            wall, infeasible, retries = self._solve(char, time_limit)
            result = DoorResult(instance, dict(ratios) if ratios else None, wall=wall, infeasible=infeasible,
                                guarded=guarded)
            if infeasible:
                result.notes.append('infeasible')
            else:
                self._read(char, result, retries)
        return result

    def _read(self, char, result, retries):
        from chardata.crit_curve import _set_view
        from chardata.presets import guard_facts
        from chardata.solution import get_solution, get_solver_facts
        from chardata.stats_weights import get_stats_weights
        from chardata.weapon_terms import stat_lines_value
        char.refresh_from_db()
        solution = get_solution(char)
        if solution is None:
            result.notes.append('no_solution')
            return
        result.weights = dict(get_stats_weights(char, persist=False))
        result.totals = dict(solution.get_stats_total())
        result.slots = {item.slot: item.id for item in solution.item_list if item.item_added}
        result.set_ids = tuple(sorted(set(result.slots.values())))
        proven, seconds, _pool = get_solver_facts(char.minimal_solution)
        result.proven = False if retries else proven
        result.seconds = seconds
        result.guard = guard_facts(char.minimal_solution)
        result.contributions = {item_id: stat_lines_value(self.structure.get_item_by_id(item_id), result.weights,
                                                          self.structure) for item_id in result.set_ids}
        result.view = _set_view(char, solution)
        if result.view is not None and result.view.worn is None:
            result.notes.append('no_weapon')
        result.credit = credited_parts(char, solution, self.effect_table)
        result.power_share = power_share(char, solution, self.effect_table)


def forbid_for(tier, engine_result):
    """The heaviest pieces of the first engine set that a tier takes away."""
    ranked = sorted(engine_result.contributions, key=lambda item_id: (-engine_result.contributions[item_id], item_id))
    return set(ranked[:TIER_FORBIDDEN[tier]])


# The loop

class Round(object):
    """One round of an instance: the ratios the door was fed, the set it gave and what was read from it."""

    def __init__(self, index, ratios, result, read, u_fit, changed, set_change=((), ())):
        self.index = index
        self.ratios = ratios
        self.result = result
        self.read = read
        self.u_fit = u_fit
        self.changed = changed
        self.set_change = set_change

    def record(self):
        result = self.result
        return {'round': self.index, 'u_fit': self.u_fit, 'T': result.turn if result.view is not None else None,
                'E': result.ehp, 'changed': self.changed, 'set': list(result.set_ids),
                'set_change': [list(self.set_change[0]), list(self.set_change[1])], 'proven': result.proven,
                'seconds': result.seconds, 'wall': result.wall,
                'u_acc': result.evaluation()['u_acc'], 'notes': list(result.notes),
                'read': dict(self.read.ratios) if self.read else None,
                'switched': sorted(self.read.switched) if self.read else []}


class TuneRun(object):
    """What the loop did on one instance."""

    def __init__(self, instance):
        self.instance = instance
        self.rounds = []
        self.dropped = []
        self.best = None
        self.converged = False
        self.stop = None

    @property
    def engine(self):
        return self.rounds[0].result if self.rounds else None

    @property
    def best_round(self):
        return self.rounds[self.best] if self.best is not None else None

    @property
    def usable(self):
        best = self.best_round
        return best is not None and best.result.proven is True

    def record(self):
        return {'instance': instance_key(self.instance), 'split': self.instance.split, 'best': self.best,
                'converged': self.converged, 'stop': self.stop, 'dropped': self.dropped,
                'rounds': [item.record() for item in self.rounds]}


def blend(current, read, index, unit):
    """The next ratios: Frank-Wolfe step 2 / (k + 2) towards the read, at most TRUST_FACTOR times either way.

    A change smaller than one unit of weight leaves the ratio as it was.
    """
    step = 2.0 / (index + 2)
    out = {}
    for stat, value in current.items():
        target = read.get(stat)
        if target is None or (value == 0 and stat in TABLE_STATS):
            out[stat] = value
            continue
        moved = value + step * (target - value)
        if value > 0:
            moved = min(max(moved, value / TRUST_FACTOR), value * TRUST_FACTOR)
        moved = max(moved, 0.0)
        out[stat] = value if abs(moved - value) * unit < 1 else moved
    shares = {stat: out[stat] for stat in SHARE_STATS if stat in out}
    if len(shares) == 2:
        out.update(clamp_shares(shares))
    return out


def _solve_proven(runner, instance, ratios, forbid, time_limit):
    """(result, dropped reason): an unproven solve is made again at twice the limit, then dropped."""
    result = runner.run(instance, ratios, forbid, time_limit)
    if result.infeasible:
        return None, 'infeasible'
    if result.proven is not True:
        result = runner.run(instance, ratios, forbid, time_limit * RETRY_FACTOR)
        if result.infeasible:
            return None, 'infeasible'
        if result.proven is not True:
            return None, 'unproven'
    return result, None


def tune_instance(runner, instance, start=None, max_rounds=MAX_ROUNDS, forbid=(), time_limit=TIME_LIMIT,
                  on_round=None):
    """TuneRun: round 0 on the engine's weights (or `start`), then up to max_rounds blended rounds, best kept."""
    from chardata.weight_table import SCENARIOS as _scenarios
    assert instance.scenario in _scenarios
    lam = SCENARIO_LAMBDA[instance.scenario]['fit']
    unit = unit_of(instance.elements, instance.scenario)
    run = TuneRun(instance)
    base = engine_ratios(instance.char_class, instance.elements, instance.scenario, runner.game_version)
    current = dict(start) if start else dict(base)
    fed = dict(start) if start else None
    seen = []
    previous = integer_weights(current, unit)
    for index in range(max_rounds + 1):
        result, reason = _solve_proven(runner, instance, fed, forbid, time_limit)
        if result is None:
            run.dropped.append({'round': index, 'reason': reason})
            run.stop = reason
            break
        read = result.read(lam)
        u_fit = result.u_fit(lam)
        if read is None or u_fit is None:
            run.dropped.append({'round': index, 'reason': 'no_turn'})
            run.stop = 'no_turn'
            break
        now = integer_weights(current, unit)
        changed = {stat: [previous[stat], now[stat]] for stat in now if now[stat] != previous[stat]}
        before = set(run.rounds[-1].result.set_ids) if run.rounds else set(result.set_ids)
        after = set(result.set_ids)
        item = Round(index, dict(current), result, read, u_fit, changed,
                     (sorted(after - before), sorted(before - after)))
        run.rounds.append(item)
        if on_round is not None:
            on_round(item)
        previous = now
        if result.set_ids in seen:
            run.converged, run.stop = True, 'repeat'
            break
        seen.append(result.set_ids)
        if index == max_rounds:
            run.stop = 'rounds'
            break
        following = blend(current, read.ratios, index, unit)
        if integer_weights(following, unit) == now:
            run.converged, run.stop = True, 'fixed'
            break
        current = following
        fed = dict(current)
    scored = [(item.u_fit, -item.index) for item in run.rounds]
    if scored:
        run.best = max(range(len(scored)), key=lambda position: scored[position])
    return run


# Pooling and acceptance

def _median(values):
    return statistics.median(values) if values else None


def _folds_disagree(first, second, engine):
    """Whether two fold values differ by more than FOLD_AGREEMENT or move opposite ways from the engine."""
    if first is None or second is None:
        return True
    low, high = sorted((first, second))
    if (high != low and low <= 0) or (low > 0 and high / low > FOLD_AGREEMENT):
        return True
    return (first - engine) * (second - engine) < 0


def _fold_values(runs, stat):
    """({instance key: ratio} of the usable runs, the median of each dev fold)."""
    values = {instance_key(run.instance): run.best_round.ratios.get(stat) for run in runs if run.usable
              and run.best_round.ratios.get(stat) is not None}
    folds = {}
    for split in DEV_SPLITS:
        picked = [run.best_round.ratios[stat] for run in runs if run.usable and run.instance.split == split
                  and stat in run.best_round.ratios]
        folds[split] = _median(picked)
    return values, folds


def _switched_runs(runs, stat):
    return sum(1 for run in runs if run.usable and stat in run.best_round.read.switched)


def pool_cell(runs, engine_ratios_, group=None, stamp=None):
    """{stat: entry} of one cell from its dev runs; a weak stat is read over the group's runs, else it keeps the engine.

    `group` is the dev runs of every cell sharing the class, the number of elements and the scenario.
    """
    unit = unit_of(runs[0].instance.elements, runs[0].instance.scenario) if runs else 1
    usable = [run for run in runs if run.usable]
    entries = {}
    for stat in sorted(engine_ratios_):
        engine = engine_ratios_[stat]
        values, folds = _fold_values(usable, stat)
        entry = {'builds': values, 'n': len(values), 'engine': engine, 'folds': [folds['dev_a'], folds['dev_b']],
                 'weak': False}
        if stamp:
            entry.update(stamp)
        if not values:
            entry.update(value=engine, spread=None, weak=True, reason='no_runs')
            entries[stat] = entry
            continue
        entry['spread'] = [min(values.values()), max(values.values())]
        value = _median(list(values.values()))
        reason = None
        if _switched_runs(usable, stat) > SWITCH_SHARE * len(usable):
            value, reason = engine, 'switch'
            entry['weak'] = True
        elif _folds_disagree(folds['dev_a'], folds['dev_b'], engine):
            pooled = _pooled_value(group, stat, engine) if group else None
            if pooled is None:
                value, reason = engine, 'folds'
                entry['weak'] = True
            else:
                value, reason = pooled, 'pooled'
        if not entry['weak']:
            low, high = BOUNDS[0] * engine, BOUNDS[1] * engine
            if value < low or value > high:
                value, reason = min(max(value, low), high), 'bound'
            if abs(value - engine) * unit < 1:
                value = engine
                reason = reason or 'unchanged'
        entry['value'] = value
        if reason:
            entry['reason'] = reason
        entries[stat] = entry
    return entries


def _pooled_value(group, stat, engine):
    """The median of a stat over a group's usable dev runs when its two folds agree, else None."""
    runs = [run for run in group if run.usable]
    if _switched_runs(runs, stat) > SWITCH_SHARE * len(runs):
        return None
    _values, folds = _fold_values(runs, stat)
    if _folds_disagree(folds['dev_a'], folds['dev_b'], engine):
        return None
    return _median([run.best_round.ratios[stat] for run in runs if stat in run.best_round.ratios])


def applied_ratios(entries):
    """{stat: ratio} the table would apply: the entries that are not weak and that moved."""
    return {stat: entry['value'] for stat, entry in entries.items()
            if not entry.get('weak') and entry['value'] != entry['engine']}


def _gains(pairs):
    """{end: table minus engine} of one instance, None when either side has no score."""
    out = {}
    for end in ('lo', 'hi'):
        engine, table = pairs['engine']['u_acc'][end], pairs['table']['u_acc'][end]
        out[end] = None if engine is None or table is None else table - engine
    return out


def _ceiling_holds(pairs):
    engine, table = pairs['engine']['pow_share'], pairs['table']['pow_share']
    if engine is None or table is None:
        return False
    return table <= max(CEILING_FACTOR * engine, engine + CEILING_MARGIN)


def accept_cell(value, dev, test, guarded, blind_share):
    """{'status': 'shipped' or 'engine', 'reason', ...} from the pooled entries and the evaluations.

    dev and test hold {'engine': evaluation, 'table': evaluation} per instance; guarded the same plus the guard facts,
    None when the scenario has no guarded door.
    """
    out = {'status': 'engine', 'reason': None, 'blind_share': blind_share}
    if blind_share is None or blind_share < BLIND_SHARE:
        out['reason'] = 'blind'
        return out
    if not applied_ratios(value):
        out['reason'] = 'no_change'
        return out
    valid = [pairs for pairs in dev if pairs['engine']['valid'] and pairs['table']['valid']]
    if len(valid) < MIN_DEV_RUNS:
        out['reason'] = 'dev_runs'
        return out
    dev_gains = [_gains(pairs) for pairs in valid]
    test_pairs = test if test and test['engine']['valid'] and test['table']['valid'] else None
    if test_pairs is None:
        out['reason'] = 'test_run'
        return out
    test_gain = _gains(test_pairs)
    median = {end: _median([gains[end] for gains in dev_gains]) for end in ('lo', 'hi')}
    out.update(u_acc_gain=median, test_gain=test_gain,
               pow_share={'engine': test_pairs['engine']['pow_share'], 'table': test_pairs['table']['pow_share']})
    if any(median[end] is None or median[end] <= 0 for end in median):
        out['reason'] = 'dev_gain'
        return out
    if any(test_gain[end] is None or test_gain[end] <= 0 for end in test_gain):
        out['reason'] = 'test_gain'
        return out
    if any(gain is not None and gain < -MAX_LOSS for gains in dev_gains + [test_gain] for gain in gains.values()):
        out['reason'] = 'loss'
        return out
    if not all(_ceiling_holds(pairs) for pairs in valid + [test_pairs]):
        out['reason'] = 'ceiling'
        return out
    if guarded is not None:
        facts = guarded['table'].get('guard') or {}
        if not guarded['engine']['valid'] or not guarded['table']['valid']:
            out['reason'] = 'guarded_run'
            return out
        if facts.get('fallback') or facts.get('short'):
            out['reason'] = 'guarded_floor'
            return out
        if any(gain is not None and gain < -MAX_LOSS for gain in _gains(guarded).values()):
            out['reason'] = 'guarded_loss'
            return out
    out['status'] = 'shipped'
    return out


# A cell and a group

def _evaluation(result):
    evaluation = result.evaluation()
    evaluation['guard'] = result.guard
    return evaluation


def tune_group(runner, cells, max_rounds=MAX_ROUNDS, time_limit=TIME_LIMIT, log=None):
    """The records of cells sharing class, number of elements and scenario: their dev runs are pooled together."""
    from chardata.stats_weights import MAX_STAT_WEIGHT
    version = runner.game_version
    records, tuned = [], []
    for cell in cells:
        share = visible_damage_share(cell.char_class, GRID_LEVEL, version)
        if share is None or share < BLIND_SHARE:
            records.append({'cell': cell_key(cell), 'status': 'engine', 'reason': 'blind', 'blind_share': share})
            continue
        started = time.monotonic()
        instances = instances_for(cell)
        first = tune_instance(runner, instances[0], max_rounds=max_rounds, time_limit=time_limit,
                              on_round=_logger(log, instances[0]))
        if first.engine is None:
            records.append({'cell': cell_key(cell), 'status': 'engine', 'reason': 'engine_run',
                            'blind_share': share, 'instances': [first.record()]})
            continue
        forbids = {tier: forbid_for(tier, first.engine) for tier in TIER_FORBIDDEN}
        runs = [first] + [tune_instance(runner, instance, max_rounds=max_rounds, forbid=forbids[instance.tier],
                                        time_limit=time_limit, on_round=_logger(log, instance))
                          for instance in instances[1:4]]
        tuned.append((cell, instances, runs, forbids, share, started))
    group = [run for _cell, _instances, runs, _forbids, _share, _started in tuned for run in runs]
    for cell, instances, runs, forbids, share, started in tuned:
        base = engine_ratios(cell.char_class, cell.elements, cell.scenario, version)
        stamp = {'data': _data_version(version), 'date': date.today().isoformat(), 'source': 'tune'}
        entries = pool_cell(runs, base, group, stamp)
        applied = applied_ratios(entries)
        dev = [{'engine': _evaluation(run.engine), 'table': _evaluation(run.best_round.result)}
               for run in runs if run.usable and run.engine is not None]
        test_instance = instances[4]
        test = None
        if applied:
            test_engine = runner.run(test_instance, None, forbids[test_instance.tier], time_limit)
            test_table = runner.run(test_instance, applied, forbids[test_instance.tier], time_limit)
            test = {'engine': _evaluation(test_engine), 'table': _evaluation(test_table)}
        guarded = None
        if applied and cell.scenario in GUARDED_PRIORITY:
            engine_result = runner.run(instances[0], None, (), time_limit, guarded=True)
            table_result = runner.run(instances[0], applied, (), time_limit, guarded=True)
            guarded = {'engine': _evaluation(engine_result), 'table': _evaluation(table_result)}
        verdict = accept_cell(entries, dev, test, guarded, share)
        unit = unit_of(cell.elements, cell.scenario)
        clamped = sorted(stat for stat, value in applied.items() if value * unit > MAX_STAT_WEIGHT)
        records.append(dict(verdict, cell=cell_key(cell), ratios=entries, applied=sorted(applied), clamped=clamped,
                            rounds=max((len(run.rounds) for run in runs), default=0),
                            converged=all(run.converged for run in runs),
                            u_fit_gain={instance_key(run.instance): _fit_gain(run) for run in runs},
                            notes=_notes(cell, runs), instances=[run.record() for run in runs],
                            test=test, guarded=guarded, seconds=time.monotonic() - started))
    return records


def _fit_gain(run):
    if not run.rounds or run.best is None:
        return None
    return run.rounds[run.best].u_fit - run.rounds[0].u_fit


def _notes(cell, runs):
    notes = ['bluff_rows'] if cell.char_class == 'Ecaflip' else []
    notes.extend(sorted({note for run in runs for item in run.rounds for note in item.result.notes}))
    return notes


def format_round(record):
    """One line for a round's record."""
    ends = record.get('u_acc') or {}

    def number(value, places=4):
        return 'none' if value is None else ('%%.%df' % places) % value
    return ('%s round %d U_fit %s U_acc lo %s hi %s T %s E %s proven %s %ss wall %ss set +%d -%d changed %s'
            % (record['instance'], record['round'], number(record['u_fit']), number(ends.get('lo')),
               number(ends.get('hi')), number(record['T'], 1), number(record['E'], 1), record['proven'],
               number(record['seconds'], 1), number(record['wall'], 1), len(record['set_change'][0]),
               len(record['set_change'][1]),
               json.dumps(record['changed'], sort_keys=True) if record['changed'] else '{}'))


def _logger(log, instance):
    if log is None:
        return None

    def on_round(item):
        log(dict(item.record(), instance=instance_key(instance)))
    return on_round


def _data_version(game_version):
    from chardata.data_versions import current_data_version
    return current_data_version(game_version)


# The run folder and the table file

def cell_path(out, record_or_key):
    key = record_or_key if isinstance(record_or_key, str) else record_or_key['cell']
    return os.path.join(out, 'cells', key.replace('/', '__') + '.json')


def write_record(out, record):
    os.makedirs(os.path.join(out, 'cells'), exist_ok=True)
    with open(cell_path(out, record), 'w', encoding='utf-8') as handle:
        json.dump(record, handle, sort_keys=True, default=_plain)


def read_records(out):
    folder = os.path.join(out, 'cells')
    records = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith('.json'):
            with open(os.path.join(folder, name), encoding='utf-8') as handle:
                records.append(json.load(handle))
    return records


def _plain(value):
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    return repr(value)


def file_sha1(path):
    digest = hashlib.sha1()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def game_data_sha1(game_version):
    from fashionistapulp.game_versions import get_game_version
    import fashionistapulp
    path = os.path.join(os.path.dirname(fashionistapulp.__file__), get_game_version(game_version).dump_file)
    return file_sha1(path) if os.path.isfile(path) else None


def repository_head():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=30,
                              cwd=os.path.dirname(os.path.abspath(__file__))).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def table_header(game_version, run_sha1, solver):
    from chardata.weight_table import engine_digest
    all_instances = [instance for cell in lot1_cells() for instance in instances_for(cell)]
    return {'generated': 'by tune_weights --ship; do not edit', 'game_version': game_version,
            'generator_version': GENERATOR_VERSION, 'engine_digest': engine_digest(game_version),
            'split_digest': split_digest(all_instances), 'game_data_sha1': game_data_sha1(game_version),
            'data_version': _data_version(game_version), 'repository_head': repository_head(),
            'solver': solver, 'lambda': {name: dict(ends, source='choice') for name, ends in SCENARIO_LAMBDA.items()},
            'run_sha1': run_sha1, 'created': date.today().isoformat()}


def ship_table(run_path, game_version, solver=None):
    """The table file's content from a run folder: its cells and the header."""
    records = read_records(run_path)
    digest = hashlib.sha1(json.dumps(records, sort_keys=True, default=_plain).encode('utf-8')).hexdigest()
    cells = {}
    for record in records:
        char_class, key, scenario, band = record['cell'].split('/')
        entry = {name: record[name] for name in ('status', 'reason', 'blind_share', 'rounds', 'converged',
                                                  'u_fit_gain', 'u_acc_gain', 'test_gain', 'pow_share', 'clamped',
                                                  'notes')
                 if name in record}
        entry['ratios'] = {stat: dict(ratio, source='tune/%s' % os.path.basename(os.path.normpath(run_path)))
                           for stat, ratio in (record.get('ratios') or {}).items()}
        cells.setdefault(char_class, {}).setdefault(key, {}).setdefault(scenario, {})[band] = entry
    return {'header': table_header(game_version, digest, solver or {}), 'cells': cells}


def cell_seconds(scenario, call_seconds=CALL_SECONDS, read_seconds=READ_SECONDS, rounds=EXPECTED_ROUNDS):
    """Seconds of one process on a cell: its dev instances, its test instance and, when it has one, the guarded pair."""
    per_round = call_seconds + read_seconds
    dev = (1 + rounds) * per_round * RESOLVE_MARGIN
    guarded = 2 * (2 * call_seconds + GUARDED_READ_SECONDS) if scenario in GUARDED_PRIORITY else 0
    return DEV_INSTANCES * dev + 2 * per_round + guarded


def projection(cells, processes, call_seconds=CALL_SECONDS, rounds=EXPECTED_ROUNDS):
    """{'cells', 'process_hours', 'wall_hours'} of running the cells on `processes` processes."""
    seconds = sum(cell_seconds(cell.scenario, call_seconds, rounds=rounds) for cell in cells)
    return {'cells': len(cells), 'process_hours': seconds / 3600.0, 'wall_hours': seconds / 3600.0 / max(processes, 1)}


def shard_stopped(records):
    """Whether more than SHARD_WEAK_LIMIT of the finished cells kept the engine, the blind classes left out."""
    finished = [record for record in records if record.get('reason') != 'blind']
    kept = [record for record in finished if record.get('status') != 'shipped']
    return len(finished) >= SHARD_MIN_CELLS and len(kept) > SHARD_WEAK_LIMIT * len(finished)


def repository_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_cell(text):
    """Cell of 'Class/str+int/scenario', the band being the grid's."""
    char_class, key, scenario = text.strip().split('/')[:3]
    elements = tuple(key.split('+'))
    if (char_class not in CHARACTER_CLASSES or elements not in grid_element_sets() or scenario not in SCENARIOS):
        raise ValueError('not a cell of the grid: %s' % text)
    return Cell(char_class, elements, scenario, BANDS[0])
