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
import re
import statistics
import subprocess
import time
from collections import Counter, namedtuple
from contextlib import contextmanager
from datetime import date
from functools import partial

from chardata.weapon_terms import CHARACTERISTIC_STEP
from chardata.weight_table import (BANDS, DAMAGE_STATS, GRID_LEVEL, RESIST_STATS, SCENARIOS, SHARE_STATS, TABLE_STATS,
                                   cell_table, element_key, engine_ratios, grid_element_sets, override_weight_table,
                                   unit_of)
from fashionistapulp.dofus_constants import CHARACTER_CLASSES, get_stat_maximum
from fashionistapulp.item_effects import (COST_ONLY_STATUSES, ELEMENT_KEYS, PLAYED_SHARE, is_valued,
                                          load_effect_table, played_characteristics)

logger = logging.getLogger(__name__)

#: bumped by hand when the reader, the score, the instances or the acceptance change
GENERATOR_VERSION = 5

STEP = CHARACTERISTIC_STEP
MAX_ROUNDS = 4
TIME_LIMIT = 90
RETRY_FACTOR = 2
#: the guard budget of the last attempt at a guarded solve that the retry left no comparison
LAST_ATTEMPT_BUDGET = 4
TRUST_FACTOR = 2
BOUNDS = (0.25, 4)
FOLD_AGREEMENT = 1.25
MIN_DEV_RUNS = 4
MAX_LOSS = 0.01
#: the gain a pair must beat for a dev median held at zero by identical sets to count as weak dominance
DOMINANCE_GAIN = 0.01
#: the range a table's set may give up against the engine's: the dev median and the test pair, no more
MAX_RANGE_LOSS = 1
CEILING_FACTOR = 1.5
CEILING_FLOOR = 0.20
BLIND_SHARE = 0.75
SPLIT_TOLERANCE = 0.10
SHARE_MARGIN = 0.02
#: a shard stops when more than this share of its finished cells could not be judged, from SHARD_MIN_CELLS of them
SHARD_WEAK_LIMIT = 0.25
SHARD_MIN_CELLS = 8
#: the reasons that say a cell was not judged at all: a cell that was judged and lost is no sign of a broken run
UNJUDGEABLE = ('engine_run', 'dev_runs', 'test_run', 'guarded_run')
#: the checks the dev pairs alone can fail, in the order they are read
DEV_CHECKS = ('dev_gain', 'panel_gain', 'loss', 'range', 'mp', 'ceiling')
#: the E1a gate: the shares of instances that converge and of fold pairs that agree, and the ceiling breaches allowed
E1A_CONVERGED = 0.70
E1A_FOLDS_AGREE = 0.75
E1A_CEILING_CELLS = 1
SWITCH_SHARE = 0.5
#: the stats no read prices cap-aware yet: they stay at the engine's weight, their read is recorded for later
HELD_STATS = ('ap',)
#: the stats the score cannot see, whose change between the engine set and the table set is recorded
BLIND_STATS = ('range', 'mp', 'init', 'lock', 'dodge')
#: the guard facts of a safeguarded solve that say it was not the comparison it stands for
GUARD_UNFIT = ('fallback', 'out_of_time')
#: what the guarded pair of a cell that stopped before the guarded check says it was dropped for
GUARDED_NOT_RUN = 'not_run'
#: the note of a cell whose spell rows are priced as if they all landed: its power is held to the elements played and
#: it keeps the engine's weights
BLUFF_NOTE = 'bluff_rows'
DRY_ROUNDS = 2
PROBE_RUNS = 3
#: for the projection of --plan: seconds of one door call, of the reads after it, and of the reads of a guarded pair
CALL_SECONDS = 18.7
READ_SECONDS = 2.5
GUARDED_READ_SECONDS = 3
#: the share of guarded solves expected to be made again on a longer budget, for the compute projection
GUARDED_RETRY_SHARE = 0.25
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
#: (tier, split) of the five instances of a cell
INSTANCE_PLAN = (('high', 'dev_a'), ('mid', 'dev_a'), ('rest', 'dev_b'), ('tail', 'dev_b'), ('low', 'test'))
DEV_SPLITS = ('dev_a', 'dev_b')
#: tier: (heaviest pieces of the first engine set it skips, pieces it forbids after them)
#: No two instances of a cell forbid the same pieces, so that none of them repeats another's solve.
TIER_FORBIDDEN = {'high': (0, 0), 'mid': (0, 3), 'rest': (6, 3), 'tail': (9, 3), 'low': (0, 6)}
SMOKE_INSTANCES = (('Iop', ('str',), 'glasscannon', 'high'), ('Cra', ('agi',), 'plain', 'high'))

#: the words of a reference text that says a spell summons something that hits
SUMMONS = re.compile(r'\bsummons?\b|\breplaces\b')
HITS = re.compile(r'\b(?:inflicts?|steals?)\b')

#: the equivalents of an effect-table item that reach the panel's turn
CREDITED_STATS = ELEMENT_KEYS + ('pow', 'dam', 'perspedam', 'ch', 'ap')
TURN_STATS = ('pow',) + DAMAGE_STATS + ('perspedam', 'perweadam')
LIFE_STATS = ('hp', 'vit')
#: the stats only a worn weapon can move
WEAPON_ONLY_STATS = ('perweadam',)
PERCENT_RESIST_KEYS = RESIST_STATS
#: stats that carry one measurement under several names: a fold pair is counted once per group
FOLD_GROUPS = (LIFE_STATS, RESIST_STATS)
#: every stat a cell can hold: the table's, and a duo's shares on its characteristics
READ_STATS = TABLE_STATS + SHARE_STATS

Cell = namedtuple('Cell', 'char_class elements scenario band')
Instance = namedtuple('Instance', 'char_class elements scenario band tier split')
Read = namedtuple('Read', 'ratios switched turn ehp g_char')
Credit = namedtuple('Credit', 'turn ehp')


def cell_key(cell):
    return '/'.join((cell.char_class, element_key(cell.elements), cell.scenario, cell.band))


