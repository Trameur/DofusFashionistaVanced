"""What each version's potions, engravings and shards do to a weapon's neutral lines."""
import copy
import json
import os
from functools import lru_cache

from .dofus_constants import (AIR, DAMAGE_TYPES, EARTH, FIRE, NEUTRAL,
                              NON_ELEMENTAL_HIT_TYPES, WATER, calculate_damage)
from .game_versions import get_game_version

_DIRECTORY = os.path.join(os.path.dirname(__file__), 'weapon_conversions')
KINDS = ('damage', 'steal', 'heal')
TIERS = ('strong', 'medium', 'weak')
STRONG = TIERS[0]
ELEMENTS = (EARTH, FIRE, WATER, AIR)
FALLBACK_LANGUAGE = 'en'


@lru_cache(maxsize=None)
def _table(version):
    path = os.path.join(_DIRECTORY, '%s.json' % version)
    if not os.path.isfile(path):
        return {'game_version': version, 'languages': [], 'conversions': [],
                'gems': [], 'unforgeable': []}
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def _unforgeable(version):
    ids = _table(version).get('unforgeable')
    return None if ids is None else frozenset(ids)


def load(version):
    """The version's stored table, as a copy the caller may change."""
    return copy.deepcopy(_table(version))


def kinds(version):
    present = {row['kind'] for row in _table(version)['conversions']}
    return tuple(kind for kind in KINDS if kind in present)


def tiers(version, kind):
    present = {row['tier'] for row in _table(version)['conversions']
               if row['kind'] == kind}
    return tuple(tier for tier in TIERS if tier in present)


def rate(version, kind, tier):
    """Share of the roll kept, None when absent or unpublished."""
    for row in _table(version)['conversions']:
        if row['kind'] == kind and row['tier'] == tier:
            return row['rate']
    return None


def applied_rate(version, kind, tier):
    found = rate(version, kind, tier)
    if (found is None and tier == STRONG and kind in kinds(version)
            and not _table(version).get('rate_published', True)):
        return get_game_version(version).weapon_element_rate
    return found


def rate_published(version):
    return _table(version).get('rate_published', True)


def offered_tiers(version, kind):
    return tuple(tier for tier in tiers(version, kind)
                 if applied_rate(version, kind, tier) is not None)


def percent(version, kind, tier):
    found = applied_rate(version, kind, tier)
    return None if found is None else int(round(found * 100))


def row(version, kind, element, tier):
    for entry in _table(version)['conversions']:
        if (entry['kind'], entry['element'], entry['tier']) == (kind, element, tier):
            return entry
    return None


def offer(version, kind):
    return [(element, tier) for tier in offered_tiers(version, kind)
            for element in ELEMENTS if row(version, kind, element, tier) is not None]


def item_name(version, kind, element, tier, language):
    found = row(version, kind, element, tier)
    if found is None:
        return None
    return found['names'].get(language) or found['names'].get(FALLBACK_LANGUAGE)


def can_forge(version, ankama_id):
    if not kinds(version):
        return False
    unforgeable = _unforgeable(version)
    return unforgeable is None or ankama_id not in unforgeable


def name(version, ankama_id, language):
    table = _table(version)
    for row in table['conversions'] + table['gems']:
        if row['ankama_id'] == ankama_id:
            return row['names'].get(language) or row['names'].get(FALLBACK_LANGUAGE)
    return None


def kind_of(hit):
    if hit.element != NEUTRAL:
        return None
    if hit.steals:
        return 'steal'
    if hit.heals:
        return 'heal'
    return 'damage'


def convert(hit, element, rate):
    converted = copy.copy(hit)
    converted.min_dam = int((hit.min_dam - 1) * rate + 1)
    converted.max_dam = max(converted.min_dam,
                            int((hit.min_dam - 1) * rate)
                            + int((hit.max_dam - hit.min_dam + 1) * rate))
    converted.element = element
    return converted


def _with_crit_bonus(hit, crit_bonus):
    critical = copy.copy(hit)
    if hit.element not in NON_ELEMENTAL_HIT_TYPES:
        critical.min_dam += crit_bonus
        critical.max_dam += crit_bonus
    return critical


