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
from types import MappingProxyType

from . import (wakfu_aptitudes, wakfu_companions, wakfu_criteria, wakfu_legality,
               wakfu_runes, wakfu_sublimations, wakfu_value)
from .structure import fits_the_class
from .wakfu_exclusions import default_exclusions
from .wakfu_model import INFEASIBLE, SOLVE, WakfuBuild

#: Systems the model leaves out; a page must say so beside the set
SYSTEMS_NOT_COUNTED = (
    'sublimations', 'states',
)

#: Aptitudes whose lines the value model does not price, and why
UNVALUED_APTITUDES = {
    6: 'armor given is counted in the totals and not valued, as on gear',
    17: 'barrier gives nothing a build can count, its effect needs a fight',
    27: 'heals received gives nothing a build can count, a state effect with '
        'no characteristic',
    36: 'armor from a percent of health points, not in the value model until '
        'the defense simulator',
    38: 'heals performed is counted in the totals, no heal model prices it',
    39: 'its indirect damage is characteristic 101, which the client tables do '
        'not name, so only its elemental mastery counts',
}


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
                   'state_unlocks aptitudes aptitude_mode unspent set_tiers levels '
                   'runes rune_mode rune_tier sublimations specials states passives '
                   'passive_slots sublimation_mode passive_mode opt_in settled_by gap '
                   'sheet_totals warnings',
    defaults=(MappingProxyType({}), None, MappingProxyType({}), (),
              MappingProxyType({}), MappingProxyType({}), None, None,
              MappingProxyType({}), MappingProxyType({}), MappingProxyType({}), (), 0,
              None, None, MappingProxyType({}), None, None, MappingProxyType({}), ()))
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
first, each with the value that would let it in. aptitudes: {ability id:
points above 0} of the set. aptitude_mode: 'solve' when the solver spread the
points, 'fixed' when they were given, None when aptitudes were left out.
unspent: {category: points left}, empty with no aptitudes. set_tiers: [(set, pieces)]
of the set bonus tiers the set reaches. levels: {item id: level} of the worn pets
and mounts, each at the level it was read at. runes: {position: (Socket, ...)}, one
Socket per socket of each worn piece that has any, the filled ones first. rune_mode:
wakfu_runes.OPTIMISTIC or NONE, None when nothing was asked. rune_tier: the tier cap.
sublimations: {position: (sublimation item id, state, level, pattern)}; specials:
{position: (item id, state, kind)} of the relic and the epic sublimation; states: {state:
wakfu_sublimations.StateReport} of every state the fight reads, passives keyed by (PASSIVE,
spell id); passives: [spell id]; passive_slots: how many the level opens (0 when passives
were not solved); sublimation_mode and passive_mode: the modes asked, None for none;
opt_in: {family: rate}. settled_by: 'key' when a round came back to the kept set, 'gap' when
the gap certificate held, None otherwise, and settled says the same; gap: the objective the
last non-improving round gained over the kept set on its own objective, in percent of the
value, None when no round was compared. status is wakfu_model.STEPWISE when the kept set
came from the two-step fallback. sheet_totals: the totals the state conditions read, totals
being the fight's. warnings: [(rule, text)] of wakfu_legality.warnings plus the solve's
own notes.
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
             state=None, aptitudes=None, battleground=False, rune_tier=None,
             spread=None):
    problems = wakfu_legality.violations(structure, level, worn, forbidden,
                                         locked, minimums, class_id, state,
                                         aptitudes, battleground, worn.levels,
                                         worn.runes, rune_tier, spread=spread)
    if problems:
        raise WakfuIllegalSet(problems)


def _aptitude_mode(structure, level, aptitudes):
    """'solve', 'fixed' or None; ValueError when a fixed vector breaks a rule."""
    if aptitudes is None:
        return None
    if isinstance(aptitudes, str):
        if aptitudes != SOLVE:
            raise ValueError('aptitudes are %r, None or {ability id: points}, got %r'
                             % (SOLVE, aptitudes))
        return 'solve'
    if not isinstance(aptitudes, dict):
        raise ValueError('aptitudes are %r, None or {ability id: points}, got %r'
                         % (SOLVE, aptitudes))
    problems = wakfu_legality.aptitude_violations(structure, level, aptitudes)
    if problems:
        raise ValueError('; '.join('%s: %s' % one for one in problems))
    return 'fixed'


def _rune_notes(structure, mode):
    """What not_counted says about the runes: nothing when they are solved."""
    if mode == wakfu_runes.NONE:
        return ['runes (left out by the mode)']
    if not wakfu_runes.valued(structure):
        return ['runes (the database holds no rune table)']
    return []


