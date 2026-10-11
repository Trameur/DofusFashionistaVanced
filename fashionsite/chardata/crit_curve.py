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

"""What a crit point and a critical damage point are worth in the best turn of the first set of a two-solve run.

The turn is read where a throw reaches a certain crit (100 less its rate) and the slopes between those crits
become the hinges of the objective. The set wears the weapon the weapon terms rank first, or the best of the
first three for a class that asks for it. One turn, one target, no effect triggered by a critical, no critical
resistance. Dofus 3 at level 200 is the only scope the bench covers.
"""

import copy
import logging
import pickle
from collections import namedtuple

from chardata.smart_build import (RACE_PROFILE_OVERRIDES_BY_VERSION, get_char_aspects, get_elements,
                                  get_standard_weights)
from chardata.stats_weights import get_stats_weights
from chardata.weapon_terms import CHARACTERISTIC_STEP, TurnReader, stat_lines_value
from fashionistapulp.item_effects import played_characteristics
from fashionistapulp.structure import get_structure

logger = logging.getLogger(__name__)

VERSIONS = ('dofus3',)
SCOPE_LEVEL = 200
CERTAIN = 100
TOLERANCE = 1e-9
DIGITS = 6
ANCHORS = ('top_weapon', 'weapon_envelope')
ENVELOPE_WIDTH = 3
BALANCED = 'balanced'
ALL_PRESETS = 'all_presets'

#: ch is the weight of a crit point up to the first break and hinges are ((crit, drop in the weight above it), ...),
#: cridam is the weight of a critical damage point; each is None or empty when the weight of the build stays
CritReading = namedtuple('CritReading', 'ch hinges cridam')


def crit_breakpoints(castables):
    """{0} and {100 - rate} for the damaging throws that can crit short of certainty."""
    points = {0}
    for castable in castables:
        rate = getattr(castable, 'crit_rate', 0) or 0
        if 0 < rate < CERTAIN and getattr(castable, 'plain_alternatives', None):
            points.add(CERTAIN - rate)
    return sorted(points)


def concave_hull(points):
    """Upper concave envelope of (x, y) points, cut at the first vertex that reaches the top.

    A point on or under the chord of its neighbours is dropped; what is left has strictly falling slopes.
    """
    out = []
    for point in sorted(points):
        while len(out) >= 2:
            (x1, y1), (x2, y2) = out[-2], out[-1]
            left = (y2 - y1) * (point[0] - x1)
            right = (point[1] - y1) * (x2 - x1)
            if left <= right + TOLERANCE * max(1.0, abs(left), abs(right)):
                out.pop()
            else:
                break
        out.append(point)
    top = max(y for _x, y in out)
    cut = next(i for i, (_x, y) in enumerate(out) if y >= top - TOLERANCE * max(1.0, abs(top)))
    return out[:cut + 1]


def slopes_of(points):
    return [(y2 - y1) / float(x2 - x1) for (x1, y1), (x2, y2) in zip(points, points[1:])]


class SetView(object):
    """One set read by the turn reader: the best turn at an absolute crit."""

    def __init__(self, reader, worn, stats):
        self.reader = reader
        self.worn = worn
        self.crit = stats.get('ch', 0) or 0
        self.cridam = stats.get('cridam', 0) or 0
        self.breaks = crit_breakpoints(list(reader.spells) + ([worn] if worn is not None else []))
        self._turns = {}

    def turn(self, crit, cridam=None):
        cridam = self.cridam if cridam is None else cridam
        if (crit, cridam) not in self._turns:
            self._turns[(crit, cridam)] = self.reader.full(
                self.worn, {'ch': crit - self.crit, 'cridam': cridam - self.cridam})
        return self._turns[(crit, cridam)]

    def per_point(self, played):
        base = self.reader.full(self.worn)
        raised = self.reader.full(self.worn, {key: CHARACTERISTIC_STEP for key in played})
        return (raised - base) / float(CHARACTERISTIC_STEP * len(played))


class EnvelopeView(object):
    """The best of several sets at each crit: the turn is the highest of theirs and the breaks are all of theirs."""

    def __init__(self, views):
        self.views = list(views)
        self.breaks = sorted({crit for view in self.views for crit in view.breaks})

    def turn(self, crit, cridam=None):
        return max(view.turn(crit, cridam) for view in self.views)

    def per_point(self, played):
        return self.views[0].per_point(played)


