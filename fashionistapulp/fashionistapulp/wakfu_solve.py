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

"""One call that solves a Wakfu set within a time budget and returns only legal sets."""

import collections
import os
import time

from . import wakfu_criteria, wakfu_legality, wakfu_value
from .structure import fits_the_class
from .wakfu_exclusions import default_exclusions
from .wakfu_model import INFEASIBLE, WakfuBuild

#: Systems the model leaves out; a page must say so beside the set
SYSTEMS_NOT_COUNTED = (
    'runes', 'sublimations', 'aptitudes', 'pets', 'mounts', 'lucky charms',
    'states',
)


class WakfuIllegalSet(Exception):
    """The solver returned a set that breaks a rule; `violations` lists them."""

    def __init__(self, violations):
        # In args, so the exception pickles as cls(*args)
        super().__init__(violations)
        self.violations = violations

    def __str__(self):
        return '; '.join('%s: %s' % one for one in self.violations)


WakfuResult = collections.namedtuple(
    'WakfuResult', 'worn totals value turn status settled rounds seconds '
                   'not_counted reason build model legacy_left_out turn_model state '
                   'state_unlocks')
WakfuResult.__doc__ = """The outcome of solve_build.

worn: a wakfu_model.WakfuSet, or None. status: PROVEN when the search closed
its gap on the kept set's own LP, TIME_LIMIT when it stopped on its clock, None
with no set. settled: the rounds came back to the same set. For a damage
model the proof covers the linearised problem of the kept round, not the
nonlinear value. reason: INFEASIBLE or TIME_LIMIT when there is no set.
turn: wakfu_turn.Turn of the class on the kept set, or None. build: the
WakfuBuild that landed the kept set. turn_model: the wakfu_turn.TurnModel
the solve priced AP by, or None. state: the wakfu_criteria.PlayerState the
solve read the pieces' player-state conditions against. state_unlocks:
[(item id, {option: bound})] of the pieces that state keeps out, highest level
first, each with the value that would let it in.
"""

ELEMENT_NAMES = wakfu_value.ELEMENTS


def make_role(elements, reach, defense=None, movement=None):
    """A wakfu_value.DamageDealer; elements and reach are required, no default."""
    if isinstance(elements, str):
        elements = [name for name in elements.split(',') if name.strip()]
    if not elements:
        raise ValueError('elements are required: choose from %s'
                         % ', '.join(ELEMENT_NAMES))
    if len(tuple(elements)) > len(ELEMENT_NAMES):
        raise ValueError('at most %d elements' % len(ELEMENT_NAMES))
    if not reach:
        # Names a bad element before the missing reach
        wakfu_value.DamageDealer(elements, 'distance')
        raise ValueError('reach is required: %s' % ' or '.join(wakfu_value.REACH_MASTERY))
    return wakfu_value.DamageDealer(elements, reach, defense, movement=movement)


def harvest_criticals(level):
    """(critical values of the French harvest at `level` or None, where they come from)."""
    from . import wakfu_turn

    if level >= wakfu_turn.TEXT_LEVEL:
        return None, 'the encyclopedia text at level %d' % wakfu_turn.TEXT_LEVEL
    fallback = 'x%s the base damage, no French spell harvest' % (
        wakfu_turn.rule('critical_multiplier'))
    try:
        from itemscraper.wakfu_mirror import current_build_dir
    except ImportError:
        return None, fallback
    folder = current_build_dir()
    path = folder and os.path.join(str(folder), 'spells_fr.json')
    if not path or not os.path.exists(path):
        return None, fallback
    return (wakfu_turn.harvest_criticals(path, [level]),
            'the French spell harvest of %s' % os.path.basename(str(folder)))


def class_spells(level, class_id):
    """(damage spells, class mechanics, {spell id: name}, source of the critical values)."""
    from . import wakfu_turn

    critical, source = harvest_criticals(level)
    book = wakfu_turn.SpellBook(critical=critical)
    try:
        return (book.spells(class_id, level), book.class_mechanics(class_id),
                book.names(class_id), source)
    finally:
        book.close()


def turn_notes(turn, names):
    """Plain sentences for what a class turn leaves out of its damage."""
    from . import wakfu_turn

    notes = []
    for spell_id, position, keys, heading in turn.dropped:
        notes.append('%s row %d is not counted: %s%s' % (
            names.get(spell_id, spell_id), position,
            ', '.join(wakfu_turn.describe(key) for key in keys),
            ' (%s)' % heading if heading else ''))
    for spell_ids, key, detail in turn.unmodelled:
        notes.append('%s, %s: %s' % (
            ', '.join(str(names.get(one, one)) for one in spell_ids),
            wakfu_turn.describe(key), detail))
    return notes


def _set_up(structure, forbidden, locked, allow_legacy):
    forbidden = set(forbidden)
    locked = [(ident, position) for ident, position in locked]
    legacy = []
    if not allow_legacy:
        # An explicit lock outranks the default exclusion; the player's own forbid does not
        wanted = {ident for ident, _position in locked}
        legacy = [ident for ident in default_exclusions(structure)
                  if ident not in wanted]
        forbidden.update(legacy)
    return forbidden, locked, legacy


