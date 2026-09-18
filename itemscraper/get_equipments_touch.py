#!/usr/bin/env python3
"""Turn the raw Touch d2o tables into transformed_equipment.json and transformed_sets.json.

Usage: get_equipments_touch.py [--raw-dir DIR] [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from untranslated_tag import clean_display_name  # noqa: E402

# typeId -> (w_type, weapon subtype), subtypes as in WEAPON_TYPES of get_equipments3.py
TYPE_MAP = {
    1: ('Amulet', None),
    9: ('Ring', None),
    10: ('Belt', None),
    11: ('Boots', None),
    16: ('Hat', None),
    17: ('Cloak', None),
    81: ('Cloak', None),    # Backpack
    82: ('Shield', None),
    18: ('Pet', None),
    121: ('Pet', None),     # Petsmount
    23: ('Dofus', None),
    151: ('Trophy', None),  # get_equipments3 moves it to the Dofus slot, flagged Trophy
    # weapons
    2: ('Weapon', 'Bow'), 3: ('Weapon', 'Wand'), 4: ('Weapon', 'Staff'),
    5: ('Weapon', 'Dagger'), 6: ('Weapon', 'Sword'), 7: ('Weapon', 'Hammer'),
    8: ('Weapon', 'Shovel'), 19: ('Weapon', 'Axe'), 21: ('Weapon', 'Pickaxe'),
    22: ('Weapon', 'Scythe'),
}

# Ankama characteristic id -> stat name; characteristic 0 is overloaded, see effectId below
CHAR_TO_STAT = {
    1: 'AP', 23: 'MP',
    10: 'Strength', 11: 'Vitality', 12: 'Wisdom', 13: 'Chance',
    14: 'Agility', 15: 'Intelligence',
    16: 'Damage', 17: 'Power', 18: 'Critical Hits', 19: 'Range', 26: 'Summon',
    27: 'AP Loss Resist', 28: 'MP Loss Resist',
    33: '% Earth Resist', 34: '% Fire Resist', 35: '% Water Resist',
    36: '% Air Resist', 37: '% Neutral Resist',
    44: 'Initiative', 48: 'Prospecting', 49: 'Heals',
    54: 'Earth Resist', 55: 'Fire Resist', 56: 'Water Resist',
    57: 'Air Resist', 58: 'Neutral Resist',
    59: '% Earth Resist in PVP', 60: '% Fire Resist in PVP',
    61: '% Water Resist in PVP', 62: '% Air Resist in PVP',
    63: '% Neutral Resist in PVP',
    64: 'Earth Resist in PVP', 65: 'Fire Resist in PVP',
    66: 'Water Resist in PVP', 67: 'Air Resist in PVP',
    68: 'Neutral Resist in PVP',
    69: '% Trap Damage', 70: 'Trap Damage',
    78: 'Dodge', 79: 'Lock',
    82: 'AP Reduction', 83: 'MP Reduction',
    84: 'Pushback Damage', 85: 'Pushback Resist',
    86: 'Critical Damage', 87: 'Critical Resist',
    88: 'Earth Damage', 89: 'Fire Damage', 90: 'Water Damage',
    91: 'Air Damage', 92: 'Neutral Damage',
}

# Characteristic 0 effects that are stats, by effectId
CHAR0_EFFECT_TO_STAT = {
    110: 'HP',
    158: 'Pods', 159: 'Pods',
}

# Weapon hit lines, diceNum..diceSide is the damage roll
WEAPON_DAMAGE_BY_EFFECT = {96: 'Water', 97: 'Earth', 98: 'Air', 99: 'Fire', 100: 'Neutral'}
WEAPON_STEAL_BY_EFFECT = {91: 'Water', 92: 'Earth', 93: 'Air', 94: 'Fire', 95: 'Neutral'}

# Effect 101 shares characteristic 1 with +AP but has bonusType 0: a hit, not a stat
WEAPON_AP_REMOVAL_BY_EFFECT = {101}

# Weapon heal lines name no element, Intelligence scales them
WEAPON_HEAL_BY_EFFECT = {108, 81}

# Non-stat lines under their Dofus 3 names; 795 is a hunting weapon only at value 1
FLAG_BY_EFFECT = {795: 'Hunting Weapon', 981: 'Linked to the character'}
FLAG_NEEDS_VALUE = {795: 1}

# Equip condition codes -> stat, the 6 primaries only
CONDITION_MAP = {
    'CS': 'Strength', 'CI': 'Intelligence', 'CA': 'Agility',
    'CV': 'Vitality', 'CC': 'Chance', 'CW': 'Wisdom',
}

# CP and CM count the item's own AP/MP bonus
AP_MP_CONDITION_MAP = {'CP': 'AP', 'CM': 'MP'}

LANGS = ['en', 'fr', 'es', 'pt', 'de']


def load_effects(raw_dir: Path) -> dict:
    """effectId(str) -> {'characteristic': int, 'operator': str}."""
    effs = json.loads((raw_dir / 'Effects_fr.json').read_text(encoding='utf-8'))
    return effs


def stat_for_effect(eid: int, effects: dict):
    """(stat_name, sign) for a characteristic effect, or None if we do not model it."""
    e = effects.get(str(eid))
    if e is None:
        return None
    operator = e.get('operator')
    sign = -1 if operator == '-' else 1
    char = e.get('characteristic')
    if eid in CHAR0_EFFECT_TO_STAT:
        return CHAR0_EFFECT_TO_STAT[eid], sign
    name = CHAR_TO_STAT.get(char)
    if name is None:
        return None
    # Wielder stats have bonusType 1 or -1, 0 is in-fight only
    if e.get('bonusType') not in (1, -1):
        return None
    return name, sign


def decode_effects(possible_effects, effects, is_weapon):
    """possibleEffects[] -> (stats [[min, max, stat]], hits [[min, max, '(<Element> damage)']])."""
    stats, hits = [], []
    for pe in (possible_effects or []):
        if not isinstance(pe, dict) or 'effectId' not in pe:
            continue
        eid = pe.get('effectId')
        lo = pe.get('diceNum') or 0
        hi = pe.get('diceSide') or 0
        hi = hi if hi > 0 else lo            # diceSide==0 => fixed value
        if is_weapon and eid in WEAPON_DAMAGE_BY_EFFECT:
            hits.append([lo, hi, '(%s damage)' % WEAPON_DAMAGE_BY_EFFECT[eid]])
            continue
        if is_weapon and eid in WEAPON_STEAL_BY_EFFECT:
            hits.append([lo, hi, '(%s steal)' % WEAPON_STEAL_BY_EFFECT[eid]])
            continue
        if is_weapon and eid in WEAPON_AP_REMOVAL_BY_EFFECT:
            hits.append([lo, hi, '(removes ap)'])
            continue
        if is_weapon and eid in WEAPON_HEAL_BY_EFFECT:
            hits.append([lo, hi, '(heals)'])
            continue
        if eid in FLAG_BY_EFFECT:
            wanted = FLAG_NEEDS_VALUE.get(eid)
            if wanted is None or pe.get('value') == wanted:
                stats.append([None, None, FLAG_BY_EFFECT[eid]])
            continue
        resolved = stat_for_effect(eid, effects)
        if resolved is None:
            continue
        name, sign = resolved
        first, second = sign * lo, sign * hi
        if first < 0 or second < 0:
            first, second = min(first, second), max(first, second)
        stats.append([first, second, name])
    return stats, hits


# Shields give bonusRatio per rank; last rank used when ShieldModelsLevels is missing
SHIELD_MAX_LEVEL = 100


def load_shield_levels(raw_dir: Path) -> dict:
    """{shield model id: its last rank}, from ShieldModelsLevels."""
    path = raw_dir / 'ShieldModelsLevels_fr.json'
    if not path.exists():
        print('  ! %s is missing: every shield is read at rank %d'
              % (path.name, SHIELD_MAX_LEVEL))
        return {}
    table = json.loads(path.read_text(encoding='utf-8'))
    return {int(model.get('id', key)): len(model.get('requiredXpLevels') or [])
            for key, model in table.items() if isinstance(model, dict)}


def decode_shield_bonuses(shield_bonuses, effects, max_level=SHIELD_MAX_LEVEL):
    stats = []
    for bonus in (shield_bonuses or []):
        if not isinstance(bonus, dict) or 'effectId' not in bonus:
            continue
        resolved = stat_for_effect(bonus['effectId'], effects)
        if resolved is None:
            continue
        name, sign = resolved
        value = int(round((bonus.get('bonusRatio') or 0) * max_level))
        if not value:
            continue
        stats.append([sign * value, sign * value, name])
    return stats


def _top_level_parts(criteria: str):
    """Split on the '&' that sit outside parentheses."""
    parts, depth, start = [], 0, 0
    for index, char in enumerate(criteria):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == '&' and depth == 0:
            parts.append(criteria[start:index])
            start = index + 1
    parts.append(criteria[start:])
    return parts


def decode_conditions(criteria: str):
    """'CS>20&CV>6' -> ['Strength > 20', 'Vitality > 6'], OR parts joined by ' | ', 'Pk<N' -> 'Set bonus < N'."""
    out = []
    if not criteria or criteria == 'null':
        return out
    for part in _top_level_parts(str(criteria)):
        gates = []
        for code, op, val in re.findall(r'(C[A-Z])\s*([<>])\s*(\d+)', part):
            stat = CONDITION_MAP.get(code) or AP_MP_CONDITION_MAP.get(code)
            if stat:
                gates.append('%s %s %s' % (stat, op, val))
        if '|' not in part:
            out.extend(gates)
            continue
        branches = [branch for branch in part.replace('(', '').replace(')', '').split('|')]
        # A branch we do not model (class, alignment) makes the part unenforceable
        if len(gates) != len(branches):
            continue
        out.append(' | '.join(gates))
    for val in re.findall(r'Pk\s*<\s*(\d+)', str(criteria)):
        out.append('Set bonus < %s' % val)
    return out


def loc_name(tables_by_lang, lang, item_id, fallback):
    rec = (tables_by_lang.get(lang) or {}).get(item_id)
    if rec and rec.get('nameId'):
        return clean_display_name(rec['nameId'])
    return fallback


def build_equipment(items_by_lang, effects, shield_levels=None):
    shield_levels = shield_levels or {}
    items_fr = items_by_lang['fr']
    out = []
    for iid, it in items_fr.items():
        if not isinstance(it, dict):
            continue
        type_id = it.get('typeId')
        if type_id not in TYPE_MAP:
            continue
        w_type, weapon_type = TYPE_MAP[type_id]
        try:
            ankama_id = int(iid)
        except (TypeError, ValueError):
            continue
        name_fr = it.get('nameId') or ''
        level = it.get('level') or 1
        level = max(1, min(int(level), 200))
        is_weapon = it.get('_type') == 'Weapon'
        stats, hits = decode_effects(it.get('possibleEffects'), effects, is_weapon)
        if it.get('shieldBonuses'):
            model_id = it.get('shieldModelId')
            max_level = shield_levels.get(model_id)
            if not max_level:
                if shield_levels:
                    print('  ! shield %s names model %s, which '
                          'ShieldModelsLevels does not list: read at rank %d'
                          % (iid, model_id, SHIELD_MAX_LEVEL))
                max_level = SHIELD_MAX_LEVEL
            stats.extend(decode_shield_bonuses(it.get('shieldBonuses'), effects,
                                               max_level))

        rec = {
            'ankama_id': ankama_id,
            'ankama_type': 'equipment',
            'name_en': loc_name(items_by_lang, 'en', iid, name_fr),
            'name_fr': name_fr,
            'name_es': loc_name(items_by_lang, 'es', iid, name_fr),
            'name_pt': loc_name(items_by_lang, 'pt', iid, name_fr),
            'name_de': loc_name(items_by_lang, 'de', iid, name_fr),
            'level': level,
            'w_type': w_type,
            'stats': stats + hits,
            'conditions': decode_conditions(it.get('criteria') or ''),
        }
        if weapon_type:
            rec['weapon_type'] = weapon_type
            if it.get('apCost'):
                rec['ap'] = int(it['apCost'])
            if it.get('criticalHitProbability') is not None:
                rec['crit_chance'] = int(it['criticalHitProbability'])
            if it.get('criticalHitBonus') is not None:
                rec['crit_bonus'] = int(it['criticalHitBonus'])
            if it.get('maxCastPerTurn'):
                rec['uses_per_turn'] = int(it['maxCastPerTurn'])
        out.append(rec)
    return out


def build_sets(sets_by_lang, effects, valid_item_ids):
    sets_fr = sets_by_lang['fr']
    out = []
    for sid, sd in sets_fr.items():
        if not isinstance(sd, dict):
            continue
        try:
            set_ankama_id = int(sid)
        except (TypeError, ValueError):
            continue
        name_fr = sd.get('nameId') or ''
        equipment_ids = [int(x) for x in (sd.get('items') or []) if int(x) in valid_item_ids]
        # Skip non-wearable sets (cubes, gems)
        if len(equipment_ids) < 2:
            continue

        # model.py caps set bonuses at 8 pieces
        max_pieces = min(len(equipment_ids), 8)

        stats_list = []
        for idx, tier in enumerate(sd.get('effects') or []):
            num_pieces = idx + 1                # tier[0] = 1 piece (no bonus)
            if num_pieces > max_pieces:
                continue
            tier_effects = []
            for pe in (tier or []):
                if not isinstance(pe, dict) or 'effectId' not in pe:
                    continue
                resolved = stat_for_effect(pe['effectId'], effects)
                if resolved is None:
                    continue
                name, sign = resolved
                lo = pe.get('diceNum') or 0
                hi = pe.get('diceSide') or 0
                hi = hi if hi > 0 else lo
                tier_effects.append([sign * lo, sign * hi, name])
            if tier_effects:
                stats_list.append({'effect_key': num_pieces, 'effects': tier_effects})

        out.append({
            'ankama_id': set_ankama_id,
            'name_en': loc_name(sets_by_lang, 'en', sid, name_fr),
            'name_fr': name_fr,
            'name_es': loc_name(sets_by_lang, 'es', sid, name_fr),
            'name_pt': loc_name(sets_by_lang, 'pt', sid, name_fr),
            'name_de': loc_name(sets_by_lang, 'de', sid, name_fr),
            'equipment_ids': equipment_ids,
            'stats_list': stats_list,
        })
    return out


def load_mounts(raw_dir: Path):
    """Touch mounts as Pet records; their ids clash with equipment, get_equipments3 offsets them."""
    path = raw_dir / 'mounts.json'
    if not path.exists():
        return []
    out = []
    for m in json.loads(path.read_text(encoding='utf-8')):
        out.append({
            'ankama_id': m['ankama_id'],
            'ankama_type': 'mounts',
            'name_en': m['name_en'], 'name_fr': m['name_fr'], 'name_es': m['name_es'],
            'name_pt': m['name_pt'], 'name_de': m['name_de'],
            'level': m.get('level', 60),
            'w_type': 'Pet',
            'stats': m['stats'],
            'conditions': [],
        })
    return out


def _load_lang_tables(raw_dir: Path, table: str):
    out = {}
    for lang in LANGS:
        p = raw_dir / ('%s_%s.json' % (table, lang))
        out[lang] = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--raw-dir', default='itemscraper/touch_raw')
    parser.add_argument('--out-dir', default='itemscraper/touch')
    args = parser.parse_args(argv)

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    effects = load_effects(raw_dir)
    items_by_lang = _load_lang_tables(raw_dir, 'Items')
    sets_by_lang = _load_lang_tables(raw_dir, 'ItemSets')

    equipment = build_equipment(items_by_lang, effects,
                                load_shield_levels(raw_dir))
    mounts = load_mounts(raw_dir)
    equipment += mounts
    valid_item_ids = {e['ankama_id'] for e in equipment}
    sets = build_sets(sets_by_lang, effects, valid_item_ids)

    (out_dir / 'transformed_equipment.json').write_text(
        json.dumps(equipment, ensure_ascii=False, indent=4), encoding='utf-8')
    (out_dir / 'transformed_sets.json').write_text(
        json.dumps(sets, ensure_ascii=False, indent=4), encoding='utf-8')

    print('wrote %d equipment (incl. %d mounts), %d sets to %s/'
          % (len(equipment), len(mounts), len(sets), out_dir))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
