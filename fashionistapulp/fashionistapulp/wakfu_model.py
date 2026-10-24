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

"""Pick the best legal set of Wakfu gear for a character."""

from __future__ import annotations

import collections

from . import wakfu_aptitudes, wakfu_companions, wakfu_runes, wakfu_sublimations
from .game_versions import get_game_version
from .lpproblem import LpProblem2
from .structure import fits_the_class
from .wakfu_criteria import base_values, start_state, state_holds, unlocking
from .wakfu_legality import WEAPON_POSITIONS
from .wakfu_slots import (BLOCKED_BY_TWO_HANDED, EXCLUSIVE_PROPERTIES,
                          SOLVED_SLOTS, TWO_HANDED_FLAG)
from .wakfu_stats import OUT_OF_COMBAT_CAPS, SPREAD_FAMILIES

# LP variable: this item, worn in this slot
WORN = 'w'
# LP variable: the set's AP total is this number
AP_TOTAL = 'apt'
# LP variable: the points put in this aptitude
APTITUDE = 'ab'
# LP variable: the sockets of a position band that hold this rune
RUNE = 'rn'
# LP variable: this set bonus tier is on
SET_TIER = 'st'
# LP variable: a normal sublimation item sits in this position
SUBLIMATION = 'sb'
# LP variable: sockets of a colour a position needs
SOCKET_COLOUR = 'sc'
# LP variable: a state counts at this level
STACK = 'sq'
# LP variable: a relic or epic sublimation is worn
SPECIAL = 'sx'
# LP variable: the conditions of a state's lines hold
ACTIVE = 'sa'
# LP variable: a clause of a condition fails
FAILS = 'sf'
# LP variable: a state counts at a level and its conditions hold
BOTH = 'sr'
# LP variable: what a conversion moves
CONVERTED = 'sv'
# LP variable: a class passive is taken
PASSIVE = 'ps'
# A conversion share is stored with this many decimals
SHARE_SCALE = 10 ** 6
# A line behind a test the model does not read
DROPPED = -1
# The aptitudes argument that lets the solver spread the points
SOLVE = wakfu_aptitudes.SOLVE
# What a point of aptitude costs the objective, so a point nothing pays for stays unspent
UNSPENT_COST = -1e-6

# WakfuSet.status and WakfuBuild.reason
PROVEN = 'proven'
STEPWISE = 'solved in steps'
TIME_LIMIT = 'time limit'
INFEASIBLE = 'infeasible'

# Element stat: the generic stat of its family
FAMILY_OF = {element: generic for generic, family in SPREAD_FAMILIES.items()
             for element in family}


def same_item(item):
    """Key shared by every rarity of one item: its type and French title."""
    # Each rarity is its own id; the English title can differ between them
    # (Kralaring, Kringlove)
    return item.type, (item.localized_names or {}).get('fr') or item.name


# One source of stat points, and the lowest and highest sum any set can take from it
Part = collections.namedtuple('Part', 'terms lowest highest')

# A stat's total: the base low and high, then the terms of every part
StatTotal = collections.namedtuple('StatTotal',
                                   'key low high terms lowest highest')


class _Source:
    """A state or a passive the model may count, and the lines it reads of it."""

    def __init__(self, name, entry, passive):
        self.name = name
        self.entry = entry
        self.passive = passive
        # Distinct sets of conditions (indexes) the lines are guarded by
        self.sets = []
        # (key, guard set or None, p0, p1) and (origin, target, p0, p1, sign, guard set)
        self.lines = []
        self.convs = []
        # {condition index: [({key: coefficient}, operator, bound)]}
        self.clauses = {}
        # Counted levels above 0 the lines are read at
        self.levels = []
        self.present = []
        self.offers = []
        self.state = None
        self.spell = None
        self.column = None
        self.reach = {}
        self.z_terms = []
        self.w_terms = []
        self.b = {}
        self.f = {}
        self.r = {}

    def keys(self):
        """Stat keys the lines and conversions touch."""
        found = {key for key, _at, _p0, _p1 in self.lines}
        for origin, target, *_rest in self.convs:
            found.update((origin, target))
        return found

    def condition_keys(self):
        """Stat keys the conditions of the guarded lines read."""
        return {key for clauses in self.clauses.values()
                for coefficients, _operator, _bound in clauses for key in coefficients}


class WakfuSet(dict):
    """{position: item} of a solve."""

    def __init__(self, worn=(), full_set_status=None, no_candidate=(),
                 status=None, aptitudes=None, battleground=False, set_tiers=(),
                 levels=None):
        super().__init__(worn)
        # {position: (sublimation item id, state, level, pattern)}, none given: None
        self.sublimations = None
        # {position: (sublimation item id, state, kind)} of the relic or epic one
        self.specials = None
        # [spell id] of the class passives taken, none given: None
        self.passives = None
        self.sublimation_mode = None
        self.passive_mode = None
        self.opt_in = {}
        # What the model left out of a source, in words
        self.notes = []
        # {state: StateReport} the fight reads, and the totals with and without the fight lines
        self.states = {}
        self.sheet_totals = collections.Counter()
        self.totals = collections.Counter()
        # {position: (Socket, ...)}, one per socket of the worn piece, filled ones first
        self.runes = {}
        self.rune_mode = None
        self.rune_tier = None
        # {item id: level} of the worn pets and mounts, at the level they are worn
        self.levels = dict(levels or {})
        # {aptitude id: points}, points above 0 only
        self.aptitudes = dict(aptitudes or {})
        self.battleground = battleground
        # [(set, pieces)] of the set bonus tiers the worn pieces reach
        self.set_tiers = list(set_tiers)
        # Status of the every-slot model when it gave no set, else None
        self.full_set_status = full_set_status
        self.no_candidate = tuple(no_candidate)
        # PROVEN when the search closed its gap, TIME_LIMIT when CBC stopped
        # on its clock holding this set
        self.status = status

    @property
    def sublimation_ids(self):
        """{position: sublimation item id}, None when none was asked for."""
        if self.sublimations is None:
            return None
        return {position: row[0] for position, row in self.sublimations.items()}

    @property
    def special_ids(self):
        """{position: relic or epic sublimation item id}, None when none was asked for."""
        if self.specials is None:
            return None
        return {position: row[0] for position, row in self.specials.items()}

    @property
    def full_set_dropped(self):
        """True when the solve had to allow empty slots."""
        return self.full_set_status is not None