def _unlocks(structure, level, class_id, forbidden, state):
    """The pieces a build of this class and level could wear but for its state."""
    name = structure.get_breed_names().get(class_id)
    pool = [item for item in structure.get_available_items_list()
            if item.level <= level and item.id not in forbidden
            and fits_the_class(item, name)]
    return wakfu_criteria.state_unlocks(pool, state)


def _checked(structure, level, worn, forbidden, locked, minimums, class_id=None,
             state=None):
    problems = wakfu_legality.violations(structure, level, worn, forbidden,
                                         locked, minimums, class_id, state)
    if problems:
        raise WakfuIllegalSet(problems)


def solve_build(structure, *, level, elements, reach, class_id=None, forbidden=(),
                locked=(), allow_legacy=False, movement=None, seconds=90,
                defense=None, rounds=5, on_class_turn=True, state=None):
    """Best legal set for a damage role within `seconds` of wall time.

    elements (1 to 4 of fire, water, earth, air) and reach ('distance' or
    'melee') are required: ValueError otherwise. locked: (item id, position or
    None) pairs; a lock the rules cannot honour raises ValueError.
    class_id: Ankama class id; its best turn is reported, and the solve prices
    every AP total by that turn unless on_class_turn is false. state: a
    wakfu_criteria.PlayerState, the game's start values by default; a piece
    whose player-state condition it fails stays out of the solve. Raises
    WakfuIllegalSet rather than return a set that breaks a rule.
    """
    started = time.monotonic()
    deadline = started + seconds
    state = state or wakfu_criteria.start_state()
    role = make_role(elements, reach, defense, movement)
    if movement is not None and not class_id:
        raise ValueError('movement needs a class')
    forbidden, locked, legacy = _set_up(structure, forbidden, locked, allow_legacy)

    turn = names = mechanics = None
    not_counted = list(SYSTEMS_NOT_COUNTED)
    if class_id:
        from . import wakfu_turn
        spells, mechanics, names, _source = class_spells(level, class_id)
        if not spells:
            raise ValueError('class %d has no damage spell in the tables' % class_id)
        if on_class_turn:
            turn = wakfu_turn.TurnModel(spells, role)
            if turn.damage(wakfu_value.resource_ceiling(
                    wakfu_criteria.base_values(structure, class_id))) <= 0:
                raise ValueError(
                    'class %d has no damage turn for %s at %s, even with AP, MP and '
                    'WP at their caps' % (class_id, '+'.join(role.elements), role.reach))

    model = wakfu_value.solve(structure, level, role, forbidden, rounds, turn=turn,
                              locked=locked, deadline=deadline, class_id=class_id or None,
                              state=state)
    unlocks = _unlocks(structure, level, class_id or None, forbidden, state)
    best = model.best
    if best is None:
        return WakfuResult(None, None, None, None, None, False, len(model.rounds),
                           time.monotonic() - started, tuple(not_counted),
                           model.reason or INFEASIBLE, None, model, len(legacy), turn,
                           state, unlocks)

    _checked(structure, level, best.worn, forbidden, locked,
             role.minimums(wakfu_criteria.base_values(structure, class_id or None)),
             class_id or None, state)
    class_turn = None
    if class_id:
        from . import wakfu_turn
        spells = class_spells(level, class_id)[0]
        class_turn = wakfu_turn.best_turn(spells, role, best.totals,
                                          class_mechanics=mechanics)
        names = dict(names)
        names.update((spell.id, spell.name) for spell in spells)
        not_counted.extend(turn_notes(class_turn, names))
    return WakfuResult(best.worn, best.totals, best.value, class_turn,
                       best.worn.status, model.converged, len(model.rounds),
                       time.monotonic() - started, tuple(not_counted), None,
                       best.build, model, len(legacy), turn, state, unlocks)


def solve_weights(structure, *, level, weights, forbidden=(), locked=(),
                  allow_legacy=False, seconds=90, class_id=None, state=None):
    """Best legal set for hand-written weights, within `seconds`."""
    started = time.monotonic()
    state = state or wakfu_criteria.start_state()
    forbidden, locked, legacy = _set_up(structure, forbidden, locked, allow_legacy)
    unlocks = _unlocks(structure, level, class_id, forbidden, state)
    build = WakfuBuild(structure, level, weights, forbidden, locked=locked,
                       class_id=class_id, state=state)
    worn = build.build().solve(started + seconds)
    seconds_used = time.monotonic() - started
    if worn is None:
        return WakfuResult(None, None, None, None, None, False, 1, seconds_used,
                           SYSTEMS_NOT_COUNTED, build.reason or INFEASIBLE, build,
                           None, len(legacy), None, state, unlocks)
    _checked(structure, level, worn, forbidden, locked, None, class_id, state)
    return WakfuResult(worn, build.totals(worn), None, None, worn.status, True, 1,
                       seconds_used, SYSTEMS_NOT_COUNTED, None, build, None,
                       len(legacy), None, state, unlocks)
