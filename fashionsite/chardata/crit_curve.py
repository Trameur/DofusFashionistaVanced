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

"""What a crit point is worth in the best turn of the first set of a two-solve run.

The turn is read where a throw reaches a certain crit (100 less its rate) and the slopes between those crits
become the hinges of the objective. One turn, one target, no effect triggered by a critical, no critical
resistance, and the weapon stays the one worn. Dofus 3 at level 200 is the only scope the bench covers.
"""

import logging
import pickle
from collections import namedtuple

from chardata.smart_build import get_char_aspects, get_standard_weights
from chardata.stats_weights import get_stats_weights
from chardata.weapon_terms import CHARACTERISTIC_STEP, TurnReader
from fashionistapulp.item_effects import played_characteristics

logger = logging.getLogger(__name__)

VERSIONS = ('dofus3',)
SCOPE_LEVEL = 200
TOLERANCE = 1e-9
DIGITS = 6

#: ch is the weight of a crit point up to the first break, hinges are ((crit, drop in the weight above it), ...)
CritReading = namedtuple('CritReading', 'ch hinges')


def crit_breakpoints(castables):
    """{0} and {100 - rate} for the damaging throws that can crit short of certainty."""
    points = {0}
    for castable in castables:
        rate = getattr(castable, 'crit_rate', 0) or 0
        if 0 < rate < 100 and getattr(castable, 'plain_alternatives', None):
            points.add(100 - rate)
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
        self.breaks = crit_breakpoints(list(reader.spells) + ([worn] if worn is not None else []))

    def turn(self, crit):
        return self.reader.full(self.worn, {'ch': crit - self.crit})

    def per_point(self, played):
        base = self.reader.full(self.worn)
        raised = self.reader.full(self.worn, {key: CHARACTERISTIC_STEP for key in played})
        return (raised - base) / float(CHARACTERISTIC_STEP * len(played))


def read_curve(view, weights):
    """The weight of a crit point on the first slope and the hinges above it; None when no crit point pays."""
    played = played_characteristics(weights)
    if not played:
        return None
    per_point = view.per_point(played)
    if per_point <= 0:
        return None
    paid = sum(weights.get(key, 0) for key in played) / float(len(played))
    hull = concave_hull([(crit, view.turn(crit)) for crit in view.breaks])
    slopes = [value / per_point * paid for value in slopes_of(hull)]
    if not any(value > 0 for value in slopes):
        return None
    follows = slopes[1:] + [0.0]
    return CritReading(round(slopes[0], DIGITS),
                       tuple((hull[k + 1][0], round(slopes[k] - follows[k], DIGITS))
                             for k in range(len(slopes))))


def _weighs_crit_itself(char):
    """Whether the engine weighs the crit of the build: no crit aspect and no weight picked by hand."""
    if get_char_aspects(char) & {'crit', 'noncrit'}:
        return False
    stored = get_stats_weights(char, persist=False)
    return stored.get('ch') == get_standard_weights(char).get('ch') or 'ch_before_floor' in stored


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


def crit_hinges(char, result, model_input):
    """The crit curve read on the first set `result`; None when the build is out of scope."""
    if result is None or getattr(char, 'game_version', None) not in VERSIONS:
        return None
    if char.level < SCOPE_LEVEL or not _weighs_crit_itself(char):
        return None
    solution = _solution_of(char, result)
    view = _set_view(char, solution) if solution is not None else None
    return read_curve(view, model_input.objective_values) if view is not None else None