def compose(base_hits, crit_bonus, choice):
    """(hits, crit_hits) once choice, {kind: (element, rate)}, converts the lines of its kinds."""
    hits = []
    for hit in base_hits:
        conversion = choice.get(kind_of(hit))
        hits.append(convert(hit, *conversion) if conversion else copy.copy(hit))
    if crit_bonus is None:
        return hits, None
    return hits, [_with_crit_bonus(hit, crit_bonus) for hit in hits]


def convertible(version, ankama_id, base_hits):
    if not can_forge(version, ankama_id):
        return ()
    present = {kind_of(hit) for hit in base_hits}
    return tuple(kind for kind in kinds(version)
                 if kind in present and applied_rate(version, kind, STRONG) is not None)


def _worth(hits, char_stats):
    return sum(hit.average() for hit in calculate_damage(hits, char_stats,
                                                          critical_hit=False,
                                                          is_spell=False))


def best_element(base_hits, kind, rate, char_stats):
    own = [hit for hit in base_hits if kind_of(hit) == kind]
    best, best_worth = NEUTRAL, None
    for element in DAMAGE_TYPES:
        hits = own if element == NEUTRAL else [convert(hit, element, rate) for hit in own]
        worth = _worth(hits, char_stats)
        if best_worth is None or worth > best_worth:
            best, best_worth = element, worth
    return best


def choose(version, ankama_id, base_hits, char_stats, override=None):
    override = override or {}
    chosen = {}
    for kind in convertible(version, ankama_id, base_hits):
        if kind in override:
            entry = override[kind]
            if entry is None:
                chosen[kind] = (NEUTRAL, STRONG)
            else:
                element, tier = entry
                if applied_rate(version, kind, tier) is None:
                    tier = STRONG
                chosen[kind] = (element, tier)
            continue
        chosen[kind] = (best_element(base_hits, kind,
                                     applied_rate(version, kind, STRONG), char_stats),
                        STRONG)
    return chosen


def compose_tabs(version, base_hits, crit_bonus, chosen):
    fixed = {kind: (element, applied_rate(version, kind, tier))
             for kind, (element, tier) in chosen.items()
             if kind != 'damage' and element != NEUTRAL}
    damage = chosen.get('damage')
    if damage is None:
        hits, critical = compose(base_hits, crit_bonus, fixed)
        return ({element: hits for element in DAMAGE_TYPES},
                None if critical is None else {element: critical for element in DAMAGE_TYPES})
    damage_rate = applied_rate(version, 'damage', damage[1])
    hits_by, critical_by = {}, {}
    for element in DAMAGE_TYPES:
        choice = dict(fixed)
        if element != NEUTRAL:
            choice['damage'] = (element, damage_rate)
        hits_by[element], critical_by[element] = compose(base_hits, crit_bonus, choice)
    return hits_by, None if crit_bonus is None else critical_by


def read_choice(text):
    try:
        stored = json.loads(text) if text else {}
    except ValueError:
        return {}
    if not isinstance(stored, dict):
        return {}
    choice = {}
    for kind, entry in stored.items():
        if kind not in KINDS:
            continue
        if entry is None:
            choice[kind] = None
        elif (isinstance(entry, list) and len(entry) == 2
              and entry[0] in ELEMENTS and entry[1] in TIERS):
            choice[kind] = (entry[0], entry[1])
    return choice


def read_option(version, kind, text):
    element, _sep, tier = (text or '').partition(':')
    if (element, tier) in offer(version, kind):
        return element, tier
    return None


def write_option(element, tier):
    return '%s:%s' % (element, tier)


def applied(chosen):
    chosen = chosen or {}
    return [(kind, chosen[kind][0], chosen[kind][1]) for kind in KINDS
            if kind in chosen and chosen[kind][0] != NEUTRAL]


def write_choice(choice):
    if not choice:
        return ''
    return json.dumps({kind: None if entry is None else list(entry)
                       for kind, entry in choice.items()}, sort_keys=True)
