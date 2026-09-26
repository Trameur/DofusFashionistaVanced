# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What worn items change on a spell, from spell_modifiers/<version>.json."""
import copy
import json
import os

from fashionistapulp.dofus_constants import NON_ELEMENTAL_HIT_TYPES

_DIRECTORY = os.path.join(os.path.dirname(__file__), 'spell_modifiers')
_CACHE = {}

APPLIED_KINDS = ('ap_cost', 'per_turn', 'per_target', 'cooldown',
                 'cooldown_set', 'critical', 'damage', 'base_damage', 'heals',
                 'min_range', 'max_range')

STAT_OF_KIND = {'critical': 'ch', 'damage': 'dam', 'heals': 'heals'}


class SpellModifier(object):
    """One row of one worn item on one spell; amount carries the sign."""

    def __init__(self, kind, amount, item_name, item_id=None):
        self.kind = kind
        self.amount = amount
        self.item_name = item_name
        self.item_id = item_id

    def __repr__(self):
        return '<SpellModifier %s %+d %s>' % (self.kind, self.amount,
                                              self.item_name)


def spell_modifier_table(game_version):
    """The version's file, empty when it has none."""
    if game_version not in _CACHE:
        path = os.path.join(_DIRECTORY, '%s.json' % game_version)
        try:
            with open(path, encoding='utf-8') as handle:
                _CACHE[game_version] = json.load(handle)
        except (IOError, OSError, ValueError):
            _CACHE[game_version] = {}
    return _CACHE[game_version]


def item_spell_modifiers(game_version, ankama_id):
    """[(spell id, kind, signed amount)] the site applies for one item."""
    table = spell_modifier_table(game_version)
    effects = table.get('effects') or {}
    out = []
    for spell_id, effect_id, value in ((table.get('items') or {})
                                       .get(str(ankama_id)) or []):
        entry = effects.get(str(effect_id)) or {}
        kind = entry.get('kind')
        if kind not in APPLIED_KINDS or value is None:
            continue
        sign = entry.get('sign') or 0
        out.append((spell_id, kind, value * sign if sign else value))
    return out


def worn_spell_modifiers(solution, game_version):
    """{spell id: [SpellModifier, ...]} for the pieces a solution wears."""
    out = {}
    seen = set()
    for pieces in (getattr(solution, 'items', None) or {}).values():
        for piece in pieces or []:
            if not getattr(piece, 'item_added', False):
                continue
            if getattr(piece, 'ankama_type', None) not in (None, 'equipment'):
                continue
            ankama_id = getattr(piece, 'ankama_id', None)
            if ankama_id is None or ankama_id in seen:
                continue
            seen.add(ankama_id)
            name = getattr(piece, 'localized_name', None) or piece.name
            for spell_id, kind, amount in item_spell_modifiers(game_version,
                                                               ankama_id):
                out.setdefault(spell_id, []).append(
                    SpellModifier(kind, amount, name, ankama_id))
    return out


def modified_cast(cost, per_turn, per_target, cooldown, modifiers):
    """(cost, per turn, per target, cooldown) once the modifiers apply."""
    for modifier in modifiers or ():
        if modifier.kind == 'ap_cost' and cost:
            cost = max(1, cost + modifier.amount)
        elif modifier.kind == 'per_turn' and per_turn:
            per_turn = per_turn + modifier.amount
        elif modifier.kind == 'per_target' and per_target:
            per_target = per_target + modifier.amount
        elif modifier.kind == 'cooldown' and cooldown:
            cooldown = max(0, cooldown + modifier.amount)
        elif modifier.kind == 'cooldown_set':
            cooldown = modifier.amount
    return cost, per_turn, per_target, cooldown


def modified_range(span, modifiers):
    """[min, max] range once the modifiers apply."""
    low, high = span
    for modifier in modifiers or ():
        if modifier.kind == 'min_range':
            low = max(0, low + modifier.amount)
        elif modifier.kind == 'max_range':
            high = high + modifier.amount
    return [low, max(low, high)]


def bonus_stats(modifiers):
    """Stats one spell gets from its modifiers, like {'ch': 30, 'dam': 5}."""
    out = {}
    for modifier in modifiers or ():
        stat = STAT_OF_KIND.get(modifier.kind)
        if stat:
            out[stat] = out.get(stat, 0) + modifier.amount
    return out


def base_damage_bonus(modifiers):
    return sum(modifier.amount for modifier in modifiers or ()
               if modifier.kind == 'base_damage')


def gets_base_damage(row):
    """A damage row: some damage, no heal, no buff, nothing the formula skips."""
    element = getattr(row, 'element', '') or ''
    return bool(row.min_dam or row.max_dam) and not (
        getattr(row, 'heals', False) or element.startswith('buff')
        or element in NON_ELEMENTAL_HIT_TYPES)


def raised_row(row, amount):
    """The row with its base damage raised, a copy; the row itself otherwise."""
    if not amount or not gets_base_damage(row):
        return row
    raised = copy.copy(row)
    raised.min_dam = row.min_dam + amount
    raised.max_dam = row.max_dam + amount
    return raised