def instance_key(instance):
    return '/'.join((cell_key(instance), instance.tier))


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
    return [Instance(cell.char_class, cell.elements, cell.scenario, cell.band, tier, split)
            for tier, split in INSTANCE_PLAN]


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
    """The whole weights the door sees: the ratios over the unit, rounded and clamped like the stored ones."""
    from chardata.stats_weights import MAX_STAT_WEIGHT as cap
    return {stat: max(-cap, min(cap, int(round(value * unit)))) for stat, value in ratios.items()}


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


def ap_gain(view):
    """The turn of a point of AP: the next one below the AP cap, the last one worn at the cap.

    The turn is read on the AP the set has. Above the cap a next point does not exist, so the secant goes backwards.
    """
    reader = view.reader
    cap = get_stat_maximum(reader.game_version, temporix=False).get('AP')
    here = reader.full(view.worn)
    if cap and reader.ap >= cap:
        return here - reader.cast(view.worn, None, reader.ap - 1)[0]
    return reader.cast(view.worn, None, reader.ap + 1)[0] - here


def share_bounds():
    """(lowest, highest) share of a duo's two: far enough apart that both stay played once the weights are whole."""
    low = 2 * PLAYED_SHARE / (1 + PLAYED_SHARE) + SHARE_MARGIN
    return low, 2 - low


