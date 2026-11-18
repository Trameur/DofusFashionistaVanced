# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dracorune transformations of an item's stat lines, read from per-version JSON."""

import json
import os
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from . import weapon_forge
from .exo_options import forgeable_type

DEFAULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'dracorunes')

ELEMENT_PAIRS = (('str', 'earthdam'), ('int', 'firedam'),
                 ('cha', 'waterdam'), ('agi', 'airdam'))
STAT_TO_DAMAGE = dict(ELEMENT_PAIRS)
RESISTANCE_ELEMENTS = ('neut', 'earth', 'fire', 'water', 'air')
RESISTANCE_NAMES = {'neut': 'neutral', 'earth': 'earth', 'fire': 'fire',
                    'water': 'water', 'air': 'air'}

_ROUNDINGS = {'floor': ROUND_FLOOR, 'ceil': ROUND_CEILING,
              'round': ROUND_HALF_UP}


def load_runes(version, folder=None):
    """The version's rune data as a dict, or None when it has no file."""
    path = os.path.join(folder or DEFAULT_FOLDER, '%s.json' % version)
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    data.setdefault('runes', [])
    data.setdefault('item_types', [])
    data.setdefault('rounding', 'floor')
    data.setdefault('power_takes_neutral', False)
    return data


def eligible(item_type, runes):
    return bool(runes) and item_type in runes.get('item_types', ())


def eligible_item(type_name, weapon_key, ankama_id, version, runes):
    if not eligible(type_name, runes):
        return False
    if type_name != 'Weapon':
        return True
    return (forgeable_type(type_name, weapon_key)
            and weapon_forge.can_forge(version, ankama_id))


def _scaled(value, keep, rounding):
    mode = _ROUNDINGS[rounding]
    return int((Decimal(value) * Decimal(str(keep))).quantize(
        Decimal(1), rounding=mode))


def _lines(stats):
    lines = {}
    for key, value in stats:
        lines[key] = lines.get(key, 0) + value
    return lines


def _moved(lines, moves):
    """Lines with each (source, target) key move applied, targets adding up."""
    result = {}
    for key, value in lines.items():
        result[moves.get(key, key)] = result.get(moves.get(key, key), 0) + value
    return result


def _element_variants(lines, target):
    if target not in STAT_TO_DAMAGE:
        return
    target_damage = STAT_TO_DAMAGE[target]
    if target in lines or target_damage in lines:
        return
    for source, source_damage in ELEMENT_PAIRS:
        if source == target:
            continue
        if source not in lines and source_damage not in lines:
            continue
        yield ('element:%s>%s' % (source, target),
               _moved(lines, {source: target, source_damage: target_damage}))


def _resistance_variants(lines):
    for source in RESISTANCE_ELEMENTS:
        keys = [k for k in (source + 'res', source + 'resper') if k in lines]
        if not keys:
            continue
        for target in RESISTANCE_ELEMENTS:
            if target == source:
                continue
            if target + 'res' in lines or target + 'resper' in lines:
                continue
            moves = {source + 'res': target + 'res',
                     source + 'resper': target + 'resper'}
            yield ('resistance:%s>%s' % (RESISTANCE_NAMES[source],
                                         RESISTANCE_NAMES[target]),
                   _moved(lines, moves))


def _power_variant(lines, rune, runes):
    rounding = runes.get('rounding', 'floor')
    keep = rune['keep']
    damage_keys = [damage for _, damage in ELEMENT_PAIRS]
    if runes.get('power_takes_neutral'):
        damage_keys.append('neutdam')
    dropped_stats = [lines[k] for k, _ in ELEMENT_PAIRS if lines.get(k, 0) > 0]
    dropped_damage = [lines[k] for k in damage_keys if lines.get(k, 0) > 0]
    if not dropped_stats and not dropped_damage:
        return None
    pow_add = _scaled(max(dropped_stats), keep, rounding) if dropped_stats else 0
    dam_add = _scaled(max(dropped_damage), keep, rounding) if dropped_damage else 0
    result = {}
    placed = set()
    for key, value in lines.items():
        if value > 0 and key in STAT_TO_DAMAGE:
            slot, add = 'pow', pow_add
        elif value > 0 and key in damage_keys:
            slot, add = 'dam', dam_add
        else:
            result[key] = value
            continue
        if slot in placed or slot in lines:
            continue
        placed.add(slot)
        if add:
            result[slot] = add
    for slot, add in (('pow', pow_add), ('dam', dam_add)):
        if slot in lines and add:
            result[slot] = result[slot] + add
    return 'power', result


def variants(stats, runes):
    """Every legal draconized version of the lines, as (variant_key, new_stats)."""
    if not runes:
        return []
    lines = _lines(stats)
    original = _effective(lines)
    found = []
    for rune in runes.get('runes', ()):
        kind = rune.get('kind')
        if kind == 'element':
            found.extend(_element_variants(lines, rune.get('target')))
        elif kind == 'resistance':
            found.extend(_resistance_variants(lines))
        elif kind == 'power':
            one = _power_variant(lines, rune, runes)
            if one:
                found.append(one)
    seen = {original}
    by_key = {}
    out = []
    for key, result in found:
        signature = frozenset(result.items())
        if key in by_key:
            if by_key[key] != signature:
                raise ValueError('variant %s has two different results' % key)
            continue
        by_key[key] = signature
        effective = _effective(result)
        if effective in seen:
            continue
        seen.add(effective)
        out.append((key, list(result.items())))
    return out


def _effective(lines):
    return frozenset((k, v) for k, v in lines.items() if v != 0)