def _system_notes(sublimations, passives):
    """What not_counted says about the sublimations and the passives."""
    if wakfu_sublimations.load() is None or (sublimations is None and passives is None):
        return list(SYSTEMS_NOT_COUNTED)
    notes = []
    if sublimations is None:
        notes.append('sublimations')
    elif sublimations == wakfu_sublimations.NONE:
        notes.append('sublimations (left out by the mode)')
    if passives in (None, wakfu_sublimations.NONE):
        notes.append('passives (left out by the mode)')
    return notes


def _leaf_notes(worn):
    """One entry per state or passive leaf of the set the model could not count."""
    block = wakfu_sublimations.load()
    if block is None:
        return []
    notes = []
    for key in sorted(getattr(worn, 'states', None) or {}, key=str):
        if isinstance(key, tuple):
            entry, label = block.PASSIVES[key[1]], 'passive'
        else:
            entry, label = block.STATES[key], 'state'
        for family, _ident, reason in entry['uncounted']:
            note = '%s %s (family %s): %s' % (label, entry['name'], family, reason)
            if note not in notes:
                notes.append(note)
    notes.extend(note for note in getattr(worn, 'notes', ()) if note not in notes)
    return notes


def aptitude_notes(structure, level, battleground):
    """One sentence per aptitude the value model does not price."""
    abilities = wakfu_aptitudes.table(structure, level, battleground).abilities
    return ['%s (aptitude %d): %s' % (
        structure.aptitude_ability_names.get((ident, 'en'), ident), ident, reason)
        for ident, reason in sorted(UNVALUED_APTITUDES.items()) if ident in abilities]


def unspent_points(structure, level, aptitudes):
    """{category: budget points not spent}, empty with no aptitudes."""
    if aptitudes is None:
        return {}
    left = dict(wakfu_aptitudes.budgets(structure, level))
    for ident, points in aptitudes.items():
        left[structure.aptitude_abilities[ident][0]] -= points
    return left


def preset_turns(structure, level, class_id, role):
    """(RoleTurns of a preset's role, {spell id: name}, class spells, mechanics, critical
    source), the turns each value of the role is read from."""
    from . import wakfu_presets, wakfu_turn

    critical, source = harvest_criticals(level)
    book = wakfu_turn.SpellBook(critical=critical)
    try:
        turns = wakfu_presets.build_turns(book, class_id, level, role)
        return (turns, book.names(class_id), book.spells(class_id, level),
                book.class_mechanics(class_id), source)
    finally:
        book.close()


def preset_class_turn(spells, role, totals, mechanics):
    """The class's best damage turn for a role with a damage share, None without one; a
    mixed reach reports the better of the two."""
    from . import wakfu_turn

    if 'damage' not in role.shares:
        return None
    reaches = ('melee', 'distance') if role.reach == 'mixed' else (role.reach,)
    return max((wakfu_turn.best_turn(spells, role._replace(reach=reach), totals,
                                     class_mechanics=mechanics) for reach in reaches),
               key=lambda found: found.damage)


def damage_floor_of(preset, content):
    """The floor share of a damage preset, None for any other preset or none."""
    from . import wakfu_presets
    if preset not in wakfu_presets.DAMAGE_PRESETS:
        return None
    return wakfu_value.rule('damage_floor')[content]