def clamp_shares(shares):
    """A duo's shares kept inside share_bounds, still summing to 2."""
    if len(shares) != 2:
        return dict(shares)
    low, high = share_bounds()
    first, second = sorted(shares)
    value = min(max(shares[first], low), high)
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

    r_k = (g_k + lam * (T / E) * e_k) / g_char, with e the gain in effective HP of a point of the stat. A set with no
    weapon reads nothing for the stats only a weapon moves, so the blend leaves them where they are.
    """
    ehp = effective_hp(totals)
    hp = totals.get('hp', 0)
    turn = view.reader.full(view.worn)
    g_char = view.per_point(played)
    if not (turn > 0 and g_char > 0 and ehp > 0 and hp > 0):
        return None
    keys = TURN_STATS if view.worn is not None else tuple(key for key in TURN_STATS if key not in WEAPON_ONLY_STATS)
    gains, switched = read_gains(view, keys, STEP)
    gains['ap'] = ap_gain(view)
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


def _unpriced_summons(entries, priced_ids):
    """The reference spells that summon something that hits, when the damage data holds no rows for them."""
    return [entry for entry in entries
            if entry.get('id') not in priced_ids
            and (entry.get('summon_push') or (SUMMONS.search(_english(entry)) and HITS.search(_english(entry))))]


def _english(entry):
    return ((entry.get('description') or {}).get('en') or '').lower()


def visible_damage_share(char_class, level, game_version):
    """Share of the class's damage per AP that best_turn evaluates, None when the data cannot price all of it.

    The rest is what the data holds but the turn leaves out: bombs, traps and glyphs, which wait, and the spells the
    turn cannot cast. A summon that hits has no rows in the data, so the share is unknown.
    """
    from chardata.spell_buffs import get_damage_spells_for_version
    from chardata.spell_combo import ONLY_HITS_A_SUMMON, Castable, _chosen_level, castable_spells
    from chardata.spell_reference import get_spell_reference
    entries = (get_spell_reference(game_version) or {}).get(char_class)
    spells = (get_damage_spells_for_version(game_version) or {}).get(char_class) or []
    if not entries:
        return None
    if _unpriced_summons(entries, {spell.spell_id for spell in spells}):
        return None

    def worth(effect):
        return (getattr(effect, 'min_dam', 0) + getattr(effect, 'max_dam', 0)) / 2.0

    def per_ap(castable):
        """What a cast is worth per AP, as (landing now, waiting).

        Both read the best alternative, as best_turn does: the rows that wait for the same trigger are one per element
        or per stage, so only the best of them lands.
        """
        cost = castable.cost or 1
        best = max([sum(worth(effect) for effect in alternative)
                    for alternative in castable.plain_alternatives or castable.alternatives or []] or [0.0])
        by_trigger = {}
        for effect, trigger in castable.waiting_plain or []:
            by_trigger[trigger] = max(by_trigger.get(trigger, 0.0), worth(effect))
        return best / cost, sum(by_trigger.values()) / cost

    seen = waiting = 0.0
    evaluated = set()
    for castable in castable_spells(char_class, level, game_version):
        evaluated.add(castable.spell_id)
        landed, later = per_ap(castable)
        seen += landed
        waiting += later
    for spell in spells:
        if (spell.spell_id in evaluated or not spell.casting or level < spell.level_req[0]
                or spell.spell_id in (ONLY_HITS_A_SUMMON.get(game_version) or {})):
            continue
        landed, later = per_ap(Castable(spell, _chosen_level(None, spell, level), False))
        waiting += landed + later
    return seen / (seen + waiting) if seen + waiting else None


# The door

def database_is_in_memory(database):
    """Whether a DATABASES entry is the in-memory sqlite the tuner needs."""
    return (database.get('ENGINE') == 'django.db.backends.sqlite3'
            and 'memory' in str(database.get('NAME') or '').lower())


def path_is_inside(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    try:
        return os.path.commonpath([path, folder]) == folder
    except ValueError:
        # Another drive: the path cannot be under the folder
        return False


@contextmanager
def guard_budget(factor):
    """The wall clock of a guarded request, and of its balanced phase, multiplied by `factor` while the block runs."""
    from chardata import fashion_action
    saved = (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS)
    fashion_action.GUARD_BUDGET_SECONDS = saved[0] * factor
    fashion_action.BALANCED_SECONDS = saved[1] * factor
    try:
        yield
    finally:
        fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS = saved


def item_stat_sums(structure, item_ids):
    """{stat key: the sum of that stat over the items}: what a set brings before the character's own points."""
    sums = {}
    for item_id in item_ids:
        for stat_id, value in structure.get_item_by_id(item_id).stats:
            key = structure.get_stat_by_id(stat_id).key
            sums[key] = sums.get(key, 0) + value
    return sums


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
        self.panel_turn = None
        self.power_share = None
        self.contributions = {}
        self.item_sums = {}
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

    def u_panel(self, lam):
        """The score on the panel's turn alone, the effect-table credit left out: ln T + lam * ln E of the set."""
        if not (self.panel_turn and self.panel_turn > 0 and self.totals and self.ehp and self.ehp > 0):
            return None
        return math.log(self.panel_turn) + lam * math.log(self.ehp)

    @property
    def credit_turn(self):
        """What the effect table adds to the panel's turn on this set, None when either is unknown."""
        if self.credit is None or self.panel_turn is None:
            return None
        return self.credit.turn - self.panel_turn

    @property
    def judgeable(self):
        """Whether the solve is a comparison: proven, and a guarded one did not fall back or run out of time."""
        facts = self.guard or {}
        return self.proven is True and not (self.guarded and any(facts.get(name) for name in GUARD_UNFIT))

    def evaluation(self):
        """What the acceptance reads: the credited and the panel score at both ends of lambda, the power share, the
        facts, and the stats the score cannot see."""
        ends = SCENARIO_LAMBDA[self.instance.scenario]
        return {'valid': self.credit is not None and self.judgeable, 'proven': self.proven,
                'T': self.credit.turn if self.credit else None, 'E': self.credit.ehp if self.credit else None,
                'T_panel': self.panel_turn, 'credit': self.credit_turn,
                'u_acc': {end: self.u_acc(ends[end]) for end in ('lo', 'hi')},
                'u_panel': {end: self.u_panel(ends[end]) for end in ('lo', 'hi')}, 'pow_share': self.power_share,
                'stats': {name: self.totals.get(name, 0) for name in BLIND_STATS},
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
        from chardata.presets import STYLE_BY_KEY, apply_setup_choices
        style, priority = SCENARIO_DOOR[instance.scenario]
        if guarded:
            style, priority = None, GUARDED_PRIORITY[instance.scenario]
        boxes = set(instance.elements) | (set(STYLE_BY_KEY[style].aspects) if style else set())
        char = create_build(self.request, instance.char_class, GRID_LEVEL, set(boxes), self.game_version,
                            name='tuner %s' % instance_key(instance))
        apply_setup_choices(char, set(boxes), priority=priority, reset=True, set_minimums=False)
        if forbid:
            add_items_to_exclusions(char, sorted(forbid))
        return char

    def _solve(self, char, time_limit, budget_factor=1):
        from fashionistapulp import lpproblem
        from chardata.fashion_action import fashion
        previous = lpproblem.SOLVER.timeLimit
        lpproblem.SOLVER.timeLimit = time_limit
        retries = self.retries
        started = time.monotonic()
        try:
            with guard_budget(budget_factor):
                response = fashion(self.request, char.id)
        finally:
            lpproblem.SOLVER.timeLimit = previous
        return (time.monotonic() - started, 'infeasible' in str(getattr(response, 'url', '')),
                self.retries - retries)

    def run(self, instance, ratios=None, forbid=(), time_limit=TIME_LIMIT, guarded=False, budget_factor=1):
        """DoorResult of the instance with `ratios` as its cell (the engine's weights when None).

        `budget_factor` stretches the wall clock a guarded request shares between its solves.
        """
        table = cell_table(instance.char_class, instance.elements, instance.scenario, ratios) if ratios else None
        with override_weight_table(self.game_version, table):
            char = self._build(instance, forbid, guarded)
            wall, infeasible, retries = self._solve(char, time_limit, budget_factor)
            result = DoorResult(instance, dict(ratios) if ratios else None, wall=wall, infeasible=infeasible,
                                guarded=guarded)
            if infeasible:
                result.notes.append('infeasible')
            else:
                self._read(char, result, retries)
        return result

    def _read(self, char, result, retries):
        from chardata.crit_curve import _set_view
        from chardata.presets import _panel_turn, guard_facts
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
        result.item_sums = item_stat_sums(self.structure, result.slots.values())
        result.panel_turn = _panel_turn(char, solution)
        result.credit = credited_parts(char, solution, self.effect_table)
        result.power_share = power_share(char, solution, self.effect_table)


def forbid_for(tier, engine_result):
    """The pieces of the first engine set that a tier takes away, the set ranked by weight in the objective."""
    ranked = sorted(engine_result.contributions, key=lambda item_id: (-engine_result.contributions[item_id], item_id))
    skipped, count = TIER_FORBIDDEN[tier]
    return set(ranked[skipped:skipped + count])


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
        self.engine_ratios = {}
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


def blend(current, read, index, unit, switched=()):
    """The next ratios: Frank-Wolfe step 2 / (k + 2) towards the read, at most TRUST_FACTOR times either way.

    A change smaller than one unit of weight leaves the ratio as it was, and so does a stat whose raise changed the cast
    list: its gain was read on a turn that another cast list replaces.
    """
    step = 2.0 / (index + 2)
    out = {}
    for stat, value in current.items():
        target = read.get(stat)
        if target is None or stat in switched or (value == 0 and stat in TABLE_STATS):
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
    run.engine_ratios = dict(base)
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
        following = blend(current, read.ratios, index, unit, set(read.switched) | set(HELD_STATS))
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


def _held_read(usable, stat):
    """What the runs read for a held stat, kept for the day a read can price it: {'builds': per run, 'median'}."""
    builds = {instance_key(run.instance): run.best_round.read.ratios[stat] for run in usable
              if run.best_round.read is not None and run.best_round.read.ratios.get(stat) is not None}
    return {'builds': builds, 'median': _median(list(builds.values()))}


def _group_key(instance):
    """[class, number of elements, scenario]: the cells whose dev runs are pooled together, as groups_of keys them."""
    return [instance.char_class, len(instance.elements), instance.scenario]


def _pool_stat(stat, engine, usable, group, unit, stamp, limits=None):
    """The entry of one stat; `limits` is (lowest, highest) in place of the bounds around the engine value."""
    values, folds = _fold_values(usable, stat)
    entry = {'builds': values, 'n': len(values), 'engine': engine, 'folds': [folds['dev_a'], folds['dev_b']],
             'weak': False}
    if limits:
        entry['limits'] = list(limits)
    if stamp:
        entry.update(stamp)
    if stat in HELD_STATS:
        entry.update(value=engine, spread=[min(values.values()), max(values.values())] if values else None,
                     weak=True, reason='held', read=_held_read(usable, stat))
        return entry
    if not values:
        entry.update(value=engine, spread=None, weak=True, reason='no_runs')
        return entry
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
            entry.update(pooled=True, group=_group_key(usable[0].instance))
    if not entry['weak']:
        low, high = limits or (BOUNDS[0] * engine, BOUNDS[1] * engine)
        if value < low or value > high:
            value, reason = min(max(value, low), high), 'bound'
        if abs(value - engine) * unit < 1:
            value = engine
            reason = reason or 'unchanged'
    entry['value'] = value
    if reason:
        entry['reason'] = reason
    return entry


def _tie_shares(head, tail):
    """A duo's two shares are one measure: the first element's entry sets the second's, so that they sum to 2."""
    tail['value'] = 2 - head['value']
    tail['weak'] = head['weak']
    for name in ('reason', 'pooled', 'group'):
        if name in head:
            tail[name] = head[name]
        else:
            tail.pop(name, None)


def power_limits(engine, count):
    """(lowest, highest) ratio of power on a cell whose spell rows are priced as if they all landed.

    A point of power is worth the played characteristic's point once per played element, so no more than `count` times
    it. A cell whose engine weight is above that keeps its engine weight as the highest.
    """
    return BOUNDS[0] * engine, max(min(BOUNDS[1] * engine, count), engine)


def pool_cell(runs, engine_ratios_, group=None, stamp=None, notes=()):
    """{stat: entry} of one cell from its dev runs; a weak stat is read over the group's runs, else it keeps the engine.

    `group` is the dev runs of every cell sharing the class, the number of elements and the scenario. A duo's shares
    are pooled as one stat, the first element's, and the other takes the rest of 2. On a cell with the bluff note
    power is held to the number of played elements.
    """
    unit = unit_of(runs[0].instance.elements, runs[0].instance.scenario) if runs else 1
    usable = [run for run in runs if run.usable]
    pair = [stat for stat in SHARE_STATS if stat in engine_ratios_]
    entries = {}
    for stat in sorted(engine_ratios_):
        limits = share_bounds() if len(pair) == 2 and stat in pair else None
        if stat == 'pow' and BLUFF_NOTE in notes and runs:
            limits = power_limits(engine_ratios_[stat], len(runs[0].instance.elements))
        entries[stat] = _pool_stat(stat, engine_ratios_[stat], usable, group, unit, stamp, limits)
    if len(pair) == 2:
        _tie_shares(entries[pair[0]], entries[pair[1]])
    return entries


def _over_engine(run, stat):
    """A run's ratio of a stat over the engine's ratio in its own cell, None where that cell weighs it at zero."""
    engine = run.engine_ratios.get(stat)
    value = run.best_round.ratios.get(stat)
    if not engine or value is None:
        return None
    return value / engine


def _sets_the_pair(run, stat):
    """Whether a stat is no share, or the share that sets its duo's pair: the first element's."""
    return stat not in SHARE_STATS or run.instance.elements[0] == stat


def _pooled_value(group, stat, engine):
    """The group's median move of a stat, applied to this cell's engine weight, when its two folds agree, else None.

    Only the runs of cells that weigh the stat count, so a cell that plays another element does not pull it to zero.
    """
    runs = [run for run in group if run.usable and _over_engine(run, stat) is not None and _sets_the_pair(run, stat)]
    if not runs or _switched_runs(runs, stat) > SWITCH_SHARE * len(runs):
        return None
    moves = {split: [_over_engine(run, stat) for run in runs if run.instance.split == split] for split in DEV_SPLITS}
    if _folds_disagree(_median(moves['dev_a']), _median(moves['dev_b']), 1.0):
        return None
    return _median(moves['dev_a'] + moves['dev_b']) * engine


def applied_ratios(entries):
    """{stat: ratio} the table would apply: the entries that are not weak and that moved."""
    return {stat: entry['value'] for stat, entry in entries.items()
            if not entry.get('weak') and entry['value'] != entry['engine']}


def owned_stats(entries):
    """The stats the table writes: the entries of a table stat that are not weak."""
    return sorted(stat for stat, entry in entries.items() if stat in TABLE_STATS and not entry.get('weak'))


def numeraire_factor(entries, engine, sums):
    """What the engine's high set is worth over what it is worth under the pooled prices, kept as a diagnostic.

    Every ratio is read against the played characteristic, which is in no basket, so the factor is no correction: the
    pooled prices are already in that numeraire and none is rescaled. The record is {'factor', 'owned', 'engine_value',
    'table_value'}, over the owned stats; the factor is 1 when nothing is applied or a value is not positive.
    """
    owned = owned_stats(entries)
    record = {'factor': 1.0, 'owned': owned, 'engine_value': None, 'table_value': None}
    if not sums or not owned or not applied_ratios(entries):
        return record
    record['engine_value'] = sum(engine[stat] * sums.get(stat, 0) for stat in owned)
    record['table_value'] = sum(entries[stat]['value'] * sums.get(stat, 0) for stat in owned)
    if record['engine_value'] > 0 and record['table_value'] > 0:
        record['factor'] = record['engine_value'] / record['table_value']
    return record


def _damp(entry, unit):
    """Moves an applied entry to the geometric midpoint of the engine's ratio and its pooled one, keeping the pooled
    value as `full`; a move of less than a unit of weight at the midpoint is dropped, as in the pooling."""
    entry['full'] = entry['value']
    half = math.sqrt(entry['engine'] * entry['value'])
    if abs(half - entry['engine']) * unit < 1:
        entry['value'], entry['reason'] = entry['engine'], 'unchanged'
    else:
        entry['value'], entry['reason'] = half, 'damped'


def damped_entries(entries, unit):
    """The entries of a cell with each applied stat halfway to the engine's ratio, in the geometric sense.

    A duo's first share goes to the midpoint and the second takes the rest of 2, as the pooling ties them. The entries
    nothing applied are as they were, and `entries` is not changed.
    """
    damped = {stat: dict(entry) for stat, entry in entries.items()}
    applied = applied_ratios(entries)
    shares = [stat for stat in SHARE_STATS if stat in entries]
    if len(shares) == 2:
        if shares[0] in applied:
            _damp(damped[shares[0]], unit)
            damped[shares[1]]['full'] = entries[shares[1]]['value']
            _tie_shares(damped[shares[0]], damped[shares[1]])
    else:
        shares = []
    for stat in applied:
        if stat not in shares:
            _damp(damped[stat], unit)
    return damped


def _gains(pairs, score='u_acc'):
    """{end: table minus engine} of one instance, None when either side has no score."""
    out = {}
    for end in ('lo', 'hi'):
        engine = (pairs['engine'].get(score) or {}).get(end)
        table = (pairs['table'].get(score) or {}).get(end)
        out[end] = None if engine is None or table is None else table - engine
    return out


def _ceiling_holds(pairs):
    """Whether the table's set keeps its power share under max(1.5 x the engine's, 0.20)."""
    engine, table = pairs['engine']['pow_share'], pairs['table']['pow_share']
    if engine is None or table is None:
        return False
    return table <= max(CEILING_FACTOR * engine, CEILING_FLOOR)


def _stat_deltas(pairs, stat):
    """Table minus engine of a stat the score cannot see, one per pair, None where either side did not report it."""
    out = []
    for pair in pairs:
        engine = (pair['engine'].get('stats') or {}).get(stat)
        table = (pair['table'].get('stats') or {}).get(stat)
        out.append(None if engine is None or table is None else table - engine)
    return out


def _dev_range(valid):
    """The median change of range over the dev pairs, None when a pair did not report it."""
    deltas = _stat_deltas(valid, 'range')
    return None if None in deltas else _median(deltas)


def _range_kept(delta):
    return delta is not None and delta >= -MAX_RANGE_LOSS


def _mp_kept(deltas):
    return all(delta == 0 for delta in deltas)


def _guard_unfit(evaluation):
    """The guard facts of a guarded solve that say it is no comparison, [] when it is one or has no guard."""
    facts = evaluation.get('guard') or {}
    return [name for name in GUARD_UNFIT if facts.get(name)]


def _median_gains(gains_per_pair):
    """{end: median over the pairs}, an end a pair has no gain at being left out."""
    return {end: _median([gains[end] for gains in gains_per_pair if gains[end] is not None]) for end in ('lo', 'hi')}


def _gain_missing(gains):
    return any(gains[end] is None or gains[end] <= 0 for end in gains)


def _same_set(pairs):
    """Whether the table's set of a pair is the engine's own, so that the two cannot differ in score."""
    engine = pairs['engine'].get('set')
    return bool(engine) and engine == pairs['table'].get('set')


def _dev_gain_missing(valid, dev_gains, median):
    """Whether the dev median fails to gain at one end, weak dominance being read where it is held at zero.

    A median of exactly zero, where every pair that gains exactly zero at that end has the engine's own set, passes
    the end when no pair loses more than MAX_LOSS at either and a pair gains more than DOMINANCE_GAIN at this one.
    """
    for end, gain in median.items():
        if gain is not None and gain > 0:
            continue
        zero = [pairs for pairs, gains in zip(valid, dev_gains) if gains[end] == 0]
        if (gain != 0 or not zero or not all(_same_set(pairs) for pairs in zero) or _loses(dev_gains)
                or not any(gains[end] is not None and gains[end] > DOMINANCE_GAIN for gains in dev_gains)):
            return True
    return False


def _loses(gains_per_pair):
    return any(gain is not None and gain < -MAX_LOSS for gains in gains_per_pair for gain in gains.values())


def dev_failure(dev):
    """The first check on the dev pairs alone that a step fails, in the order accept_cell reads them: 'dev_runs' when
    fewer than MIN_DEV_RUNS pairs are comparisons, one of DEV_CHECKS, or None when it passes them all.

    The test pair is not read, so that a step can be chosen without it.
    """
    valid = _usable_pairs(dev)
    if len(valid) < MIN_DEV_RUNS:
        return 'dev_runs'
    dev_gains = [_gains(pairs) for pairs in valid]
    if _dev_gain_missing(valid, dev_gains, _median_gains(dev_gains)):
        return 'dev_gain'
    if any(gain is None or gain < 0 for gain in _median_gains([_gains(pairs, 'u_panel') for pairs in valid]).values()):
        return 'panel_gain'
    if _loses(dev_gains):
        return 'loss'
    if not _range_kept(_dev_range(valid)):
        return 'range'
    if not _mp_kept(_stat_deltas(valid, 'mp')):
        return 'mp'
    if not all(_ceiling_holds(pairs) for pairs in valid):
        return 'ceiling'
    return None


def accept_cell(value, dev, test, guarded, blind_share, notes=()):
    """{'status': 'shipped' or 'engine', 'reason', ...} from the pooled entries and the evaluations.

    dev and test hold {'engine': evaluation, 'table': evaluation} per instance; guarded the same plus the guard facts,
    None when the scenario has no guarded door, or a function that makes the pair, which is called only when the cell
    reaches the guarded check and whose pair the verdict then holds under 'guarded'. The table's sets must keep the
    engine's range (the median of the dev pairs and the test pair give up at most MAX_RANGE_LOSS) and its MP (no pair
    changes it), which no score sees, and the test pair must hold on the panel's turn alone as the dev median does. A
    cell with the bluff note passes every check and still keeps the engine's weights: its spell rows are priced as if
    they all landed, which no first-hand source has settled.
    """
    out = {'status': 'engine', 'reason': None, 'blind_share': blind_share}
    if blind_share is None or blind_share < BLIND_SHARE:
        out['reason'] = 'blind'
        return out
    if not applied_ratios(value):
        out['reason'] = 'no_change'
        return out
    valid = _usable_pairs(dev)
    if len(valid) < MIN_DEV_RUNS:
        out['reason'] = 'dev_runs'
        return out
    dev_gains = [_gains(pairs) for pairs in valid]
    test_pairs = test if test and test['engine']['valid'] and test['table']['valid'] else None
    if test_pairs is None:
        out['reason'] = 'test_run'
        return out
    test_gain = _gains(test_pairs)
    test_panel = _gains(test_pairs, 'u_panel')
    median = _median_gains(dev_gains)
    panel = _median_gains([_gains(pairs, 'u_panel') for pairs in valid])
    range_delta = {'dev_median': _dev_range(valid), 'test': _stat_deltas([test_pairs], 'range')[0]}
    mp_delta = {'dev': _stat_deltas(valid, 'mp'), 'test': _stat_deltas([test_pairs], 'mp')[0]}
    out.update(u_acc_gain=median, panel_gain=panel, test_gain=test_gain, test_panel_gain=test_panel,
               range_delta=range_delta, mp_delta=mp_delta,
               pow_share={'engine': test_pairs['engine']['pow_share'], 'table': test_pairs['table']['pow_share']})
    if _dev_gain_missing(valid, dev_gains, median):
        out['reason'] = 'dev_gain'
        return out
    if _gain_missing(median):
        out['weak_dominance'] = True
    if any(panel[end] is None or panel[end] < 0 for end in panel):
        out['reason'] = 'panel_gain'
        return out
    if any(test_panel[end] is None or test_panel[end] < -MAX_LOSS for end in test_panel):
        out['reason'] = 'test_panel'
        return out
    if _gain_missing(test_gain):
        out['reason'] = 'test_gain'
        return out
    if _loses(dev_gains + [test_gain]):
        out['reason'] = 'loss'
        return out
    if not (_range_kept(range_delta['dev_median']) and _range_kept(range_delta['test'])):
        out['reason'] = 'range'
        return out
    if not _mp_kept(mp_delta['dev'] + [mp_delta['test']]):
        out['reason'] = 'mp'
        return out
    if not all(_ceiling_holds(pairs) for pairs in valid + [test_pairs]):
        out['reason'] = 'ceiling'
        return out
    if callable(guarded):
        guarded = out['guarded'] = guarded()
    if guarded is not None:
        facts = guarded['table'].get('guard') or {}
        if (not guarded['engine']['valid'] or not guarded['table']['valid'] or _guard_unfit(guarded['engine'])
                or _guard_unfit(guarded['table'])):
            out['reason'] = 'guarded_run'
            return out
        if facts.get('short'):
            out['reason'] = 'guarded_floor'
            return out
        if any(gain is not None and gain < -MAX_LOSS for gain in _gains(guarded).values()):
            out['reason'] = 'guarded_loss'
            return out
    if BLUFF_NOTE in notes:
        out['reason'] = BLUFF_NOTE
        return out
    out['status'] = 'shipped'
    return out


# A cell and a group

def _evaluation(result, dropped=None):
    """The evaluation of a door result; a solve that was dropped gives an invalid one that names why."""
    if result is None:
        return {'valid': False, 'dropped': dropped}
    evaluation = result.evaluation()
    evaluation['guard'] = result.guard
    return evaluation


def _difference(table, engine):
    return None if table is None or engine is None else table - engine


def _delta(engine, table):
    """Table minus engine: the credited turn, the panel turn, the effect credit and the stats the score cannot see."""
    if engine.get('T') is None or table.get('T') is None:
        return None
    return {'T': table['T'] - engine['T'], 'T_panel': _difference(table.get('T_panel'), engine.get('T_panel')),
            'credit': _difference(table.get('credit'), engine.get('credit')),
            'stats': {name: table['stats'][name] - engine['stats'][name] for name in BLIND_STATS}}


def _pair(engine, table, dropped=None):
    """{'engine', 'table', 'delta'}: the evaluations of the two solves of one instance and what the table changed."""
    pair = {'engine': _evaluation(engine, dropped), 'table': _evaluation(table, dropped)}
    pair['delta'] = _delta(pair['engine'], pair['table'])
    return pair


def guarded_not_run():
    """The guarded pair of a cell that stopped before the guarded check: neither solve was made, so none compares."""
    return _pair(None, None, GUARDED_NOT_RUN)


def symmetric_forbids(engine_high, table_high):
    """{tier: the pieces both sides of a pair give up}: the tier's cut of the engine's high set and of the table's."""
    return {tier: forbid_for(tier, engine_high) | forbid_for(tier, table_high) for tier in TIER_FORBIDDEN}


def _dev_pairs(runner, runs, applied, time_limit):
    """(pairs, forbids): the dev instances solved on the engine's weights and on the cell's, with the same pieces taken
    away from both sides.

    The table's high set is solved first; each tier then loses its cut of that set as well as of the engine's, so that
    neither side keeps a piece the other was denied. The rounds of a run only propose values: what the acceptance reads
    are these solves, so that the weights it judges are the ones that would ship.
    """
    runs = [run for run in runs if run.engine is not None]
    head = runs[0]
    table_high, reason = _solve_proven(runner, head.instance, applied, (), time_limit)
    pairs = [_pair(head.engine, table_high, reason)]
    if table_high is None:
        return pairs, {}
    forbids = symmetric_forbids(head.engine, table_high)
    for run in runs[1:]:
        tier = run.instance.tier
        engine, reason = run.engine, None
        if forbids[tier] != forbid_for(tier, head.engine):
            engine, reason = _solve_proven(runner, run.instance, None, forbids[tier], time_limit)
        table = None
        if engine is not None:
            table, reason = _solve_proven(runner, run.instance, applied, forbids[tier], time_limit)
        pairs.append(_pair(engine, table, reason))
    return pairs, forbids


def _damped_dev_pairs(runner, runs, pairs, applied, forbids, time_limit):
    """The dev pairs of a damped step: the engine sides and the forbidden pieces of the full step's pairs are kept, and
    only the table sides are solved again, on the damped ratios."""
    runs = [run for run in runs if run.engine is not None]
    out = []
    for run, pair in zip(runs, pairs):
        if not pair['engine']['valid']:
            out.append(pair)
            continue
        table, reason = _solve_proven(runner, run.instance, applied, forbids[run.instance.tier], time_limit)
        damped = {'engine': pair['engine'], 'table': _evaluation(table, reason)}
        damped['delta'] = _delta(damped['engine'], damped['table'])
        out.append(damped)
    return out


def _dev_reading(dev, applied):
    """What the dev pairs of a step said: the check they failed (None when none), the ratios applied and the medians."""
    valid = _usable_pairs(dev)
    reading = {'failure': dev_failure(dev), 'applied': dict(applied), 'pairs': len(valid)}
    if valid:
        reading.update(u_acc_gain=_median_gains([_gains(pairs) for pairs in valid]),
                       panel_gain=_median_gains([_gains(pairs, 'u_panel') for pairs in valid]),
                       range_delta=_dev_range(valid))
    return reading


def _test_pair(runner, instance, applied, forbid, time_limit):
    return _pair(runner.run(instance, None, forbid, time_limit), runner.run(instance, applied, forbid, time_limit))


def _guarded_fit(result):
    return result.infeasible or (result.credit is not None and result.judgeable)


def _guarded_solve(runner, instance, ratios, time_limit):
    """A guarded solve, made once more on a budget of twice the time when it ran short, fell back or ran out of time,
    and a last time on LAST_ATTEMPT_BUDGET times the budget, with the limit of the retry, when that is no comparison."""
    result = runner.run(instance, ratios, (), time_limit, guarded=True)
    if _guarded_fit(result):
        return result
    result = runner.run(instance, ratios, (), time_limit * RETRY_FACTOR, guarded=True, budget_factor=RETRY_FACTOR)
    if _guarded_fit(result):
        return result
    return runner.run(instance, ratios, (), time_limit * RETRY_FACTOR, guarded=True,
                      budget_factor=LAST_ATTEMPT_BUDGET)


def _guarded_pair(runner, instance, applied, time_limit):
    return _pair(_guarded_solve(runner, instance, None, time_limit),
                 _guarded_solve(runner, instance, applied, time_limit))


def _usable_pairs(pairs):
    return [pair for pair in pairs if pair['engine']['valid'] and pair['table']['valid']]


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
        tuned.append((cell, instances, runs, share, started))
    group = [run for _cell, _instances, runs, _share, _started in tuned for run in runs]
    for cell, instances, runs, share, started in tuned:
        base = engine_ratios(cell.char_class, cell.elements, cell.scenario, version)
        unit = unit_of(cell.elements, cell.scenario)
        stamp = {'data': _data_version(version), 'date': date.today().isoformat(), 'source': 'tune'}
        notes = _notes(cell, runs)
        entries = pool_cell(runs, base, group, stamp, notes)
        applied = applied_ratios(entries)
        dev, symmetric = _dev_pairs(runner, runs, applied, time_limit) if applied else ([], {})
        step, fallback = 'full', None
        failure = dev_failure(dev) if applied else None
        if failure in DEV_CHECKS and BLUFF_NOTE not in notes:
            # the step is chosen on the dev pairs alone; the test pair is solved once, for the step chosen
            damped = damped_entries(entries, unit)
            damped_applied = applied_ratios(damped)
            fallback = {'trigger': failure, 'chosen': 'full', 'full': dict(_dev_reading(dev, applied), dev=dev),
                        'damped': None}
            if damped_applied:
                damped_dev = _damped_dev_pairs(runner, runs, dev, damped_applied, symmetric, time_limit)
                fallback['damped'] = dict(_dev_reading(damped_dev, damped_applied), dev=damped_dev)
                if fallback['damped']['failure'] is None:
                    step, fallback['chosen'] = 'damped', 'damped'
                    entries, applied, dev = damped, damped_applied, damped_dev
        numeraire = numeraire_factor(entries, base, runs[0].engine.item_sums)
        test = make_guarded = None
        if len(_usable_pairs(dev)) >= MIN_DEV_RUNS:
            test = _test_pair(runner, instances[4], applied, symmetric[instances[4].tier], time_limit)
            if cell.scenario in GUARDED_PRIORITY:
                make_guarded = partial(_guarded_pair, runner, instances[0], applied, time_limit)
        verdict = accept_cell(entries, dev, test, make_guarded, share, notes)
        guarded = verdict.pop('guarded', guarded_not_run() if cell.scenario in GUARDED_PRIORITY else None)
        clamped = sorted(stat for stat, value in applied.items() if value * unit > MAX_STAT_WEIGHT)
        records.append(dict(verdict, cell=cell_key(cell), ratios=entries, applied=sorted(applied), clamped=clamped,
                            step=step, fallback=fallback, numeraire=numeraire,
                            rounds=max((len(run.rounds) for run in runs), default=0),
                            converged=all(run.converged for run in runs),
                            u_fit_gain={instance_key(run.instance): _fit_gain(run) for run in runs},
                            notes=notes, instances=[run.record() for run in runs], dev=dev, test=test,
                            guarded=guarded, forbids={tier: sorted(ids) for tier, ids in symmetric.items()},
                            seconds=time.monotonic() - started))
    return records


def _fit_gain(run):
    if not run.rounds or run.best is None:
        return None
    return run.rounds[run.best].u_fit - run.rounds[0].u_fit


def _repeated_sets(runs):
    """How many dev runs gave, on the engine's weights, a set another dev run had already given."""
    sets = [run.engine.set_ids for run in runs if run.engine is not None]
    return len(sets) - len(set(sets))


def _notes(cell, runs):
    notes = ['bluff_rows'] if cell.char_class == 'Ecaflip' else []
    if _repeated_sets(runs):
        notes.append('repeated_dev_sets')
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


def solver_facts(time_limit):
    """The solver settings of a run: the limit of one solve and the threads the solver was given."""
    from fashionistapulp import lpproblem
    solver = lpproblem.SOLVER
    return {'name': type(solver).__name__, 'time_limit': time_limit, 'threads': getattr(solver, 'threads', None)}


def read_meta(run_path):
    """The options file of a run folder, {} when it has none."""
    try:
        with open(os.path.join(run_path, 'run.json'), encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def ship_table(run_path, game_version, solver=None):
    """The table file's content from a run folder: its cells and the header, with the solver the run was made on."""
    records = read_records(run_path)
    if solver is None:
        solver = read_meta(run_path).get('solver')
    digest = hashlib.sha1(json.dumps(records, sort_keys=True, default=_plain).encode('utf-8')).hexdigest()
    cells = {}
    for record in records:
        char_class, key, scenario, band = record['cell'].split('/')
        entry = {name: record[name] for name in ('status', 'reason', 'blind_share', 'rounds', 'converged',
                                                  'u_fit_gain', 'u_acc_gain', 'panel_gain', 'test_gain',
                                                  'test_panel_gain', 'range_delta', 'mp_delta', 'pow_share',
                                                  'clamped', 'step', 'numeraire', 'notes', 'weak_dominance')
                 if name in record}
        entry['ratios'] = {stat: dict(ratio, source='tune/%s' % os.path.basename(os.path.normpath(run_path)))
                           for stat, ratio in (record.get('ratios') or {}).items()}
        cells.setdefault(char_class, {}).setdefault(key, {}).setdefault(scenario, {})[band] = entry
    return {'header': table_header(game_version, digest, solver or {}), 'cells': cells}


def cell_seconds(scenario, call_seconds=CALL_SECONDS, read_seconds=READ_SECONDS, rounds=EXPECTED_ROUNDS):
    """Seconds of one process on a cell: its dev instances, their solves on the pooled weights and the engine's again
    under the symmetric forbids, its test instance and, when it has one, the guarded pair with the share of them made
    again."""
    per_round = call_seconds + read_seconds
    dev = (1 + rounds) * per_round * RESOLVE_MARGIN
    pooled = 2 * per_round * RESOLVE_MARGIN
    guarded = 0
    if scenario in GUARDED_PRIORITY:
        guarded = 2 * (2 * call_seconds + GUARDED_READ_SECONDS) * (1 + RETRY_FACTOR * GUARDED_RETRY_SHARE)
    return DEV_INSTANCES * (dev + pooled) - per_round * RESOLVE_MARGIN + 2 * per_round + guarded


def projection(cells, processes, call_seconds=CALL_SECONDS, rounds=EXPECTED_ROUNDS):
    """{'cells', 'process_hours', 'wall_hours'} of running the cells on `processes` processes."""
    seconds = sum(cell_seconds(cell.scenario, call_seconds, rounds=rounds) for cell in cells)
    return {'cells': len(cells), 'process_hours': seconds / 3600.0, 'wall_hours': seconds / 3600.0 / max(processes, 1)}


def shard_stopped(records):
    """Whether more than SHARD_WEAK_LIMIT of the finished cells could not be judged, the blind classes left out.

    A cell that was judged and kept the engine's weights is the tuner doing its job, not a broken run.
    """
    finished = [record for record in records if record.get('reason') != 'blind']
    unjudged = [record for record in finished if record.get('reason') in UNJUDGEABLE]
    return len(finished) >= SHARD_MIN_CELLS and len(unjudged) > SHARD_WEAK_LIMIT * len(finished)


def _cell_gained(record):
    """Whether a cell gained on the credited score at both ends of lambda, on its dev median and on the test."""
    gains = list((record.get('u_acc_gain') or {}).values()) + list((record.get('test_gain') or {}).values())
    return len(gains) == 4 and all(gain is not None and gain > 0 for gain in gains)


def _fold_agreements(record):
    """One bool per distinct fold pair of a cell: whether its two folds agree.

    A stat both folds weigh at zero is left out, and the stats of a group that carry the same pair (the five
    resistances, hp and vit) are one measure and count once.
    """
    agreements = {}
    for stat, entry in sorted((record.get('ratios') or {}).items()):
        first, second = entry.get('folds') or (None, None)
        if first == 0 and second == 0:
            continue
        group = next((position for position, members in enumerate(FOLD_GROUPS) if stat in members), stat)
        agreements[(group, first, second, entry['engine'])] = not _folds_disagree(first, second, entry['engine'])
    return list(agreements.values())


def _ceiling_breached(record):
    """Whether a pair of the cell, judged on both sides, put the table's set over the power ceiling."""
    pairs = list(record.get('dev') or ()) + [record.get('test')]
    return any(pair and pair['engine'].get('valid') and pair['table'].get('valid') and not _ceiling_holds(pair)
               for pair in pairs)


def e1a_verdict(records):
    """The E1a gate over the records of its cells, {'passed', 'checks', ...}.

    A class the blind gate cannot price keeps the engine whatever the tuner finds, so it cannot gain. The gains, the
    convergence, the fold agreement and the ceiling are counted over the live cells, all but one of which must gain,
    and the blind cells must have kept the engine without a run.
    """
    blind = [record for record in records if record.get('reason') == 'blind']
    live = [record for record in records if record.get('reason') != 'blind']
    gained = sum(1 for record in live if _cell_gained(record))
    needed = max(len(live) - 1, 1)
    runs = [run for record in live for run in record.get('instances') or ()]
    agreements = [agree for record in live for agree in _fold_agreements(record)]
    converged = sum(1 for run in runs if run.get('converged')) / float(len(runs)) if runs else 0.0
    agreeing = sum(agreements) / float(len(agreements)) if agreements else 0.0
    ceiling = sum(1 for record in live if _ceiling_breached(record))
    checks = {'live': bool(live), 'gains': gained >= needed, 'converged': converged >= E1A_CONVERGED,
              'folds': agreeing >= E1A_FOLDS_AGREE, 'ceiling': ceiling <= E1A_CEILING_CELLS,
              'blind': (all(record.get('status') == 'engine' and not record.get('instances') for record in blind)
                        and all((record.get('blind_share') or 0) >= BLIND_SHARE for record in live))}
    return {'live': len(live), 'blind': len(blind), 'gained': gained, 'needed': needed, 'converged': converged,
            'folds_agree': agreeing, 'ceiling_cells': ceiling,
            'repeated_sets': sum(1 for record in live if 'repeated_dev_sets' in (record.get('notes') or ())),
            'checks': checks, 'passed': all(checks.values())}


def repository_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_cell(text):
    """Cell of 'Class/str+int/scenario', the band being the grid's."""
    char_class, key, scenario = text.strip().split('/')[:3]
    elements = tuple(key.split('+'))
    if (char_class not in CHARACTER_CLASSES or elements not in grid_element_sets() or scenario not in SCENARIOS):
        raise ValueError('not a cell of the grid: %s' % text)
    return Cell(char_class, elements, scenario, BANDS[0])
