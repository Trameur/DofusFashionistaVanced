# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the spell modifiers of each piece add to a build's best turn, priced in its objective.

A piece is worth its best_turn gain on a set of the build, at each AP from the one that set
reaches, times the lowest price the weights pay for a point of that turn through a damage stat.
"""

import copy
from itertools import combinations

from chardata.presets import ELEMENT_DAMAGE
from chardata.spell_combo import best_turn, castable_spells, combat_ap
from chardata.spell_modifiers import item_modifiers_by_spell, spell_modifier_table
from fashionistapulp.dofus_constants import get_stat_maximum
from fashionistapulp.structure import (fits_the_class, get_current_game_version, get_structure,
                                       level_to_wear)

CHARACTERISTICS = ('str', 'int', 'cha', 'agi')
# A characteristic is played when it weighs at least this share of the heaviest one
PLAYED_SHARE = 0.7
# The damage stats a turn is priced through, each raised by its step
PRICE_STEPS = (('pow', 20), ('ch', 5), ('cridam', 10), ('dam', 10), ('perspedam', 5))
CHARACTERISTIC_STEP = 20
ELEMENT_DAMAGE_STEP = 10
# AP totals priced from the one reached when the version has no AP cap
UNCAPPED_TIERS = 6
GAINS_KEPT = 5000
# The panel rounds its cast and delayed totals apart
PANEL_ROUNDING = 2

_CHANGERS = {}
_GAINS = {}


def played_characteristics(weights):
    values = {key: (weights or {}).get(key) or 0 for key in CHARACTERISTICS}
    top = max(values.values())
    if top <= 0:
        return ()
    return tuple(key for key in CHARACTERISTICS if values[key] >= PLAYED_SHARE * top)


def ap_tiers(game_version, reached_ap, temporix=False):
    """The AP totals priced: from the one the set reaches up to the cap."""
    lowest = max(int(reached_ap or 0), 1)
    cap = get_stat_maximum(game_version, temporix=temporix).get('AP')
    highest = cap if cap else lowest + UNCAPPED_TIERS - 1
    return tuple(range(lowest, max(lowest, highest) + 1))


def _reads(castable):
    """What best_turn reads of a cast that a modifier can change."""
    rows = [[(row.min_dam, row.max_dam) for row in alternative]
            for alternative in (castable.plain_alternatives + castable.crit_alternatives)]
    return (castable.cost, castable.limit, sorted((castable.bonus_stats or {}).items()), rows)


def turn_changers(game_version, char_class, level):
    """[(item ids, {spell id: [SpellModifier]})] for the pieces the class can wear whose
    modifiers change a cast of its turn."""
    key = (game_version, char_class, level)
    if key in _CHANGERS:
        return _CHANGERS[key]
    structure = get_structure(game_version)
    available = {item.id for item in structure.get_available_items_list()}
    plain = {castable.spell_id: _reads(castable)
             for castable in castable_spells(char_class, level, game_version)}
    out = []
    for ankama_id in sorted((spell_modifier_table(game_version).get('items') or {}), key=int):
        item = structure.get_item_by_ankama_id(int(ankama_id))
        if (item is None or item.id not in available or not fits_the_class(item, char_class)
                or level_to_wear(item) > level):
            continue
        modifiers = item_modifiers_by_spell(game_version, int(ankama_id), item.name)
        if not set(modifiers) & set(plain):
            continue
        changed = [castable for castable in castable_spells(char_class, level, game_version,
                                                            modifiers=modifiers)
                   if castable.spell_id in modifiers
                   and _reads(castable) != plain.get(castable.spell_id)]
        if not changed:
            continue
        rows = set(structure.get_rows_of_the_same_item(item.id) or ()) | {item.id}
        out.append((tuple(sorted(row for row in rows if row in available)), modifiers))
    _CHANGERS[key] = out
    return out


def _castables(game_version, char_class, level, weapon, modifiers=None):
    spells = castable_spells(char_class, level, game_version, modifiers=modifiers)
    return spells + [weapon] if weapon is not None else spells


def _raises(elements):
    """(stat keys, step) of each way turn_prices raises the turn."""
    out = [(tuple(elements), CHARACTERISTIC_STEP)] if elements else []
    out += [((ELEMENT_DAMAGE[element],), ELEMENT_DAMAGE_STEP) for element in elements]
    return out + [((key,), step) for key, step in PRICE_STEPS]


def turn_prices(game_version, char_class, level, stats, elements, ap, weapon=None):
    """(best turn, {stat keys: its gain per unit}), the gains read on the casts of that turn;
    the played characteristics are raised together."""
    spells = _castables(game_version, char_class, level, weapon)
    base, order = best_turn(stats, spells, ap, game_version=game_version, caster_level=level)
    cast = [spell for spell in spells if spell.name in {name for name, _damage in order}]
    per_unit = {}
    for keys, step in _raises(elements):
        raised = dict(stats)
        for key in keys:
            raised[key] = raised.get(key, 0) + step
        per_unit[keys] = (best_turn(raised, cast, ap, game_version=game_version,
                                    caster_level=level)[0] - base) / step
    return base, per_unit


def turn_price(weights, per_unit):
    """The lowest objective value the weights pay for one point of turn through a damage stat."""
    prices = [sum((weights or {}).get(key) or 0 for key in keys) / gain
              for keys, gain in per_unit.items() if gain > 0]
    prices = [price for price in prices if price > 0]
    return min(prices) if prices else 0.0


def _modifiers(*changers):
    modifiers = {}
    for _rows, by_spell in changers:
        for spell_id, found in by_spell.items():
            modifiers.setdefault(spell_id, []).extend(found)
    return modifiers


def item_gains(game_version, char_class, level, stats, elements, ap, weapon=None):
    """({item id: turn gain}, {(item id, item id): turn lost worn together}, the per unit gains
    of turn_prices) at one AP total."""
    worn_weapon = getattr(weapon, 'weapon', None)
    key = (game_version, char_class, level, tuple(sorted(stats.items())), elements, ap,
           getattr(worn_weapon, 'id', None), getattr(worn_weapon, 'element_maged', None),
           getattr(worn_weapon, 'forge_key', ()))
    if key in _GAINS:
        return _GAINS[key]
    gains, overlaps, per_unit = {}, {}, {}
    changers = turn_changers(game_version, char_class, level)
    if changers:
        base, per_unit = turn_prices(game_version, char_class, level, stats, elements, ap,
                                     weapon)

        def gain(*pieces):
            worn = _castables(game_version, char_class, level, weapon, _modifiers(*pieces))
            total, _order = best_turn(stats, worn, ap, game_version=game_version,
                                      caster_level=level)
            return total - base
        paying = []
        for changer in changers:
            alone = round(gain(changer), 2)
            if alone > 0:
                paying.append((changer, alone))
                for item_id in changer[0]:
                    gains[item_id] = alone
        for (first, first_alone), (second, second_alone) in combinations(paying, 2):
            lost = round(gain(first, second) - first_alone - second_alone, 2)
            if lost < 0:
                for one in first[0]:
                    for other in second[0]:
                        overlaps[(one, other)] = lost
    if len(_GAINS) >= GAINS_KEPT:
        _GAINS.clear()
    _GAINS[key] = (gains, overlaps, per_unit)
    return _GAINS[key]


def modifier_values(game_version, char_class, level, weights, stats, temporix=False,
                    weapon=None):
    """({item id: {AP: objective value}}, {(item id, item id): {AP: objective value}}) on stats,
    the stats of a set of the build, and weapon, its WeaponCastable or None."""
    if not char_class or not level or not stats:
        return {}, {}
    elements = played_characteristics(weights)
    values, overlaps = {}, {}
    reached = combat_ap(stats.get('ap'), game_version, temporix=temporix)
    for ap in ap_tiers(game_version, reached, temporix):
        gains, lost, per_unit = item_gains(game_version, char_class, level, stats, elements, ap,
                                           weapon)
        price = turn_price(weights, per_unit) if gains else 0.0
        for item_id, gained in gains.items():
            value = int(round(gained * price))
            if value > 0:
                values.setdefault(item_id, {})[ap] = value
        for pair, gained in lost.items():
            value = int(round(gained * price))
            if value < 0 and all(ap in values.get(item_id, {}) for item_id in pair):
                overlaps.setdefault(pair, {})[ap] = value
    return values, overlaps


def credited(modifier_values, modifier_overlaps, worn, ap):
    """What the solver credits a set wearing the item ids in worn at ap."""
    worn = set(worn)
    return (sum(per_ap.get(ap, 0) for item_id, per_ap in (modifier_values or {}).items()
                if item_id in worn)
            + sum(per_ap.get(ap, 0) for pair, per_ap in (modifier_overlaps or {}).items()
                  if set(pair) <= worn))


class _WithoutModifiers(object):
    """solution with the pieces of item_ids carrying no spell modifier."""

    def __init__(self, solution, item_ids):
        self._solution = solution
        self.items = {slot: [_unmodified(piece) if getattr(piece, 'id', None) in item_ids
                             else piece for piece in pieces or []]
                      for slot, pieces in (getattr(solution, 'items', None) or {}).items()}

    def __getattr__(self, name):
        return getattr(self._solution, name)


def _unmodified(piece):
    # worn_spell_modifiers skips a piece without an Ankama id
    hidden = copy.copy(piece)
    hidden.ankama_id = None
    return hidden


def _panel_total(combo):
    return (combo['total'] + (combo.get('later_total') or 0)) if combo else 0


def true_gain(char, solution, game_version, item_ids):
    """The spells panel's best turn on solution less the same with no spell modifier from item_ids."""
    from chardata.spells_view import _best_combo
    return (_panel_total(_best_combo(char, solution, game_version))
            - _panel_total(_best_combo(char, _WithoutModifiers(solution, item_ids),
                                       game_version)))


def pays_at_the_true_turn(char, priced_input, found, reference):
    """Whether the priced pieces of found, a set solved on priced_input, add their credit to the panel's best turn."""
    from chardata.spells_view import _weapon_castable
    game_version = get_current_game_version()
    values = priced_input.modifier_values or {}
    worn = {piece.id for pieces in (found.items or {}).values() for piece in pieces or []
            if getattr(piece, 'item_added', False)} & set(values)
    ap = combat_ap(dict(found.get_stats_total()).get('ap'), game_version,
                   temporix=bool(priced_input.options.get('temporix')))
    credit = credited(values, priced_input.modifier_overlaps, worn, ap)
    if credit <= 0:
        return False
    elements = played_characteristics(priced_input.objective_values)
    _gains, _lost, per_unit = item_gains(game_version, priced_input.char_class,
                                         priced_input.char_level,
                                         dict(reference.get_stats_total()), elements, ap,
                                         _weapon_castable(reference))
    price = turn_price(priced_input.objective_values, per_unit)
    gain = true_gain(char, found, game_version, worn)
    return (gain + PANEL_ROUNDING) * price >= credit