def _style_of(aspects, game_version):
    from chardata.presets import STYLE_BY_KEY, VERSION_PRESETS
    for key in VERSION_PRESETS[game_version]['styles']:
        if STYLE_BY_KEY[key].aspects <= set(aspects):
            return key
    return BALANCED


def class_reading(char_class, aspects, game_version='dofus3'):
    """The entry {'anchor', 'scale'} of the class table for these elements and this style, {} for the default.

    One element played: the entry of that element. Several: the entry of their sorted combination ('agi/int'). Then
    'all'. The value of an entry is by style of the version, balanced when none is set, or for 'all_presets'.
    """
    by_class = RACE_PROFILE_OVERRIDES_BY_VERSION.get(game_version, {}).get(char_class) or {}
    elements = sorted(get_elements(aspects))
    keys = ([elements[0]] if len(elements) == 1 else ['/'.join(elements)]) if elements else []
    for key in keys + ['all']:
        reading = (by_class.get(key) or {}).get('crit_reading')
        value = reading and (reading.get(_style_of(aspects, game_version)) or reading.get(ALL_PRESETS))
        if value:
            return value
    return {}


def _hull_of(view, cridam):
    return concave_hull([(crit, view.turn(crit, cridam)) for crit in view.breaks])


def _first_break(hull):
    return hull[1][0] if len(hull) > 1 else CERTAIN


def _cridam_gain(view, crit, cridam):
    return (view.turn(crit, cridam + CHARACTERISTIC_STEP) - view.turn(crit, cridam)) / float(CHARACTERISTIC_STEP)


def read_curve(view, weights, first=None, price_break=None, priced=True, scale=1.0):
    """The weight of a crit point on the first slope, the hinges above it and the weight of a critical damage point.

    `first` is the first set when the view is read on another weapon, the turn is read at its critical damage. A
    critical damage point is priced at the mean of its gain at the crit of the first set and at the crit
    `price_break`, the first break of the view when None. `scale` multiplies the slopes and the price. Without a
    slope the crit weight stays; None when no characteristic is played or none pays.
    """
    played = played_characteristics(weights)
    if not played:
        return None
    per_point = view.per_point(played)
    if per_point <= 0:
        return None
    first = first or view
    paid = sum(weights.get(key, 0) for key in played) / float(len(played))
    hull = _hull_of(view, first.cridam)
    cridam = None
    if priced:
        top = _first_break(hull) if price_break is None else price_break
        gain = scale * (_cridam_gain(view, first.crit, first.cridam) + _cridam_gain(view, top, first.cridam)) / 2.0
        cridam = round(gain / per_point * paid, DIGITS)
    slopes = [scale * value / per_point * paid for value in slopes_of(hull)]
    if not any(value > 0 for value in slopes):
        return CritReading(None, (), cridam) if cridam is not None else None
    follows = slopes[1:] + [0.0]
    return CritReading(round(slopes[0], DIGITS),
                       tuple((hull[k + 1][0], round(slopes[k] - follows[k], DIGITS))
                             for k in range(len(slopes))),
                       cridam)


def _engine_weighs(char, aspects):
    """(whether the engine weighs the crit of the build, whether it weighs its critical damage).

    Neither under a crit aspect or a weight picked by hand; the weight of an old floor counts as the engine's.
    """
    if aspects & {'crit', 'noncrit'}:
        return False, False
    stored = get_stats_weights(char, persist=False)
    engine = get_standard_weights(char)
    crit = stored.get('ch') == engine.get('ch') or 'ch_before_floor' in stored
    return crit, crit and stored.get('cridam') == engine.get('cridam')


def _solution_of(char, result):
    from chardata.solution import get_solution_from_minimal
    try:
        return get_solution_from_minimal(char, pickle.loads(pickle.dumps(result)),
                                         refresh_base_stats=False)
    except Exception:
        logger.exception('could not read the first set of char %s for the crit curve',
                         getattr(char, 'id', '?'))
        return None