class WakfuBuild:
    """Best set at a level; `weights` is keyed by stats.key.

    ap_values: optional {AP total: worth}, base included; the set is then worth
    the entry of its AP total instead of weights['ap'] per AP.

    locked: (item id, position or None) pairs; each item is worn, in that
    position when one is given. A lock the rules cannot honour raises
    ValueError here, before any solve. After solve(), reason says why a solve
    gave no set: INFEASIBLE or TIME_LIMIT.

    class_id: the breed; its base values count and its class pieces are
    candidates. With none, a piece that asks for a class is left out and the
    base values are the range over every breed. state: the PlayerState the
    pieces' player-state conditions are read against, the game's start values
    by default.

    aptitudes: None leaves aptitudes out; SOLVE lets the solver spread the
    points of every category; a dict {ability id: points} fixes them, and an
    unknown id or a negative or non-integer count raises ValueError. The
    budgets and caps of a fixed dict are checked by wakfu_legality, not here.
    battleground: the set bonus tiers count, those of the bracket of the level.

    levels: a wakfu_companions.Levels; a pet or a mount gives the lines it has
    at its level, the highest it allows when none is given. WakfuSet.levels
    reports the level each worn one was read at.

    runes: None or 'none' leaves the runes out; 'optimistic' fills every socket
    a worn piece can have with the runes the solver picks. rune_tier: the
    highest tier a socket may hold, the one its piece's level allows when None.
    WakfuSet.runes reports each socket of each worn piece.

    sublimations: None leaves them out, with every rule on them; 'none' counts only
    the states worn pieces carry; 'optimistic' lets the solver place a sublimation in any
    position whose pieces have the sockets, the colours free. passives: None or 'none'
    take no passive; 'solve' lets the solver pick the passives of the class, as many as its
    level opens. opt_in: {family: rate} with families E to H, carried and read by
    wakfu_sublimations.fight_lines. WakfuSet.sublimations, specials, passives and states
    report the choices, sheet_totals the totals the conditions read and totals the fight's.
    """

    def __init__(self, structure, level, weights, forbidden=(),
                 full_set=True, minimums=None, ap_values=None, locked=(),
                 class_id=None, state=None, aptitudes=None, battleground=False,
                 levels=None, runes=None, rune_tier=None, sublimations=None,
                 passives=None, opt_in=None, fight_constants=None):
        self.structure = structure
        # {stat key: value} added to the fight totals as lines no choice changes
        self._constant_fight = {key: value for key, value in (fight_constants or {}).items()
                                if value}
        self.sublimation_mode, self.passive_mode = wakfu_sublimations.read_options(
            structure, sublimations, passives)
        self.opt_in = wakfu_sublimations.read_opt_in(opt_in)
        self._given_sublimations = sublimations is not None
        self._given_passives = passives is not None
        self._block = wakfu_sublimations.load()
        self._sublimating = (self._block is not None
                             and self.sublimation_mode == wakfu_sublimations.OPTIMISTIC)
        # Gear states and the sublimation and passive rows exist when one of their arguments is given
        self._fight_on = (self._block is not None
                          and (self._given_sublimations or self._given_passives))
        self._reset_states()
        self.levels = levels or wakfu_companions.Levels()
        self.rune_mode, self.rune_tier = wakfu_runes.read_options(
            structure, runes, rune_tier)
        # {rune id: Rune} of the runes the solver may place
        self._runes = {}
        if self.rune_mode == wakfu_runes.OPTIMISTIC:
            self._runes = {ident: rune
                           for ident, rune in wakfu_runes.valued(structure).items()
                           if self._key_of(rune.stat) is not None}
        # {(position, rune id, band): (column name, value, stat key)}
        self._rune_columns = {}
        # {(position, band): most sockets}, {(item id, position): band}
        self._rune_limits = {}
        self._rune_band_of = {}
        # {position: names of its rune columns}
        self._rune_names = collections.defaultdict(set)
        self._lines = {}
        self.level = level
        self.class_id = class_id
        self.state = state or start_state()
        self._base = base_values(structure, class_id)
        self._class_name = (None if class_id is None
                            else structure.get_breed_names()[class_id])
        self._totals = {}
        self.weights = dict(weights)
        self.ap_values = None if ap_values is None else dict(ap_values)
        if self.ap_values is not None:
            self.weights.pop('ap', None)
        self.forbidden = set(forbidden)
        # Fill every slot, or slots worth 0 in the objective stay empty
        self.full_set = full_set
        # {stat key: lowest total, base values included}
        self.minimums = dict(minimums or {})
        self.full_set_status = None
        self.reason = None
        self.problem = None
        self._placements = []
        self._locks = self._read_locks(locked)
        self.battleground = bool(battleground)
        self.aptitudes = aptitudes
        self._fixed = self._read_aptitudes(aptitudes)
        # {ability id: (per point lines, most points)} of the variables
        self._ab_lines = {}
        # {'<set>_<pieces>': lines} of the tier variables
        self._tier_lines = {}
        self._fixed_lines = collections.Counter()

    def _apt_table(self):
        return wakfu_aptitudes.table(self.structure, self.level, self.battleground)

    def _read_aptitudes(self, aptitudes):
        """The fixed {id: points} of the argument, None when the solver spreads them."""
        if aptitudes is None or (isinstance(aptitudes, str) and aptitudes == SOLVE):
            return None
        if not isinstance(aptitudes, dict):
            raise ValueError('aptitudes are None, %r or {ability id: points}, got %r'
                             % (SOLVE, aptitudes))
        known = self._apt_table().abilities
        for ident, points in aptitudes.items():
            if ident not in known:
                raise ValueError('unknown aptitude %r' % (ident,))
            if not isinstance(points, int) or isinstance(points, bool) or points < 0:
                raise ValueError('aptitude %r takes a whole number of points, got %r'
                                 % (ident, points))
        return {ident: points for ident, points in aptitudes.items() if points}

    def _positions_of_type(self):
        """{type id: [position, ...]}"""
        places = collections.defaultdict(list)
        for type_id, position in self.structure.get_type_positions():
            places[type_id].append(position)
        return places

    def _read_locks(self, locked):
        """[(item, position or None)] of the locks, refused when no set can honour them."""
        locked = list(locked)
        if not locked:
            return []
        locks = []
        places = self._positions_of_type()
        for ident, position in locked:
            item = self.structure.get_item_by_id(ident)
            if item is None:
                raise ValueError('locked item %r is not in the catalogue' % (ident,))
            if item.removed:
                raise ValueError('locked item %s is removed from the game' % item.name)
            if item.level > self.level:
                raise ValueError('locked item %s is level %d, above the build '
                                 'level %d' % (item.name, item.level, self.level))
            if item.id in self.forbidden:
                raise ValueError('locked item %s is forbidden' % item.name)
            why = self._why_not_wearable(item)
            if why:
                raise ValueError('locked item %s %s' % (item.name, why))
            for target_id in getattr(item, 'worn_with', ()):
                self._check_worn_with_target(item, target_id)
            allowed = places.get(item.type, ())
            if not allowed:
                raise ValueError('locked item %s fits no slot' % item.name)
            if position is not None and position not in allowed:
                raise ValueError('locked item %s cannot sit in %s, only in %s'
                                 % (item.name, position, ', '.join(allowed)))
            locks.append((item, position))
        self._check_locks_agree(locks, places)
        return locks

    def _check_locks_agree(self, locks, places):
        keys = {}
        for item, _position in locks:
            other = keys.setdefault(same_item(item), item)
            if other is not item:
                raise ValueError('locked items %s and %s are one item in two '
                                 'rarities' % (other.name, item.name))
        if len({item.id for item, _position in locks}) < len(locks):
            raise ValueError('an item is locked twice')
        held = {item.id: item for item, _position in locks}
        for item, _position in locks:
            for other_id in getattr(item, 'not_worn_with', ()):
                if other_id in held:
                    raise ValueError('locked items %s and %s cannot be worn '
                                     'together' % (item.name, held[other_id].name))
        for flag in EXCLUSIVE_PROPERTIES.values():
            held = [item for item, _p in locks if flag in (item.flags or ())]
            if len(held) > 1:
                raise ValueError('locked items %s are all %s items, a character '
                                 'wears one' % (', '.join(i.name for i in held), flag))
        if not self._slots_for_locks(locks, places):
            raise ValueError('locked items %s need the same slot'
                             % ', '.join(item.name for item, _p in locks))
        two_handed = [item for item, _p in locks
                      if TWO_HANDED_FLAG in (item.flags or ())]
        if two_handed:
            for item, position in locks:
                only_place = position or (places[item.type][0]
                                          if len(places[item.type]) == 1 else None)
                if only_place == BLOCKED_BY_TWO_HANDED:
                    raise ValueError('locked item %s is two-handed and a lock fills '
                                     'the second weapon slot' % two_handed[0].name)

    @staticmethod
    def _slots_for_locks(locks, places):
        """True when every lock can have a slot of its own."""
        taken = {}

        def place(index, seen):
            item, position = locks[index]
            for slot in ([position] if position else places[item.type]):
                if slot in seen:
                    continue
                seen.add(slot)
                if slot not in taken or place(taken[slot], seen):
                    taken[slot] = index
                    return True
            return False

        return all(place(index, set()) for index in range(len(locks)))

    def _why_not_wearable(self, item):
        """Why this character cannot wear a piece whatever else is worn, or ''."""
        if getattr(item, 'unusable', False):
            return 'cannot be worn by anyone'
        if not fits_the_class(item, self._class_name):
            return 'is for the %s, not for this character' % '/'.join(
                getattr(item, 'classes', ()))
        lowest = getattr(item, 'min_level', None)
        highest = getattr(item, 'max_level', None)
        if lowest is not None and self.level < lowest:
            return 'needs level %d, the build is level %d' % (lowest, self.level)
        if highest is not None and self.level > highest:
            return 'is for level %d at most, the build is level %d' % (
                highest, self.level)
        conditions = getattr(item, 'state_conditions', ())
        if not state_holds(conditions, self.state):
            return 'needs ' + ', '.join(self._state_needs(conditions))
        return ''

    def _state_needs(self, conditions):
        """['wakfu_gauge >= 41', ...] for each condition the build state fails."""
        failing = unlocking(conditions, self.state) or {}
        out = []
        for condition in conditions:
            key = ((condition.option, condition.nation)
                   if condition.option == 'citizenship' else condition.option)
            if key not in failing:
                continue
            name = condition.option
            if condition.option == 'citizenship':
                name = 'citizenship of nation %s' % condition.nation
            out.append('%s %s %s' % (name, condition.operator, condition.value))
        return sorted(out)

    def _check_worn_with_target(self, item, target_id):
        target = self.structure.get_item_by_id(target_id)
        if target is None or target.removed:
            raise ValueError('locked item %s needs item %s, which is not in the '
                             'catalogue' % (item.name, target_id))
        if target.level > self.level or target.id in self.forbidden \
                or self._why_not_wearable(target):
            raise ValueError('locked item %s needs %s, which this build cannot '
                             'wear' % (item.name, target.name))

    def _item_lines(self, item):
        """[(stat id, value)] of an item at the level it is worn at."""
        if item.id not in self._lines:
            self._lines[item.id] = wakfu_companions.lines_at(
                item, wakfu_companions.level_of(self.levels, item))
        return self._lines[item.id]

    def _statless(self, item):
        if (self._runes or self._sublimating) and wakfu_runes.sockets_of(item):
            return False
        return not self._item_lines(item) and not item.element_spread

    def _candidates(self):
        """Every (item, position) a character of this level could wear."""
        places = self._positions_of_type()
        wearable = []
        for item in self.structure.get_available_items_list():
            if item.level > self.level or item.id in self.forbidden:
                continue
            if self._why_not_wearable(item):
                continue
            for position in places.get(item.type, ()):
                wearable.append((item, position))
        # A piece with no stat line only stands where no piece with one does
        locked = {item.id for item, _position in self._locks}
        with_stats = {position for item, position in wearable
                      if not self._statless(item)}
        kept = {(item.id, position) for item, position in wearable
                if not self._statless(item) or item.id in locked
                or position not in with_stats}
        # A kept piece brings in the piece it must be worn with, and goes when
        # that piece cannot be worn at all
        by_id = collections.defaultdict(list)
        for item, position in wearable:
            by_id[item.id].append((item, position))
        items = {item.id: item for item, _position in wearable}
        changed = True
        while changed:
            changed = False
            for ident, position in sorted(kept):
                targets = getattr(items[ident], 'worn_with', ())
                if any(target not in by_id for target in targets):
                    kept.discard((ident, position))
                    changed = True
                    continue
                for target in targets:
                    for other, place in by_id[target]:
                        if (other.id, place) not in kept:
                            kept.add((other.id, place))
                            changed = True
        return [(item, position) for item, position in wearable
                if (item.id, position) in kept]

    def _stat_value(self, item, key):
        stat = self.structure.get_stat_by_key(key)
        if stat is None:
            return 0
        return sum(value for stat_id, value in self._item_lines(item)
                   if stat_id == stat.id)

    def _key_of(self, stat_id):
        stat = self.structure.get_stat_by_id(stat_id)
        return stat.key if stat is not None else None

    def _element_weights(self, generic):
        """{element stat: weight}, dmg_in_percent's or res_in_percent's added."""
        extra = self.weights.get(generic, 0)
        return {name: self.weights.get(name, 0) + extra
                for name in SPREAD_FAMILIES[generic]}

    def _lands_on(self, generic, value, elements):
        """Elements a spread line feeds: the best N, the worst N for a loss."""
        weights = self._element_weights(generic)
        sign = -1 if value >= 0 else 1
        ranked = sorted(weights, key=lambda name: sign * weights[name])
        return ranked[:max(0, elements)]

    def _plain_lines(self, item):
        """(stat id, value) rows of an item, its spread lines left out."""
        # Spread lines are also rows of item.stats
        spread = collections.Counter((stat_id, value) for stat_id, value, _e
                                     in item.element_spread or ())
        for stat_id, value in self._item_lines(item):
            if spread[(stat_id, value)]:
                spread[(stat_id, value)] -= 1
                continue
            yield stat_id, value

    def _plain_weight(self, key):
        """Worth of one point of a line that is not spread."""
        if key in SPREAD_FAMILIES:
            # Elemental mastery and resistance apply to every element
            return sum(self._element_weights(key).values())
        if key in FAMILY_OF:
            return self._element_weights(FAMILY_OF[key])[key]
        return self.weights.get(key, 0)

    def _spread_weight(self, key, value, elements):
        if key not in SPREAD_FAMILIES:
            return self.weights.get(key, 0)
        weights = self._element_weights(key)
        return sum(weights[name]
                   for name in self._lands_on(key, value, elements))

    def _worth(self, item):
        total = 0
        for stat_id, value in self._plain_lines(item):
            total += value * self._plain_weight(self._key_of(stat_id))
        for stat_id, value, elements in item.element_spread or ():
            total += value * self._spread_weight(self._key_of(stat_id), value,
                                                 elements)
        return total

    def build(self):
        self.problem = LpProblem2()
        self._totals = {}
        self._placements = self._candidates()
        for item, position in self._placements:
            self.problem.setup_variable(WORN, self._name(item, position), 0, 1)
        self._aptitude_variables()
        self._set_tier_variables()
        self._rune_variables()
        self._sublimation_model()

        self._one_item_per_slot()
        self._one_copy_of_an_item()
        self._two_handed_empties_the_off_hand()
        self._one_relic_and_one_epic()
        self._caps()
        self._minimums()
        self._locked()
        self._ap_total()
        self._stat_gates()
        self._item_relations()
        self._objective()
        return self

    def _name(self, item, position):
        return '%d_%s' % (item.id, position)

    def _parcels(self, placements, coefficient=1):
        return [(coefficient, WORN, self._name(item, position))
                for item, position in placements]

    def _aptitude_variables(self):
        """One integer column per aptitude with a counted line, a budget row per category."""
        self._ab_lines = {}
        self._fixed_lines = collections.Counter()
        if self.aptitudes is None:
            return
        table = self._apt_table()
        if self._fixed is not None:
            for ident, points in self._fixed.items():
                for key, per_point in table.abilities[ident][2]:
                    self._fixed_lines[key] += per_point * points
            return
        budget = wakfu_aptitudes.budgets(self.structure, self.level)
        by_category = collections.defaultdict(list)
        for ident, (category, cap, lines, _notes) in sorted(table.abilities.items()):
            upper = min(cap, budget.get(category, 0)) if cap else budget.get(category, 0)
            if lines and upper > 0:
                self.problem.setup_variable(APTITUDE, ident, 0, upper)
                self._ab_lines[ident] = (lines, upper)
                by_category[category].append(ident)
        for category, idents in sorted(by_category.items()):
            self.problem.add_row(
                LpProblem2._parcel_terms([(1, APTITUDE, ident) for ident in idents]),
                '<=', budget[category], 'aptitude_budget_%d' % category)

    def _set_tier_variables(self):
        """A binary column per tier a battleground build can reach, on exactly when held."""
        self._tier_lines = {}
        if not self.battleground:
            return
        table = self._apt_table()
        if not table.tiers:
            return
        variables = collections.defaultdict(list)
        for item, position in self._placements:
            variables[item.id].append(self._name(item, position))
        for (item_set, pieces), lines in sorted(table.tiers.items()):
            titles = [[name for ident in ids for name in variables.get(ident, ())]
                      for ids in table.members[item_set]]
            titles = [names for names in titles if names]
            if len(titles) < pieces:
                continue
            name = '%d_%d' % (item_set, pieces)
            self.problem.setup_variable(SET_TIER, name, 0, 1)
            self._tier_lines[name] = lines
            members = [one for names in titles for one in names]
            self.problem.add_row(
                LpProblem2._parcel_terms([(pieces, SET_TIER, name)]
                                         + [(-1, WORN, one) for one in members]),
                '<=', 0, 'tier_%s_on' % name)
            self.problem.add_row(
                LpProblem2._parcel_terms([(1, WORN, one) for one in members]
                                         + [(pieces - len(titles) - 1, SET_TIER, name)]),
                '<=', pieces - 1, 'tier_%s_off' % name)

    def _read_stat_keys(self):
        """Stat keys a row of the model reads, whatever sources feed them."""
        keys = set(self.minimums) | {name.lower() for name in OUT_OF_COMBAT_CAPS}
        for item, _position in self._placements:
            for stat_id, _bound in (tuple(getattr(item, 'min_stats_to_equip', ()))
                                    + tuple(getattr(item, 'max_stats_to_equip', ()))):
                key = self._key_of(stat_id)
                if key is not None:
                    keys.add(key)
        return keys

    def _kept_runes(self, tiers, position, read):
        """The runes a band of this position may hold: those a row reads, and for each
        colour the best of the others, which any other of its colour cannot beat."""
        kept = []
        best = {}
        for ident, rune in sorted(self._runes.items()):
            key = self._key_of(rune.stat)
            if key in read:
                kept.append(ident)
                continue
            number = wakfu_runes.value(rune, tiers[ident], position in rune.doubles)
            worth = number * self._plain_weight(key)
            if worth > 0 and (rune.colour not in best or worth > best[rune.colour][0]):
                best[rune.colour] = (worth, ident)
        return sorted(kept + [ident for _worth, ident in best.values()])

    def _rune_variables(self):
        """An integer column per rune of each band of each socketed position."""
        self._rune_columns = {}
        self._rune_limits = {}
        self._rune_band_of = {}
        self._rune_names = collections.defaultdict(set)
        if not self._runes:
            return
        read = self._read_stat_keys()
        by_position = collections.defaultdict(list)
        for item, position in self._placements:
            if wakfu_runes.sockets_of(item):
                by_position[position].append(item)
        for position, items in sorted(by_position.items()):
            bands = {}
            members = collections.defaultdict(list)
            for item in items:
                tiers = tuple((ident, wakfu_runes.socket_tier(rune, item, self.rune_tier))
                              for ident, rune in sorted(self._runes.items()))
                band = bands.setdefault(tiers, len(bands))
                self._rune_band_of[(item.id, position)] = band
                members[band].append(item)
                limit = (position, band)
                self._rune_limits[limit] = max(self._rune_limits.get(limit, 0),
                                               wakfu_runes.sockets_of(item))
            for tiers, band in bands.items():
                tiers = dict(tiers)
                names = []
                for ident in self._kept_runes(tiers, position, read):
                    rune = self._runes[ident]
                    name = '%d_%s_%d' % (ident, position, band)
                    number = wakfu_runes.value(rune, tiers[ident], position in rune.doubles)
                    self.problem.setup_variable(
                        RUNE, name, 0, self._rune_limits[(position, band)])
                    self._rune_columns[(position, ident, band)] = (
                        name, number, self._key_of(rune.stat))
                    self._rune_names[position].add(name)
                    names.append(name)
                parcels = [(1, RUNE, name) for name in names]
                parcels += [(-wakfu_runes.sockets_of(item), WORN, self._name(item, position))
                            for item in members[band]]
                self.problem.add_row(LpProblem2._parcel_terms(parcels), '<=', 0,
                                     'sockets_%s_%d' % (position, band))

    def rune_colour_terms(self, position, colour):
        """[(1, RUNE, column)] of the sockets of this position that hold a rune of this colour."""
        return [(1, RUNE, name)
                for (place, ident, _band), (name, _number, _key)
                in sorted(self._rune_columns.items())
                if place == position and self._runes[ident].colour == colour]

    # Sublimations, gear states and passives

    def _reset_states(self):
        self._sources = {}
        self._z = {}
        self._w = {}
        self._col = {}
        self._fight = collections.defaultdict(list)
        self._fight_bounds = collections.defaultdict(lambda: [0, 0])
        self._gear_lines = collections.defaultdict(lambda: collections.defaultdict(
            collections.Counter))
        self._gear_worth = collections.Counter()
        self._column_worth = []
        self._clamps = {}
        self._fight_totals = {}
        self.notes = []

    def _fight_add(self, key, terms, lowest, highest):
        self._fight[key].extend(terms)
        self._fight_bounds[key][0] += lowest
        self._fight_bounds[key][1] += highest

    def _prepare_source(self, name, entry, passive):
        """The _Source of a state or a passive: the lines and conversions the model reads.

        A test on the character alone is settled here. A line behind a test the model does
        not read is left out, with a note.
        """
        rules = wakfu_sublimations
        kinds = [rules.condition_kind(condition) for condition in entry['conditions']]
        holds = {at: rules.condition_holds([condition], {}, self.level, self.class_id)[0]
                 for at, condition in enumerate(entry['conditions'])
                 if kinds[at] == rules.STATIC}
        source = _Source(name, entry, passive)

        def place(guards):
            dynamic = set()
            for at in guards:
                if kinds[at] == rules.UNSUPPORTED:
                    self.notes.append('%s: condition %r is not read, its lines are left out'
                                      % (name, entry['conditions'][at][:2]))
                    return DROPPED
                if kinds[at] == rules.STATIC:
                    if not holds[at]:
                        return DROPPED
                else:
                    dynamic.add(at)
            if not dynamic:
                return None
            found = tuple(sorted(dynamic))
            if found not in source.sets:
                source.sets.append(found)
            return source.sets.index(found)

        for _family, key, p0, p1, guards in entry['lines']:
            at = place(guards)
            if at != DROPPED:
                source.lines.append((key, at, p0, p1))
        for origin, target, p0, p1, sign, guards in entry['conversions']:
            at = place(guards)
            if at != DROPPED:
                source.convs.append((origin, target, p0, p1, sign, at))
        for found in source.sets:
            for at in found:
                source.clauses[at] = rules.condition_clauses(entry['conditions'][at])
        return source if source.lines or source.convs else None

    def _gear_state_lines(self, read):
        """The lines of the states the worn pieces carry, one term for each piece."""
        block = self._block
        for item, position in self._placements:
            for state, level in block.GEAR_STATES.get(item.id, ()):
                entry = block.STATES[state]
                if entry['conditions'] or entry['conversions'] or any(
                        guards for *_rest, guards in entry['lines']):
                    self.notes.append('gear state %d has a condition, it is left out' % state)
                    continue
                at = wakfu_sublimations.counted_level([level], entry['cap'])
                for _family, key, p0, p1, _guards in entry['lines']:
                    value = wakfu_sublimations.value_at(p0, p1, at)
                    if value and (key in read or self._plain_weight(key)):
                        name = self._name(item, position)
                        self._gear_lines[key][position][name] += value
                        self._gear_worth[name] += value * self._plain_weight(key)

    def _gear_state_part(self, key):
        terms = []
        lowest = highest = 0
        for _position, rows in sorted(self._gear_lines.get(key, {}).items()):
            terms.extend((value, WORN, name) for name, value in sorted(rows.items()))
            lowest += min([0] + list(rows.values()))
            highest += max([0] + list(rows.values()))
        return Part(terms, lowest, highest)

    def _state_offers(self):
        """{state: [(item id, level, kind, pattern)]}, the lowest item id for each level,
        kind and colour counts a state's sublimations come in."""
        best = {}
        for ident, (state, level, kind, pattern) in sorted(self._block.SUBLIMATIONS.items()):
            needs = tuple(sorted(wakfu_sublimations.colour_needs(pattern).items()))
            best.setdefault((state, level, kind, needs), (ident, level, kind, pattern))
        out = collections.defaultdict(list)
        for (state, *_rest), row in sorted(best.items()):
            out[state].append(row)
        return out

    def _sublimation_model(self):
        """Columns and rows of the sublimations, the gear states and the passives."""
        self._reset_states()
        block = self._block
        if block is None or not self._fight_on:
            return
        rules = wakfu_sublimations
        read = set(self._read_stat_keys())
        self._gear_state_lines(read)
        most = collections.defaultdict(int)
        kinds_at = collections.defaultdict(set)
        for item, position in self._placements:
            most[position] = max(most[position], wakfu_runes.sockets_of(item))
            if rules.special_kind(item):
                kinds_at[rules.special_kind(item)].add(position)
        prepared = {}
        for state, rows in sorted(self._state_offers().items() if self._sublimating else ()):
            usable = [row for row in rows
                      if (row[2] == rules.KIND_NORMAL
                          and any(count >= len(row[3]) for count in most.values()))
                      or (row[2] != rules.KIND_NORMAL and kinds_at[row[2]])]
            source = self._prepare_source(str(state), block.STATES[state], False)
            if usable and source is not None:
                source.state = state
                source.offers = usable
                prepared[source.name] = source
        if self.passive_mode == rules.SOLVE:
            if self.class_id is None:
                self.notes.append('passives need a class')
            else:
                for spell in rules.passives_of(self.class_id, self.level):
                    source = self._prepare_source('p%d' % spell, block.PASSIVES[spell], True)
                    if source is not None:
                        source.spell = spell
                        prepared[source.name] = source
        kept = {}
        changed = True
        while changed:
            changed = False
            for name, source in sorted(prepared.items()):
                if name not in kept and any(key in read or self._plain_weight(key)
                                            for key in source.keys()):
                    kept[name] = source
                    read |= source.condition_keys()
                    changed = True
        self._sources = kept
        self._socket_model(kept, most)
        for source in kept.values():
            self._source_columns(source)
        passives = [source.column for source in kept.values() if source.passive]
        if passives:
            self.problem.add_row(
                LpProblem2._parcel_terms([(1, PASSIVE, column) for column in passives]),
                '<=', rules.slots_open(self.level), 'passive_slots')
        for source in kept.values():
            self._source_rows(source)

    def _socket_model(self, kept, most):
        """z(p, i), the specials w(i) and the colour columns col(p, k) with their rows."""
        rules = wakfu_sublimations
        by_position = collections.defaultdict(list)
        for source in kept.values():
            if source.passive:
                continue
            for ident, level, kind, pattern in source.offers:
                if kind == rules.KIND_NORMAL:
                    for position, count in sorted(most.items()):
                        if count < len(pattern):
                            continue
                        name = '%s_%d' % (position, ident)
                        self.problem.setup_variable(SUBLIMATION, name, 0, 1)
                        self._z[(position, ident)] = name
                        by_position[position].append((ident, pattern))
                        source.z_terms.append((level, SUBLIMATION, name))
                        source.reach[position] = max(source.reach.get(position, 0), level)
                        self._column_worth.append((SUBLIMATION, name, UNSPENT_COST))
                else:
                    self.problem.setup_variable(SPECIAL, ident, 0, 1)
                    self._w[ident] = kind
                    source.w_terms.append((level, SPECIAL, ident))
                    source.reach[kind] = max(source.reach.get(kind, 0), level)
                    self._column_worth.append((SPECIAL, ident, UNSPENT_COST))
        for position, rows in sorted(by_position.items()):
            held = [(item, place) for item, place in self._placements if place == position]
            for number in sorted({len(pattern) for _ident, pattern in rows}):
                names = [self._z[(position, ident)] for ident, pattern in rows
                         if len(pattern) >= number]
                pieces = [self._name(item, place) for item, place in held
                          if wakfu_runes.sockets_of(item) >= number]
                self.problem.add_row(
                    LpProblem2._parcel_terms([(1, SUBLIMATION, name) for name in names]
                                             + [(-1, WORN, name) for name in pieces]),
                    '<=', 0, 'sublimation_%s_%d' % (position, number))
            widest = max(wakfu_runes.sockets_of(item) for item, _place in held)
            for colour in wakfu_runes.RUNE_COLOURS:
                column = '%s_%d' % (position, colour)
                self.problem.setup_variable(SOCKET_COLOUR, column, 0, widest)
                self._col[(position, colour)] = column
                needs = [(rules.colour_needs(pattern).get(colour, 0), SUBLIMATION,
                          self._z[(position, ident)]) for ident, pattern in rows]
                needs = [parcel for parcel in needs if parcel[0]]
                if needs:
                    self.problem.add_row(
                        LpProblem2._parcel_terms(needs + [(-1, SOCKET_COLOUR, column)]),
                        '<=', 0, 'colour_%s_pattern' % column)
                runes = self.rune_colour_terms(position, colour)
                if runes:
                    self.problem.add_row(
                        LpProblem2._parcel_terms(runes + [(-1, SOCKET_COLOUR, column)]),
                        '<=', 0, 'colour_%s_rune' % column)
            self.problem.add_row(
                LpProblem2._parcel_terms(
                    [(1, SOCKET_COLOUR, self._col[(position, colour)])
                     for colour in wakfu_runes.RUNE_COLOURS]
                    + [(-wakfu_runes.sockets_of(item), WORN, self._name(item, place))
                       for item, place in held]),
                '<=', 0, 'colour_%s_sockets' % position)
        for kind in rules.SPECIAL_KINDS:
            names = [ident for ident, one in sorted(self._w.items()) if one == kind]
            if not names:
                continue
            worn = [(-1, WORN, self._name(item, place)) for item, place in self._placements
                    if rules.special_kind(item) == kind]
            self.problem.add_row(
                LpProblem2._parcel_terms([(1, SPECIAL, ident) for ident in names] + worn),
                '<=', 0, 'special_%s_worn' % kind)
            self.problem.add_row(
                LpProblem2._parcel_terms([(1, SPECIAL, ident) for ident in names]),
                '<=', 1, 'special_%s_one' % kind)

    def _source_columns(self, source):
        """The stack, passive, condition and product columns of a kept source, and the lines
        they feed into the fight totals and the objective."""
        if source.passive:
            source.levels = [self.level]
            source.column = str(source.spell)
            self.problem.setup_variable(PASSIVE, source.column, 0, 1)
            self._column_worth.append((PASSIVE, source.column, UNSPENT_COST))
            source.present = [(1, PASSIVE, source.column)]
        else:
            self._stack_columns(source)
            source.present = [(1, STACK, '%s_%d' % (source.name, at))
                              for at in source.levels]
        for at in range(len(source.sets)):
            source.b[at] = '%s_%d' % (source.name, at)
            self.problem.setup_variable(ACTIVE, source.b[at], 0, 1)
        for found in source.sets:
            for condition in found:
                for part in range(len(source.clauses[condition])):
                    source.f[(condition, part)] = '%s_%d_%d' % (source.name, condition, part)
                    self.problem.setup_variable(FAILS, source.f[(condition, part)], 0, 1)
        if len(source.levels) > 1:
            for at in range(len(source.sets)):
                for level in source.levels:
                    source.r[(at, level)] = '%s_%d_%d' % (source.name, at, level)
                    self.problem.setup_variable(BOTH, source.r[(at, level)], 0, 1)
        self._line_terms(source)
        self._conversion_columns(source)

    def _stack_columns(self, source):
        """q(s, e) for each counted level the state can reach, tied to min(levels, cap)."""
        cap = source.entry['cap']
        smax = sum(source.reach.values())
        top = min(cap, smax) if cap else smax
        source.levels = list(range(1, top + 1))
        name = source.name
        columns = [(at, STACK, '%s_%d' % (name, at)) for at in range(top + 1)]
        for _at, _category, column in columns:
            self.problem.setup_variable(STACK, column, 0, 1)
        self.problem.add_row(
            LpProblem2._parcel_terms([(1, category, column) for _at, category, column
                                      in columns]), '==', 1, 'stack_%s_one' % name)
        added = source.z_terms + source.w_terms
        self.problem.add_row(
            LpProblem2._parcel_terms(
                [parcel for parcel in columns if parcel[0]]
                + [(-level, category, ident) for level, category, ident in added]),
            '<=', 0, 'stack_%s_below' % name)
        over = []
        if cap and smax > cap:
            over = [(-(smax - cap), STACK, '%s_%d' % (name, cap))]
        if added:
            self.problem.add_row(
                LpProblem2._parcel_terms(
                    list(added) + [(-at, category, column) for at, category, column in columns]
                    + over),
                '<=', 0, 'stack_%s_cap' % name)

    def _indicator(self, source, found, level):
        """(category, name) of the column that is 1 when the lines of a guard set count at
        this level: the stack column, the condition column, or the product of both."""
        if found is None:
            return ((PASSIVE, source.column) if source.passive
                    else (STACK, '%s_%d' % (source.name, level)))
        if len(source.levels) == 1:
            return ACTIVE, source.b[found]
        return BOTH, source.r[(found, level)]

    def _line_terms(self, source):
        """The lines of a source in the fight totals and the objective."""
        grouped = collections.defaultdict(lambda: collections.defaultdict(int))
        for key, found, p0, p1 in source.lines:
            for level in source.levels:
                grouped[(key, found)][level] += wakfu_sublimations.value_at(p0, p1, level)
        for (key, found), values in sorted(grouped.items(), key=str):
            terms = []
            for level, value in sorted(values.items()):
                if value:
                    category, name = self._indicator(source, found, level)
                    terms.append((value, category, name))
                    self._column_worth.append((category, name, value * self._plain_weight(key)))
            numbers = [value for value, _category, _name in terms]
            self._fight_add(key, terms, min([0] + numbers), max([0] + numbers))

    def _conversion_columns(self, source):
        """v(s, c): what a conversion moves, an integer floored as the client floors it."""
        for number, (origin, target, p0, p1, sign, found) in enumerate(source.convs):
            total = self.stat_total_expr(origin)
            low, high = total.low + total.lowest, total.low + total.highest
            if high <= 0:
                continue
            amounts = []
            for level in source.levels:
                share = wakfu_sublimations.share_at(p0, p1, level)
                if origin == target and sign < 0:
                    share = min(share, 1)
                scale = round(share * SHARE_SCALE)
                most = scale * high // SHARE_SCALE
                if not most:
                    continue
                name = '%s_%d_%d' % (source.name, number, level)
                indicator = self._indicator(source, found, level)
                if low < 0:
                    indicator = self._clamped(origin, total, low, high, indicator, name)
                self.problem.setup_variable(CONVERTED, name, 0, most)
                self._column_worth.append((CONVERTED, name, sign * self._plain_weight(target)))
                self._conversion_rows(name, indicator, total, scale, most, low, high)
                self._fight_add(target, [(sign, CONVERTED, name)], 0, 0)
                amounts.append(sign * most)
            self._fight_bounds[target][0] += min([0] + amounts)
            self._fight_bounds[target][1] += max([0] + amounts)

    def _clamped(self, origin, total, low, high, indicator, label):
        """The column that is 1 when `indicator` is 1 and the sheet total of `origin` is not
        negative: a negative total moves nothing."""
        if origin not in self._clamps:
            column = 'h_%s' % origin
            self.problem.setup_variable(ACTIVE, column, 0, 1)
            self.problem.add_row(
                LpProblem2._parcel_terms([(-value, category, name)
                                          for value, category, name in total.terms]
                                         + [(-low, ACTIVE, column)]),
                '<=', total.low - low, 'clamp_%s_up' % origin)
            self.problem.add_row(
                LpProblem2._parcel_terms([(value, category, name)
                                          for value, category, name in total.terms]
                                         + [(-high, ACTIVE, column)]),
                '<=', -total.low, 'clamp_%s_down' % origin)
            self._clamps[origin] = column
        both = 'h_%s' % label
        self.problem.setup_variable(BOTH, both, 0, 1)
        column = self._clamps[origin]
        category, name = indicator
        self.problem.add_row(
            LpProblem2._parcel_terms([(1, BOTH, both), (-1, category, name)]),
            '<=', 0, 'and_%s_a' % both)
        self.problem.add_row(
            LpProblem2._parcel_terms([(1, BOTH, both), (-1, ACTIVE, column)]),
            '<=', 0, 'and_%s_b' % both)
        self.problem.add_row(
            LpProblem2._parcel_terms([(-1, BOTH, both), (1, category, name),
                                      (1, ACTIVE, column)]),
            '<=', 1, 'and_%s_c' % both)
        return BOTH, both

    def _conversion_rows(self, name, indicator, total, scale, most, low, high):
        """v is floor(scale x X / SHARE_SCALE) while the indicator is 1, and 0 otherwise."""
        category, ident = indicator
        self.problem.add_row(
            LpProblem2._parcel_terms([(1, CONVERTED, name), (-most, category, ident)]),
            '<=', 0, 'convert_%s_off' % name)
        below = scale * max(0, -low)
        self.problem.add_row(
            LpProblem2._parcel_terms(
                [(SHARE_SCALE, CONVERTED, name)]
                + [(-scale * value, cat, one) for value, cat, one in total.terms]
                + [(below, category, ident)]),
            '<=', below + scale * total.low, 'convert_%s_up' % name)
        above = max(0, scale * high - (SHARE_SCALE - 1))
        self.problem.add_row(
            LpProblem2._parcel_terms(
                [(-SHARE_SCALE, CONVERTED, name)]
                + [(scale * value, cat, one) for value, cat, one in total.terms]
                + [(above, category, ident)]),
            '<=', SHARE_SCALE - 1 - scale * total.low + above, 'convert_%s_down' % name)

    def _clause_expression(self, coefficients):
        """(terms, base, lowest, highest) of a sum of sheet totals, on the lowest base."""
        terms = []
        base = lowest = highest = 0
        for key, coefficient in sorted(coefficients.items()):
            total = self.stat_total_expr(key)
            base += coefficient * total.low
            if coefficient > 0:
                lowest += coefficient * total.lowest
                highest += coefficient * total.highest
            else:
                lowest += coefficient * total.highest
                highest += coefficient * total.lowest
            terms.extend((coefficient * value, category, name)
                         for value, category, name in total.terms)
        return terms, base, lowest, highest

    def _clause_rows(self, source, condition, part, sets):
        """The rows that tie b (the clause holds) and f (it fails) to the sheet totals.

        Every big-M is the distance between the bound and the sum's own lowest or highest
        value, read from the bounds of the totals.
        """
        coefficients, operator, bound = source.clauses[condition][part]
        terms, base, lowest, highest = self._clause_expression(coefficients)
        label = '%s_%d_%d' % (source.name, condition, part)
        if operator == '>=':
            holds = bound - (base + lowest)
            fails = (base + highest) - (bound - 1)
            holding = ([(-value, category, name) for value, category, name in terms],
                       holds - bound + base)
            failing = ([(value, category, name) for value, category, name in terms],
                       bound - 1 - base + fails)
        else:
            holds = (base + highest) - bound
            fails = (bound + 1) - (base + lowest)
            holding = ([(value, category, name) for value, category, name in terms],
                       bound - base + holds)
            failing = ([(-value, category, name) for value, category, name in terms],
                       fails - (bound + 1) + base)
        if holds > 0:
            for at in sets:
                self.problem.add_row(
                    LpProblem2._parcel_terms(holding[0] + [(holds, ACTIVE, source.b[at])]),
                    '<=', holding[1], 'holds_%s_%d' % (label, at))
        if fails > 0:
            self.problem.add_row(
                LpProblem2._parcel_terms(
                    failing[0] + [(fails, FAILS, source.f[(condition, part)])]),
                '<=', failing[1], 'fails_%s' % label)

    def _source_rows(self, source):
        """Presence, the conditions and the products of a kept source."""
        for at, found in enumerate(source.sets):
            self.problem.add_row(
                LpProblem2._parcel_terms(
                    [(1, ACTIVE, source.b[at])]
                    + [(-number, category, name) for number, category, name in source.present]),
                '<=', 0, 'active_%s_%d_present' % (source.name, at))
            fails = [(-1, FAILS, source.f[(condition, part)]) for condition in found
                     for part in range(len(source.clauses[condition]))]
            self.problem.add_row(
                LpProblem2._parcel_terms(list(source.present) + fails
                                         + [(-1, ACTIVE, source.b[at])]),
                '<=', 0, 'active_%s_%d_reverse' % (source.name, at))
        for condition in sorted({one for found in source.sets for one in found}):
            sets = [at for at, found in enumerate(source.sets) if condition in found]
            for part in range(len(source.clauses[condition])):
                self._clause_rows(source, condition, part, sets)
        for (at, level), column in sorted(source.r.items()):
            stack = (STACK, '%s_%d' % (source.name, level))
            self.problem.add_row(
                LpProblem2._parcel_terms([(1, BOTH, column), (-1, stack[0], stack[1])]),
                '<=', 0, 'both_%s_a' % column)
            self.problem.add_row(
                LpProblem2._parcel_terms([(1, BOTH, column), (-1, ACTIVE, source.b[at])]),
                '<=', 0, 'both_%s_b' % column)
            self.problem.add_row(
                LpProblem2._parcel_terms([(-1, BOTH, column), (1, stack[0], stack[1]),
                                          (1, ACTIVE, source.b[at])]),
                '<=', 1, 'both_%s_c' % column)

    def fight_total_expr(self, key):
        """A stat's total in the fight: the sheet total plus what the sublimations, the worn
        pieces' states and the passives add. The sheet total itself when none touches it."""
        sheet = self.stat_total_expr(key)
        if key not in self._fight_totals:
            part = self._gear_state_part(key)
            terms = list(part.terms) + list(self._fight.get(key, ()))
            constant = self._constant_fight.get(key, 0)
            if not terms and not constant:
                self._fight_totals[key] = sheet
            else:
                lowest, highest = self._fight_bounds.get(key, (0, 0))
                self._fight_totals[key] = StatTotal(
                    key, sheet.low + constant, sheet.high + constant, sheet.terms + terms,
                    sheet.lowest + part.lowest + lowest,
                    sheet.highest + part.highest + highest)
        return self._fight_totals[key]

    def report(self, worn):
        """Read the set's totals and states off this build: the spread lines land as this
        build's weights put them, and the states read the totals that gives."""
        worn.sheet_totals = self.sheet_totals(worn)
        worn.totals = self.totals(worn)
        worn.states = self._fight_lines(worn)[1]

    def held_lines(self, worn):
        """{stat key: value} the set's sublimations, specials and passives give in the fight,
        the worn pieces' own states left out."""
        return self._fight_lines(worn, gear=False)[0]

    def _fight_lines(self, worn, gear=True):
        """({stat key: value}, {state: StateReport}) the set's sources give in the fight."""
        block = self._block
        if block is None or not self._fight_on:
            return {}, {}
        reading = self.sheet_totals(worn)
        skip = {name.lower() for name in OUT_OF_COMBAT_CAPS}
        for key, (low, _high) in self._base.items():
            if key not in skip:
                reading[key] += low
        rules = wakfu_sublimations
        choices = [(rules.SUBLIMATION, row[0])
                   for given in (getattr(worn, 'sublimations', None),
                                 getattr(worn, 'specials', None))
                   for row in (given or {}).values()]
        if gear:
            choices += [(rules.GEAR, item.id) for item in worn.values()
                        if item.id in block.GEAR_STATES]
        choices += [(rules.PASSIVE, spell) for spell in getattr(worn, 'passives', None) or ()]
        weapons = {item.type for position, item in worn.items() if position in WEAPON_POSITIONS}
        return rules.fight_lines(choices, reading, self.level, self.class_id, self.opt_in,
                                 weapons)

    def objective_of(self, worn):
        """What this build's objective is worth on any set: the columns' worth read from the
        set's own choices, so it equals the solver's objective on the set the solver gave."""
        total = 0.0
        for item in worn.values():
            total += self._worth(item)
        for ident, points in (getattr(worn, 'aptitudes', None) or {}).items():
            if ident in self._ab_lines:
                total += points * (UNSPENT_COST + sum(
                    per_point * self._plain_weight(key)
                    for key, per_point in self._ab_lines[ident][0]))
        for tier in getattr(worn, 'set_tiers', ()):
            name = '_'.join(str(number) for number in tier)
            total += sum(number * self._plain_weight(key)
                         for key, number in self._tier_lines.get(name, ()))
        for position, sockets in (getattr(worn, 'runes', None) or {}).items():
            item = worn.get(position)
            for socket in sockets:
                band = self._rune_band_of.get((item.id, position)) if item else None
                column = self._rune_columns.get((position, socket.rune, band))
                if socket.rune is not None and column is not None:
                    total += column[1] * self._plain_weight(column[2]) + UNSPENT_COST
        lines, _reports = self._fight_lines(worn)
        total += sum(value * self._plain_weight(key) for key, value in lines.items())
        given = [getattr(worn, name, None) or () for name in ('sublimations', 'specials',
                                                              'passives')]
        total += UNSPENT_COST * sum(len(one) for one in given)
        if self.ap_values is not None:
            reached = self.totals(worn)['ap']
            if reached in self._ap_totals():
                total += self.ap_values.get(reached, min(self.ap_values.values()))
        return total

    def _one_item_per_slot(self):
        """One item per slot, exactly one when full_set."""
        by_slot = collections.defaultdict(list)
        for item, position in self._placements:
            by_slot[position].append((item, position))
        for position in SOLVED_SLOTS:
            if not by_slot[position]:
                continue
            parcels = self._parcels(by_slot[position])
            if self.full_set and position != BLOCKED_BY_TWO_HANDED:
                # Off hand can stay empty for two-handed weapons
                self.problem.restriction_eq(1, parcels)
            else:
                self.problem.restriction_lt_eq(1, parcels)

    def _one_copy_of_an_item(self):
        """One copy of a ring, in either hand, its other rarities included."""
        doubles = get_game_version('wakfu').rings_can_double
        by_item = collections.defaultdict(list)
        for item, position in self._placements:
            by_item[same_item(item)].append((item, position))
        for placements in by_item.values():
            if len({position for _item, position in placements}) > 1:
                self.problem.restriction_lt_eq(
                    2 if doubles else 1, self._parcels(placements))

    def _two_handed_empties_the_off_hand(self):
        off_hand = [(item, position) for item, position in self._placements
                    if position == BLOCKED_BY_TWO_HANDED]
        if not off_hand:
            return
        for item, position in self._placements:
            if TWO_HANDED_FLAG not in (item.flags or ()):
                continue
            self.problem.restriction_lt_eq(
                1, self._parcels([(item, position)]) + self._parcels(off_hand))

    def _one_relic_and_one_epic(self):
        for flag in EXCLUSIVE_PROPERTIES.values():
            wearing = [(item, position) for item, position in self._placements
                       if flag in (item.flags or ())]
            if wearing:
                self.problem.restriction_lt_eq(1, self._parcels(wearing))

    def _gear_part(self, key):
        """The worn pieces' lines of one stat."""
        terms = []
        lowest = collections.defaultdict(int)
        highest = collections.defaultdict(int)
        for item, position in self._placements:
            value = self._stat_value(item, key)
            if value:
                terms.append((value, WORN, self._name(item, position)))
                lowest[position] = min(lowest[position], value)
                highest[position] = max(highest[position], value)
        return Part(terms, sum(lowest.values()), sum(highest.values()))

    def _aptitude_part(self, key):
        """The points put in the aptitudes, as lines of one stat."""
        terms = []
        lowest = highest = 0
        for ident, (lines, upper) in self._ab_lines.items():
            for line_key, per_point in lines:
                if line_key == key:
                    terms.append((per_point, APTITUDE, str(ident)))
                    lowest += min(0, per_point * upper)
                    highest += max(0, per_point * upper)
        return Part(terms, lowest, highest)

    def _set_bonus_part(self, key):
        """The set bonus tiers, as lines of one stat."""
        terms = []
        lowest = highest = 0
        for name, lines in self._tier_lines.items():
            value = sum(number for line_key, number in lines if line_key == key)
            if value:
                terms.append((value, SET_TIER, name))
                lowest += min(0, value)
                highest += max(0, value)
        return Part(terms, lowest, highest)

    def _rune_part(self, key):
        """The runes placed in the sockets, as lines of one stat."""
        terms = []
        best = {}
        for (position, _ident, band), (name, number, rune_key) in self._rune_columns.items():
            if rune_key == key:
                terms.append((number, RUNE, name))
                limit = self._rune_limits[(position, band)]
                top, bottom = best.get((position, band), (0, 0))
                best[(position, band)] = (max(top, limit * number),
                                          min(bottom, limit * number))
        highest = collections.defaultdict(int)
        lowest = collections.defaultdict(int)
        for (position, _band), (top, bottom) in best.items():
            highest[position] = max(highest[position], top)
            lowest[position] = min(lowest[position], bottom)
        return Part(terms, sum(lowest.values()), sum(highest.values()))

    def _total_parts(self):
        """Every source of stat points; a later source is appended here."""
        return [self._gear_part, self._aptitude_part, self._set_bonus_part,
                self._rune_part]

    def stat_total_expr(self, key):
        """A stat's total as base plus terms, the one every rule reads."""
        if key not in self._totals:
            low, high = self._base.get(key, (0, 0))
            low += self._fixed_lines.get(key, 0)
            high += self._fixed_lines.get(key, 0)
            terms, lowest, highest = [], 0, 0
            for part in self._total_parts():
                one = part(key)
                terms += one.terms
                lowest += one.lowest
                highest += one.highest
            self._totals[key] = StatTotal(key, low, high, terms, lowest, highest)
        return self._totals[key]

    def _caps(self):
        """AP, MP and WP caps, base values included."""
        for name, cap in OUT_OF_COMBAT_CAPS.items():
            total = self.stat_total_expr(name.lower())
            if total.terms:
                self.problem.restriction_lt_eq(cap - total.high, total.terms)

    def _minimums(self):
        """Lowest totals, base values included, as a <= on the negated sums."""
        for key, required in sorted(self.minimums.items()):
            total = self.fight_total_expr(key)
            if total.terms:
                self.problem.restriction_lt_eq(
                    total.low - required,
                    [(-value, category, name)
                     for value, category, name in total.terms])

    def _locked(self):
        """Each locked item is worn, in its position when the lock names one."""
        for item, position in self._locks:
            placements = [(one, place) for one, place in self._placements
                          if one.id == item.id
                          and (position is None or place == position)]
            self.problem.restriction_eq(1, self._parcels(placements))

    def _ap_totals(self):
        """Every AP total a set can reach, base included, up to the cap."""
        total = self.fight_total_expr('ap')
        sheet = self.stat_total_expr('ap')
        beyond = max(0, total.highest - sheet.highest + total.high - sheet.high)
        return range(total.low + total.lowest, OUT_OF_COMBAT_CAPS['AP'] + 1 + beyond)

    def _ap_total(self):
        """One AP_TOTAL variable at 1, the one the worn AP adds up to."""
        if self.ap_values is None:
            return
        totals = self._ap_totals()
        for total in totals:
            self.problem.setup_variable(AP_TOTAL, total, 0, 1)
        self.problem.restriction_eq(1, [(1, AP_TOTAL, total) for total in totals])
        base = self.fight_total_expr('ap')
        parcels = [(base.low - total, AP_TOTAL, total) for total in totals]
        parcels.extend(base.terms)
        self.problem.restriction_eq(0, parcels)

    def _variables_of(self, item):
        return [self._name(one, position) for one, position in self._placements
                if one.id == item.id]

    def _gate_row(self, item, key, bound, upper, total=None, tag=''):
        """One condition of a piece on a stat total, read with and without the piece."""
        total = total or self.stat_total_expr(key)
        value = self._stat_value(item, key)
        if upper:
            slack = total.high + total.highest - min(value, 0) - bound
            sign, rhs = 1, bound - total.high + min(value, 0) + slack
        else:
            slack = bound + max(value, 0) - (total.low + total.lowest)
            sign, rhs = -1, total.low - max(value, 0) - bound + slack
        if not upper and any(category == RUNE for _c, category, _n in total.terms):
            self._min_gate_rows(item, key, bound, total, value, tag)
            return
        if slack <= 0:
            return
        coefficients = collections.OrderedDict(
            ((category, name), sign * coefficient)
            for coefficient, category, name in total.terms)
        for name in self._variables_of(item):
            coefficients[(WORN, name)] = coefficients.get((WORN, name), 0) + slack
        parcels = [(coefficient, category, name)
                   for (category, name), coefficient in coefficients.items()]
        self.problem.add_row(LpProblem2._parcel_terms(parcels), '<=', rhs,
                             'gate_%d_%s_%s%s' % (item.id, key,
                                                  'max' if upper else 'min', tag))

    def _min_gate_rows(self, item, key, bound, total, value, tag=''):
        """A minimum read per placement: the piece and the runes in its own sockets are
        left out of the reading without it, and the reading with it must hold too."""
        for one, position in self._placements:
            if one.id != item.id:
                continue
            own = self._rune_names.get(position, ())
            readings = [(value, [term for term in total.terms
                                 if not (term[1] == RUNE and term[2] in own)], 'min')]
            if value < 0:
                readings.append((0, list(total.terms), 'with'))
            for taken, terms, label in readings:
                slack = bound + taken - (total.low + total.lowest)
                if slack <= 0:
                    continue
                coefficients = collections.OrderedDict(
                    ((category, name), -coefficient) for coefficient, category, name in terms)
                place = (WORN, self._name(one, position))
                coefficients[place] = coefficients.get(place, 0) + slack
                parcels = [(coefficient, category, name)
                           for (category, name), coefficient in coefficients.items()]
                self.problem.add_row(
                    LpProblem2._parcel_terms(parcels), '<=',
                    total.low - taken - bound + slack,
                    'gate_%d_%s_%s_%s%s' % (item.id, key, label, position, tag))

    def _stat_gates(self):
        """Each piece's own conditions on the stat totals of the set it is worn in."""
        seen = set()
        for item, _position in self._placements:
            if item.id in seen:
                continue
            seen.add(item.id)
            for stat_id, bound in getattr(item, 'min_stats_to_equip', ()):
                key = self._key_of(stat_id)
                if key is not None:
                    self._gate_rows(item, key, bound, upper=False)
            for stat_id, bound in getattr(item, 'max_stats_to_equip', ()):
                key = self._key_of(stat_id)
                if key is not None:
                    self._gate_rows(item, key, bound, upper=True)

    def _gate_rows(self, item, key, bound, upper):
        """A condition holds on the sheet total, and on the fight total where a state
        touches it."""
        self._gate_row(item, key, bound, upper)
        fight = self.fight_total_expr(key)
        if fight is not self.stat_total_expr(key):
            self._gate_row(item, key, bound, upper, fight, '_fight')

    def _item_relations(self):
        """Pieces worn only with, or never with, another piece."""
        wanted = {item.id: item for item, _position in self._placements}
        for ident, item in sorted(wanted.items()):
            for other_id in sorted(getattr(item, 'not_worn_with', ())):
                other = wanted.get(other_id)
                if other is None or other_id < ident:
                    continue
                if same_item(item) == same_item(other):
                    continue
                parcels = [(1, WORN, name) for name in self._variables_of(item)]
                parcels += [(1, WORN, name) for name in self._variables_of(other)]
                self.problem.add_row(LpProblem2._parcel_terms(parcels), '<=', 1,
                                     'apart_%d_%d' % (ident, other_id))
            for other_id in sorted(getattr(item, 'worn_with', ())):
                if other_id not in wanted:
                    continue
                parcels = [(1, WORN, name) for name in self._variables_of(item)]
                parcels += [(-1, WORN, name)
                            for name in self._variables_of(wanted[other_id])]
                self.problem.add_row(LpProblem2._parcel_terms(parcels), '<=', 0,
                                     'needs_%d_%d' % (ident, other_id))

    def _objective(self):
        self.problem.init_objective_function()
        for item, position in self._placements:
            name = self._name(item, position)
            worth = self._worth(item) + self._gear_worth.get(name, 0)
            if worth:
                self.problem.add_to_of(WORN, name, worth)
        for ident, (lines, _upper) in self._ab_lines.items():
            self.problem.add_to_of(APTITUDE, ident, UNSPENT_COST + sum(
                per_point * self._plain_weight(key) for key, per_point in lines))
        for name, lines in self._tier_lines.items():
            worth = sum(number * self._plain_weight(key) for key, number in lines)
            if worth:
                self.problem.add_to_of(SET_TIER, name, worth)
        for name, number, key in self._rune_columns.values():
            self.problem.add_to_of(RUNE, name, number * self._plain_weight(key) + UNSPENT_COST)
        for category, name, worth in self._column_worth:
            self.problem.add_to_of(category, name, worth)
        if self.ap_values is not None:
            floor = min(self.ap_values.values())
            for total in self._ap_totals():
                self.problem.add_to_of(AP_TOTAL, total, self.ap_values.get(total, floor))
        self.problem.finish_objective_function()

    def _run(self, deadline):
        from .wakfu_value import solver_time_limit

        with solver_time_limit(deadline):
            self.problem.run()

    def solve(self, deadline=None):
        """WakfuSet or None; drops full_set only when that model is infeasible.

        deadline: a time.monotonic() value; each CBC run, the fallback run
        included, is cut to what is left when it starts.

        With no set, reason says why: INFEASIBLE, TIME_LIMIT, or the solver's
        own word for any other status.
        """
        if self.problem is None:
            self.build()
        self.reason = None
        self._run(deadline)
        if self.problem.get_status() == 'Infeasible' and self.full_set:
            self.full_set_status = self.problem.get_status()
            self.full_set = False
            self.problem = None
            self.build()
            self._run(deadline)
        status = self.problem.get_status()
        if status != 'Optimal':
            # PuLP calls a search that ran out of time without a set Not Solved
            self.reason = {'Not Solved': TIME_LIMIT,
                           'Infeasible': INFEASIBLE}.get(status, status.lower())
            return None
        chosen = self.problem.get_result()
        placed = {position for _item, position in self._placements}
        if self._fixed is not None:
            points = dict(self._fixed)
        else:
            points = {ident: round(chosen.get('%s_%s' % (APTITUDE, ident)) or 0)
                      for ident in self._ab_lines}
        tiers = [tuple(int(number) for number in name.split('_'))
                 for name in self._tier_lines
                 if (chosen.get('%s_%s' % (SET_TIER, name)) or 0) > 0.5]
        # Optimal is also what PuLP says when CBC stopped on its time limit
        worn = WakfuSet(full_set_status=self.full_set_status,
                        no_candidate=[slot for slot in SOLVED_SLOTS
                                      if slot not in placed],
                        status=(PROVEN if self.problem.solution_is_proven()
                                else TIME_LIMIT),
                        aptitudes={ident: number for ident, number in points.items()
                                   if number > 0},
                        battleground=self.battleground, set_tiers=sorted(tiers))
        for item, position in self._placements:
            name = '%s_%s' % (WORN, self._name(item, position))
            if (chosen.get(name) or 0) > 0.5:
                worn[position] = item
        worn.levels = {item.id: wakfu_companions.level_of(self.levels, item)
                       for item in worn.values()
                       if getattr(item, 'level_cap', None) is not None}
        worn.rune_mode = self.rune_mode
        worn.rune_tier = self.rune_tier
        self._chosen_sources(worn, chosen)
        if self._runes or worn.sublimations:
            worn.runes = self._sockets(worn, chosen)
        self.report(worn)
        worn.notes = list(self.notes)
        return worn

    def _chosen_sources(self, worn, chosen):
        """The sublimations, specials and passives the solver picked, on the set."""
        worn.sublimation_mode = self.sublimation_mode
        worn.passive_mode = self.passive_mode
        worn.opt_in = dict(self.opt_in)
        block = self._block
        if self._given_sublimations:
            worn.sublimations = {}
            worn.specials = {}
        if self._given_passives:
            worn.passives = []
        if block is None:
            return
        for (position, ident), name in sorted(self._z.items()):
            if (chosen.get('%s_%s' % (SUBLIMATION, name)) or 0) > 0.5:
                state, level, _kind, pattern = block.SUBLIMATIONS[ident]
                worn.sublimations[position] = (ident, state, level, pattern)
        for ident, kind in sorted(self._w.items()):
            if (chosen.get('%s_%s' % (SPECIAL, ident)) or 0) > 0.5:
                state = block.SUBLIMATIONS[ident][0]
                position = min(place for place, item in worn.items()
                               if wakfu_sublimations.special_kind(item) == kind)
                worn.specials[position] = (ident, state, kind)
        for source in self._sources.values():
            if source.passive and (chosen.get('%s_%s' % (PASSIVE, source.column)) or 0) > 0.5:
                worn.passives.append(source.spell)
        worn.passives = sorted(worn.passives) if worn.passives is not None else None

    def _sockets(self, worn, chosen):
        """{position: (Socket, ...)} of the worn pieces, one per socket, filled ones first."""
        out = {}
        for position, item in sorted(worn.items()):
            count = wakfu_runes.sockets_of(item)
            if not count:
                continue
            placed = (getattr(worn, 'sublimations', None) or {}).get(position)
            pattern = placed[3] if placed else ()
            if not self._runes and not pattern:
                continue
            band = self._rune_band_of.get((item.id, position))
            filled = []
            for (place, ident, one), (name, _number, _key) in sorted(
                    self._rune_columns.items(), key=lambda row: row[0][1]):
                if place != position or one != band:
                    continue
                rune = self._runes[ident]
                tier = wakfu_runes.socket_tier(rune, item, self.rune_tier)
                doubled = position in rune.doubles
                number = round(chosen.get('%s_%s' % (RUNE, name)) or 0)
                filled.extend([(rune, tier, doubled)] * number)
            out[position] = self._arranged(count, filled, pattern)
        return out

    @staticmethod
    def _socket_of(index, rune, tier, doubled):
        return wakfu_runes.Socket(
            index, rune.colour, rune.id, tier, wakfu_runes.value(rune, tier, doubled),
            doubled, wakfu_runes.shards_at(rune, tier))

    def _arranged(self, count, filled, pattern):
        """The sockets of a piece: the pattern first, each rune in a socket of its colour,
        the extra sockets after it, an empty extra socket with no colour."""
        pool = list(filled)
        sockets = [None] * count
        for index, colour in enumerate(pattern):
            pick = next((one for one in pool if colour and one[0].colour == colour), None)
            if pick is not None:
                pool.remove(pick)
                sockets[index] = self._socket_of(index, *pick)
            else:
                sockets[index] = wakfu_runes.Socket(
                    index, colour or None, None, None, 0, False, 0)
        for index, colour in enumerate(pattern):
            if not colour and pool and sockets[index].rune is None:
                sockets[index] = self._socket_of(index, *pool.pop(0))
        if len(pool) > count - len(pattern):
            raise ValueError('%d runes do not fit %d sockets after a pattern of %d'
                             % (len(filled), count, len(pattern)))
        for index in range(len(pattern), count):
            sockets[index] = (self._socket_of(index, *pool.pop(0)) if pool
                              else wakfu_runes.Socket(index, None, None, None, 0, False, 0))
        return tuple(sockets)

    def spread_lines(self, worn):
        """[(position, item, key, value, elements it landed on)] of a set."""
        out = []
        for position in sorted(worn):
            item = worn[position]
            for stat_id, value, elements in item.element_spread or ():
                key = self._key_of(stat_id)
                if key in SPREAD_FAMILIES:
                    out.append((position, item, key, value,
                                self._lands_on(key, value, elements)))
        return out

    def where_the_spread_lands(self, worn):
        """{stat key: total} for the elements a build's spread lines feed."""
        landing = collections.Counter()
        for _position, _item, _key, value, landed in self.spread_lines(worn):
            for name in landed:
                landing[name] += value
        return landing

    def totals(self, worn):
        """Stat totals of a set in the fight: the sheet totals and the lines of the
        sublimations, the worn pieces' states and the passives."""
        out = self.sheet_totals(worn)
        out.update(self._fight_lines(worn)[0])
        return out

    def sheet_totals(self, worn):
        """Stat totals of the sheet: worn lines, spread lines landed, aptitudes, set bonus
        tiers, runes and base values. The lines of sublimations and passives are left out."""
        out = collections.Counter()
        for item in worn.values():
            for stat_id, value in self._plain_lines(item):
                key = self._key_of(stat_id)
                if key is not None:
                    out[key] += value
            for stat_id, value, _elements in item.element_spread or ():
                key = self._key_of(stat_id)
                if key is not None and key not in SPREAD_FAMILIES:
                    out[key] += value
        out.update(self.where_the_spread_lands(worn))
        out.update(self._source_lines(worn))
        out.update(wakfu_runes.lines(self.structure, worn, getattr(worn, 'runes', None)))
        for name in OUT_OF_COMBAT_CAPS:
            out[name.lower()] += self._base[name.lower()][0]
        return out

    def _source_lines(self, worn):
        """Counter of the lines the aptitudes and the set bonus tiers of a set give."""
        lines = collections.Counter()
        given = getattr(worn, 'aptitudes', None) or {}
        if not given and not self.battleground:
            return lines
        table = self._apt_table()
        for ident, points in given.items():
            for key, per_point in table.abilities[ident][2]:
                lines[key] += per_point * points
        if self.battleground:
            ids = {item.id for item in worn.values()}
            for tier in wakfu_aptitudes.tiers_reached(table, ids):
                for key, number in table.tiers[tier]:
                    lines[key] += number
        return lines
