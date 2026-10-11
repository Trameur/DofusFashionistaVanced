# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The tuned weights of a version, weight_tables/<version>.json, and the step of _set_weights that reads them.

    py fashionsite/manage.py tune_weights --version dofus3 --out <folder outside the repository>
"""
import hashlib
import json
import logging
import os
from contextlib import contextmanager
from types import SimpleNamespace

from fashionistapulp.dofus_constants import CHARACTER_CLASSES, DAMAGE_TYPES, MAIN_STATS

logger = logging.getLogger(__name__)

DIRECTORY = os.path.join(os.path.dirname(__file__), 'weight_tables')
VERSIONS = ('dofus3',)
GRID_LEVEL = 200
BANDS = (str(GRID_LEVEL),)
ELEMENT_COUNTS = (1, 2)
SEPARATOR = '+'
SCENARIOS = ('plain', 'glasscannon', 'tank')
#: the aspects a scenario stands for, once element boxes, omni and balanced are set aside
SCENARIO_ASPECTS = {'plain': frozenset(), 'glasscannon': frozenset({'glasscannon'}),
                    'tank': frozenset({'vit', 'res'})}
NEUTRAL_ASPECTS = frozenset(MAIN_STATS) | {'omni', 'balanced'}

DAMAGE_STATS = ('dam', 'neutdam', 'earthdam', 'firedam', 'waterdam', 'airdam')
RESIST_STATS = tuple('%sresper' % kind for kind in DAMAGE_TYPES)
#: the stats the table reads, apart from the characteristic shares of a duo
TABLE_STATS = (('pow',) + DAMAGE_STATS + ('perspedam', 'perweadam', 'ap', 'hp', 'vit') + RESIST_STATS)
#: a duo's shares sit on its characteristics and sum to the number of elements
SHARE_STATS = tuple(MAIN_STATS)

_CACHE = {}
_OVERRIDES = {}
_DIGESTS = {}


def element_key(elements):
    """'str+int': the played elements in the order of MAIN_STATS."""
    return SEPARATOR.join(element for element in MAIN_STATS if element in elements)


def grid_element_sets():
    """The element sets of the grid, one and two elements, in the order of MAIN_STATS."""
    singles = [(element,) for element in MAIN_STATS]
    pairs = [(first, second) for index, first in enumerate(MAIN_STATS) for second in MAIN_STATS[index + 1:]]
    return singles + pairs


def weight_scenario(aspects, game_version):
    """The scenario of a build's aspects, None when the table does not cover them."""
    if game_version not in VERSIONS:
        return None
    others = frozenset(aspects) - NEUTRAL_ASPECTS
    for scenario in SCENARIOS:
        if others == SCENARIO_ASPECTS[scenario]:
            return scenario
    return None


def level_band(level):
    """The band of a level, None below the grid."""
    return str(GRID_LEVEL) if level is not None and level >= GRID_LEVEL else None


def load_weight_table(game_version):
    """The version's table, an override first, {} when it has none."""
    if game_version in _OVERRIDES:
        return _OVERRIDES[game_version]
    if not game_version or not game_version.isalnum():
        return {}
    if game_version not in _CACHE:
        path = os.path.join(DIRECTORY, '%s.json' % game_version)
        try:
            with open(path, encoding='utf-8') as handle:
                _CACHE[game_version] = json.load(handle)
        except (IOError, OSError, ValueError):
            _CACHE[game_version] = {}
    return _CACHE[game_version]


@contextmanager
def override_weight_table(game_version, table):
    """Reads `table` (None for no table) in place of the version's file while the block runs."""
    missing = object()
    previous = _OVERRIDES.get(game_version, missing)
    _OVERRIDES[game_version] = table or {}
    try:
        yield
    finally:
        if previous is missing:
            del _OVERRIDES[game_version]
        else:
            _OVERRIDES[game_version] = previous


