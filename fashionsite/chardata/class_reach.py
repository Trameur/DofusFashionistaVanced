"""A class's melee and range weights, read from the casts of its best turn."""
from chardata.management.commands.store_default_elements import (
    TOP_LEVEL, element_turns, gear_line, reference_stats, turn_aps)
from chardata.presets import ELEMENT_DAMAGE
from chardata.spell_combo import best_turn, castable_spells
from chardata.spell_reference import get_spell_reference

MELEE_REACH = 1
RANGED_REACH = 4


def top_reach(entry):
    """The longest cast range of the spell's last grade, 0 for a spell cast on its caster."""
    ranges = entry.get('range') or []
    if not ranges or not ranges[-1]:
        return 0
    return int(ranges[-1][-1] or 0)


def reach_by_name(game_version, char_class):
    return {(entry.get('name') or {}).get('en'): top_reach(entry)
            for entry in get_spell_reference(game_version).get(char_class) or []}


def reach_shares(game_version, char_class, level=TOP_LEVEL):
    """{'meleeness', 'range_importance'}: damage shares of the best turns, over every element and AP."""
    reach = reach_by_name(game_version, char_class)
    melee = ranged = total = 0.0
    turns = element_turns(game_version, char_class, gear_line(game_version, level), level)
    for _turn, orders in turns.values():
        for order in orders.values():
            for name, damage in order:
                cells = reach.get(name, 0)
                total += damage
                if cells <= MELEE_REACH:
                    melee += damage
                elif cells >= RANGED_REACH:
                    ranged += damage
    if total <= 0:
        return {'meleeness': 0.0, 'range_importance': 0.0}
    return {'meleeness': round(melee / total, 1),
            'range_importance': round(ranged / total, 1)}


def _cast_worth(stats, spell, game_version, level):
    return best_turn(stats, [spell], spell.cost, game_version=game_version,
                     caster_level=level)[0]


def hp_share_fraction(game_version, char_class, level=TOP_LEVEL):
    """Share of the best turns' damage that is a share of the caster's HP, over every element and AP."""
    spells = {spell.name: spell for spell in castable_spells(char_class, level, game_version)}
    gear = gear_line(game_version, level)
    from_hp = total = 0.0
    for element in ELEMENT_DAMAGE:
        for ap in turn_aps(game_version, char_class, element, level):
            stats = reference_stats(game_version, char_class, element, gear, ap, level)
            lifeless = dict(stats, hp=0)
            _turn, order = best_turn(stats, list(spells.values()), ap,
                                     game_version=game_version, caster_level=level)
            for name, damage in order:
                total += damage
                spell = spells.get(name)
                full = _cast_worth(stats, spell, game_version, level) if spell else 0
                if full > 0:
                    bare = _cast_worth(lifeless, spell, game_version, level)
                    from_hp += damage * max(full - bare, 0.0) / full
    return from_hp / total if total > 0 else 0.0


def vit_importance(game_version, char_class, level=TOP_LEVEL):
    """The default Vitality weight raised toward 1 by the HP-share fraction of the best turns."""
    from chardata.smart_build import RACE_TO_BUILD_PROFILE
    default = RACE_TO_BUILD_PROFILE['default']['vit_importance']
    fraction = hp_share_fraction(game_version, char_class, level)
    return round(default + fraction * (1 - default), 1)