def solve_build(structure, *, level, elements, reach, class_id=None,
                forbidden=(), locked=(), allow_legacy=False, movement=None, seconds=90,
                defense=None, rounds=5, on_class_turn=True, state=None,
                aptitudes=SOLVE, battleground=False, pet_level=None,
                mount_level=None, item_levels=None, runes=wakfu_runes.OPTIMISTIC,
                rune_tier=None, sublimations=wakfu_sublimations.OPTIMISTIC,
                passives=wakfu_sublimations.SOLVE, opt_in=None, preset=None,
                content='pvm'):
    """Best legal set for a role within `seconds` of wall time.

    Without a preset the role is a damage dealer: elements (1 to 4 of fire, water, earth,
    air) and reach ('distance' or 'melee') are required, ValueError otherwise. With a
    preset (a key of wakfu_presets.PRESETS) the role comes from the registry for class_id
    at the level and content ('pvm' or 'pvp'): elements are required except for the mule
    (pass ()), reach is None and defense is None (the preset's own), and the class turns of every
    component the preset shares in price the value. locked: (item id, position or
    None) pairs; a lock the rules cannot honour raises ValueError.
    class_id: Ankama class id; its best turn is reported, and the solve prices
    every AP total by that turn unless on_class_turn is false. state: a
    wakfu_criteria.PlayerState, the game's start values by default; a piece
    whose player-state condition it fails stays out of the solve. Raises
    WakfuIllegalSet rather than return a set that breaks a rule.

    aptitudes: SOLVE lets the solver spread the points of every category, a
    dict {ability id: points} fixes them (ValueError when one breaks a cap or
    a budget), None leaves aptitudes out. battleground: the set bonus tiers of
    the build's bracket count.

    pet_level, mount_level: the level the pet and the mount are worn at, the
    highest each allows when none is given. item_levels: {item id: level} for
    single items. A level that cannot be worn raises ValueError.

    runes: 'optimistic' fills every socket of the worn pieces with the runes the solver
    picks, 'none' leaves them out. rune_tier: the highest tier a socket may hold, the
    one its piece's level allows when None; 0 is the same as 'none'. A mode outside
    wakfu_runes.MODES or a tier the rune table lacks raises ValueError.

    sublimations: 'optimistic' lets the solver place a sublimation in every position whose
    pieces have the sockets, 'none' counts only the states the worn pieces carry, None
    leaves them out as before. passives: 'solve' picks the passives of class_id that the
    level opens (with no class none are taken, and a warning says so), 'none' takes none.
    opt_in: {family: rate} with families E to H and rates in [0, 1]; ValueError otherwise.
    """
    started = time.monotonic()
    deadline = started + seconds
    wakfu_sublimations.read_options(structure, sublimations, passives)
    opt_in = wakfu_sublimations.read_opt_in(opt_in)
    notes = []
    if passives == wakfu_sublimations.SOLVE and not class_id:
        passives = wakfu_sublimations.NONE
        notes.append(('PASSIVES', 'passives need a class, none were taken'))
    rune_mode, rune_tier = wakfu_runes.read_options(structure, runes, rune_tier)
    levels = wakfu_companions.read_levels(structure, pet_level, mount_level,
                                          item_levels)
    state = state or wakfu_criteria.start_state()
    mode = _aptitude_mode(structure, level, aptitudes)
    if preset is None:
        role = make_role(elements, reach, defense, movement)
    else:
        if not class_id:
            raise ValueError('a preset needs a class')
        if not on_class_turn:
            raise ValueError('a preset is valued on the class turns')
        if reach is not None or defense is not None:
            raise ValueError('reach and defense come from the preset')
        from . import wakfu_presets
        role = wakfu_presets.role(class_id, preset, elements or (), level, content)
        if movement is not None:
            role = role._replace(movement=movement)
    if movement is not None and not class_id:
        raise ValueError('movement needs a class')
    forbidden, locked, legacy = _set_up(structure, forbidden, locked, allow_legacy)

    turn = names = mechanics = None
    not_counted = _system_notes(sublimations, passives) + _rune_notes(structure, rune_mode)
    if mode is None:
        not_counted.append('aptitudes')
    else:
        not_counted.extend(aptitude_notes(structure, level, battleground))
    if class_id and preset is not None:
        turn, names, spells, mechanics, _source = preset_turns(
            structure, level, class_id, role)
        ceiling = wakfu_value.resource_ceiling(
            wakfu_criteria.base_values(structure, class_id))
        if 'damage' in role.shares and turn.damage(ceiling) <= 0:
            raise ValueError(
                'class %d has no damage turn for %s at %s, even with AP, MP and '
                'WP at their caps' % (class_id, '+'.join(role.elements), role.reach))
        if 'heal' in role.shares and turn.models['heal'].damage(ceiling) <= 0:
            raise ValueError('class %d has no heal turn for %s at level %d'
                             % (class_id, '+'.join(role.elements), level))
    elif class_id:
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

    floor_share = damage_floor_of(preset, content)
    if floor_share is not None or wakfu_value.picks_sublimations_or_passives(
            sublimations, passives):
        deadline -= min(wakfu_value.FINISH_SECONDS, seconds / 10)
    model = wakfu_value.solve(structure, level, role, forbidden, rounds, turn=turn,
                              locked=locked, deadline=deadline, class_id=class_id or None,
                              state=state, aptitudes=aptitudes, battleground=battleground,
                              levels=levels, runes=rune_mode, rune_tier=rune_tier,
                              sublimations=sublimations, passives=passives, opt_in=opt_in,
                              damage_floor=floor_share)
    unlocks = _unlocks(structure, level, class_id or None, forbidden, state)
    best = model.best
    if best is not None:
        bound = (None if model.damage_floor is None or not model.damage_top
                 else (1 - model.damage_floor) * model.damage_top)

        def landing(one):
            return wakfu_value.best_landing(
                structure, level, role, one, turn, locked, class_id or None, state, aptitudes,
                battleground, levels, rune_mode, rune_tier, sublimations, passives, opt_in,
                least_damage=bound)

        landed = landing(best)
        before = model.pre_floor
        if before is not None:
            before = landed if before is best else landing(before)
        rounds = tuple(landed if one is best else one for one in model.rounds)
        model = model._replace(best=landed, rounds=rounds, pre_floor=before)
        best = landed
    modes = {'sublimation_mode': sublimations, 'passive_mode': passives, 'opt_in': opt_in}
    if best is None:
        return WakfuResult(None, None, None, None, None, False, len(model.rounds),
                           time.monotonic() - started, tuple(not_counted),
                           model.reason or INFEASIBLE, None, model, len(legacy), turn,
                           state, unlocks, {}, mode, {}, (), {}, {}, rune_mode, rune_tier,
                           warnings=tuple(notes), **modes)

    held = None if mode is None else dict(best.worn.aptitudes)
    landing = best.build.where_the_spread_lands(best.worn)
    best.worn.spread_landing = landing
    _checked(structure, level, best.worn, forbidden, locked,
             role.minimums(wakfu_criteria.base_values(structure, class_id or None)),
             class_id or None, state, held, battleground, rune_tier, landing)
    class_turn = None
    if class_id and preset is not None:
        class_turn = preset_class_turn(spells, role, best.totals, mechanics)
        if class_turn is not None:
            names = dict(names)
            names.update((spell.id, spell.name) for spell in spells)
            not_counted.extend(turn_notes(class_turn, names))
    elif class_id:
        from . import wakfu_turn
        spells = class_spells(level, class_id)[0]
        class_turn = wakfu_turn.best_turn(spells, role, best.totals,
                                          class_mechanics=mechanics)
        names = dict(names)
        names.update((spell.id, spell.name) for spell in spells)
        not_counted.extend(turn_notes(class_turn, names))
    not_counted.extend(_leaf_notes(best.worn))
    notes.extend(wakfu_legality.warnings(
        structure, level, best.worn, class_id or None, held, battleground,
        best.worn.levels, spread=landing))
    worn = best.worn
    return WakfuResult(worn, best.totals, best.value, class_turn,
                       worn.status, model.converged, len(model.rounds),
                       time.monotonic() - started, tuple(not_counted), None,
                       best.build, model, len(legacy), turn, state, unlocks,
                       dict(worn.aptitudes), mode,
                       unspent_points(structure, level, held),
                       tuple(worn.set_tiers), dict(worn.levels),
                       dict(worn.runes), rune_mode, rune_tier,
                       dict(worn.sublimations or {}), dict(worn.specials or {}),
                       dict(worn.states), tuple(worn.passives or ()),
                       wakfu_sublimations.slots_open(level)
                       if passives == wakfu_sublimations.SOLVE else 0,
                       settled_by=model.settled_by, gap=model.gap,
                       sheet_totals=dict(worn.sheet_totals), warnings=tuple(notes), **modes)