def _set_view(char, solution):
    """The set read by the turn reader, None without AP or spells."""
    from chardata.spell_combo import castable_spells, combat_ap
    from chardata.spell_modifiers import worn_spell_modifiers
    from chardata.spells_view import _weapon_castable
    from chardata.temporix_mode import solution_uses_temporix
    stats = dict(solution.get_stats_total())
    game_version = char.game_version
    ap = combat_ap(stats.get('ap'), game_version,
                   temporix=solution_uses_temporix(solution, game_version))
    spells = castable_spells(char.char_class, char.level, game_version,
                             modifiers=worn_spell_modifiers(solution, game_version))
    if not ap or not spells:
        return None
    return SetView(TurnReader(stats, spells, ap, game_version, char.level),
                   _weapon_castable(solution), stats)


def ranked_weapons(terms, model_input, game_version):
    """The weapons the objective of the second solve ranks first, best first: the term plus the value of the stat lines.

    A forbidden weapon is left out and the first of equal values stays ahead.
    """
    structure = get_structure(game_version)
    weights = model_input.objective_values
    forbidden = model_input.forbidden_equips or ()
    values = {item_id: term + stat_lines_value(structure.get_item_by_id(item_id), weights, structure)
              for item_id, term in terms.items() if item_id not in forbidden}
    return sorted(values, key=values.get, reverse=True)


def top_weapon(terms, model_input, game_version):
    ranked = ranked_weapons(terms, model_input, game_version)
    return ranked[0] if ranked else None


def _swappable(model_input):
    return not ('weapon' in (model_input.empty_slot_types or []) or (model_input.locked_equips or {}).get('weapon'))


def _with_weapon(char, result, item_id):
    """The first set wearing the weapon `item_id`, None if it cannot be read."""
    swapped = copy.copy(result)
    swapped.item_per_slot = dict(result.item_per_slot, weapon=item_id)
    return _solution_of(char, swapped)


def anchor_solution(char, result, solution, terms, model_input):
    """The first set wearing the weapon the terms rank first, `solution` if none can be swapped in."""
    if not terms or not _swappable(model_input):
        return solution
    top = top_weapon(terms, model_input, char.game_version)
    if top is None or top == result.item_per_slot.get('weapon'):
        return solution
    return _with_weapon(char, result, top) or solution


def envelope_view(char, result, first, terms, model_input):
    """The best of the sets wearing each of the first weapons the terms rank, `first` if none can be swapped in."""
    if not terms or not _swappable(model_input):
        return first
    worn = result.item_per_slot.get('weapon')
    views = []
    for item_id in ranked_weapons(terms, model_input, char.game_version)[:ENVELOPE_WIDTH]:
        view = first
        if item_id != worn:
            solution = _with_weapon(char, result, item_id)
            view = _set_view(char, solution) if solution is not None else None
        if view is not None:
            views.append(view)
    return EnvelopeView(views) if len(views) > 1 else (views[0] if views else first)


def crit_hinges(char, result, model_input, terms=None):
    """The crit curve and the critical damage price read on the first set `result` wearing the top weapon of `terms`.

    None when the build is out of scope. The turn is read at the critical damage of the first set, and the
    critical damage point is priced up to the first break of that set. The class table of the version can read the
    best of the first weapons instead and scale the reading.
    """
    if result is None or getattr(char, 'game_version', None) not in VERSIONS:
        return None
    aspects = get_char_aspects(char)
    weighs_crit, weighs_cridam = _engine_weighs(char, aspects)
    if char.level < SCOPE_LEVEL or not weighs_crit:
        return None
    solution = _solution_of(char, result)
    first = _set_view(char, solution) if solution is not None else None
    if first is None:
        return None
    entry = class_reading(char.char_class, aspects, char.game_version)
    scale = entry['scale']['value'] if 'scale' in entry else 1.0
    price_break = None
    if entry.get('anchor') == 'weapon_envelope':
        view = envelope_view(char, result, first, terms, model_input)
    else:
        anchor = anchor_solution(char, result, solution, terms, model_input)
        view = first if anchor is solution else (_set_view(char, anchor) or first)
        if weighs_cridam and view is not first:
            price_break = _first_break(_hull_of(first, first.cridam))
    return read_curve(view, model_input.objective_values, first, price_break, weighs_cridam, scale)