def table_cell(char_class, aspects, level, game_version):
    """The shipped cell of a build, None when the table has none and the engine weighs it."""
    scenario = weight_scenario(aspects, game_version)
    band = level_band(level)
    if scenario is None or band is None:
        return None
    from chardata.smart_build import get_elements
    elements = get_elements(aspects)
    if len(elements) not in ELEMENT_COUNTS:
        return None
    table = load_weight_table(game_version)
    if not table:
        return None
    key = element_key(elements)
    cell = ((((table.get('cells') or {}).get(char_class) or {}).get(key) or {}).get(scenario) or {}).get(band)
    if not cell or cell.get('status') != 'shipped':
        logger.info('no weight cell for %s %s %s %s on %s: the engine weighs it', char_class, key, scenario, band,
                    game_version)
        return None
    return cell


def apply_weight_table(w, char, aspects, unit, tuning):
    """Writes the cell's ratios times `unit` over the engine's weights, returns the keys it wrote."""
    game_version = getattr(char, 'game_version', None) or 'dofus3'
    cell = table_cell(char.char_class, aspects, char.level, game_version)
    if cell is None or not unit:
        return []
    written = []
    zeroed = tuning.get('zero_stats', ())
    for stat, entry in (cell.get('ratios') or {}).items():
        if stat not in TABLE_STATS + SHARE_STATS or stat not in w or stat in zeroed or entry.get('weak'):
            continue
        value = entry.get('value')
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        w[stat] = value * unit
        written.append(stat)
    return written


def engine_weights(char_class, elements, scenario, game_version, level=GRID_LEVEL):
    """The weights the engine gives a grid build, the table left out."""
    from chardata.smart_build import _set_weights
    char = SimpleNamespace(char_class=char_class, level=level, game_version=game_version)
    return _set_weights(char, set(elements) | SCENARIO_ASPECTS[scenario], apply=False, table=False)


def unit_of(elements, scenario):
    """The weight of one played characteristic before the table: what a ratio multiplies."""
    from chardata.smart_build import ENGINE_PARAMS
    factor = ENGINE_PARAMS['attack_factor'][len(elements)]
    if scenario == 'glasscannon':
        factor *= ENGINE_PARAMS['glasscannon_attack']
    return factor * ENGINE_PARAMS['b']


def engine_ratios(char_class, elements, scenario, game_version):
    """{stat: the engine's weight over the unit} for the read stats, and a duo's equal shares."""
    weights = engine_weights(char_class, elements, scenario, game_version)
    unit = float(unit_of(elements, scenario))
    ratios = {stat: weights[stat] / unit for stat in TABLE_STATS}
    if len(elements) == 2:
        ratios.update({element: 1.0 for element in elements})
    return ratios


def engine_digest(game_version):
    """sha1 of the table-less weights of the grid and of ENGINE_PARAMS: it moves when the engine does."""
    from chardata.smart_build import ENGINE_PARAMS
    if game_version not in _DIGESTS:
        _DIGESTS[game_version] = _compute_engine_digest(game_version, ENGINE_PARAMS)
    return _DIGESTS[game_version]


def _compute_engine_digest(game_version, engine_params):
    digest = hashlib.sha1()
    digest.update(json.dumps(engine_params, sort_keys=True, default=list).encode('utf-8'))
    for char_class in CHARACTER_CLASSES:
        for elements in grid_element_sets():
            for scenario in SCENARIOS:
                weights = engine_weights(char_class, elements, scenario, game_version)
                digest.update(json.dumps([char_class, element_key(elements), scenario, sorted(weights.items())],
                                         default=repr).encode('utf-8'))
    return digest.hexdigest()


def cell_table(char_class, elements, scenario, ratios, band=BANDS[0]):
    """A table holding one shipped cell whose ratios all apply: what a tuning round feeds the door."""
    entries = {stat: {'value': value, 'weak': False} for stat, value in (ratios or {}).items()}
    cell = {'status': 'shipped', 'ratios': entries}
    return {'cells': {char_class: {element_key(elements): {scenario: {band: cell}}}}}