def solve_weights(structure, *, level, weights, forbidden=(), locked=(),
                  allow_legacy=False, seconds=90, class_id=None, state=None,
                  aptitudes=SOLVE, battleground=False, pet_level=None,
                  mount_level=None, item_levels=None, runes=wakfu_runes.OPTIMISTIC,
                  rune_tier=None):
    """Best legal set for hand-written weights, within `seconds`.

    aptitudes, battleground, the levels, runes and rune_tier: as in solve_build.
    """
    started = time.monotonic()
    rune_mode, rune_tier = wakfu_runes.read_options(structure, runes, rune_tier)
    levels = wakfu_companions.read_levels(structure, pet_level, mount_level,
                                          item_levels)
    state = state or wakfu_criteria.start_state()
    mode = _aptitude_mode(structure, level, aptitudes)
    not_counted = list(SYSTEMS_NOT_COUNTED) + _rune_notes(structure, rune_mode)
    if mode is None:
        not_counted.append('aptitudes')
    else:
        not_counted.extend(aptitude_notes(structure, level, battleground))
    forbidden, locked, legacy = _set_up(structure, forbidden, locked, allow_legacy)
    unlocks = _unlocks(structure, level, class_id, forbidden, state)
    build = WakfuBuild(structure, level, weights, forbidden, locked=locked,
                       class_id=class_id, state=state, aptitudes=aptitudes,
                       battleground=battleground, levels=levels, runes=rune_mode,
                       rune_tier=rune_tier)
    worn = build.build().solve(started + seconds)
    seconds_used = time.monotonic() - started
    if worn is None:
        return WakfuResult(None, None, None, None, None, False, 1, seconds_used,
                           tuple(not_counted), build.reason or INFEASIBLE, build,
                           None, len(legacy), None, state, unlocks, {}, mode, {}, (),
                           {}, {}, rune_mode, rune_tier)
    held = None if mode is None else dict(worn.aptitudes)
    _checked(structure, level, worn, forbidden, locked, None, class_id, state, held,
             battleground, rune_tier)
    return WakfuResult(worn, build.totals(worn), None, None, worn.status, True, 1,
                       seconds_used, tuple(not_counted), None, build, None,
                       len(legacy), None, state, unlocks, dict(worn.aptitudes), mode,
                       unspent_points(structure, level, held), tuple(worn.set_tiers),
                       dict(worn.levels), dict(worn.runes), rune_mode, rune_tier)
