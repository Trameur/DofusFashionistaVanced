#!/usr/bin/env python3
"""
get_equipments_retro.py — Stage 3 transform for the Dofus Retro pipeline.

Reads the parsed Retro lang JSON (produced by download_retro_langs.py) and emits
transformed_equipment.json + transformed_sets.json in the SAME shape that
get_equipments2.py produces for Dofus 3 — so the existing get_equipments3.py
(dump) + load_item_db.py (load) work unchanged with --input-dir.

Stat decoding validated against known items:
  Coiffe du Bouftou -> 1-40 Strength / 1-40 Intelligence
  Amulette du Bouftou -> 1-10 Strength / 1-10 Intelligence
  Gelano / Dofus Ocre -> +1 AP

Effect convention: ISTA entry = "<effectId_hex>#<jetMin_hex>#<jetMax_hex>#<dice>".
The optimizer wants the best roll, so value = jetMax (fallback jetMin).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Retro item type id -> (slot/category name, weapon subtype or None).
# Only equippable categories are kept; consumables/resources are dropped.
TYPE_MAP = {
    '1': ('Amulet', None), '2': ('Weapon', 'Bow'), '3': ('Weapon', 'Wand'),
    '4': ('Weapon', 'Staff'), '5': ('Weapon', 'Dagger'), '6': ('Weapon', 'Sword'),
    '7': ('Weapon', 'Hammer'), '8': ('Weapon', 'Shovel'), '9': ('Ring', None),
    '10': ('Belt', None), '11': ('Boots', None), '16': ('Hat', None),
    '17': ('Cloak', None), '18': ('Pet', None), '19': ('Weapon', 'Axe'),
    '21': ('Weapon', 'Pickaxe'), '22': ('Weapon', 'Scythe'), '23': ('Dofus', None),
}

# Retro effect id -> (English stat name as used by get_equipments3, sign).
EFFECT_MAP = {
    118: ('Strength', 1), 119: ('Agility', 1), 123: ('Chance', 1),
    124: ('Wisdom', 1), 125: ('Vitality', 1), 126: ('Intelligence', 1),
    112: ('Damage', 1), 115: ('Critical Hits', 1), 117: ('Range', 1),
    110: ('HP', 1), 174: ('Initiative', 1), 176: ('Prospecting', 1),
    178: ('Heals', 1), 182: ('Summon', 1), 111: ('AP', 1), 128: ('MP', 1),
    96: ('Water Damage', 1), 97: ('Earth Damage', 1), 98: ('Air Damage', 1),
    99: ('Fire Damage', 1), 100: ('Neutral Damage', 1),
    210: ('% Earth Resist', 1), 211: ('% Water Resist', 1), 212: ('% Air Resist', 1),
    213: ('% Fire Resist', 1), 214: ('% Neutral Resist', 1),
    240: ('Earth Resist', 1), 241: ('Water Resist', 1), 242: ('Air Resist', 1),
    243: ('Fire Resist', 1), 244: ('Neutral Resist', 1),
    # malus (negative)
    153: ('Vitality', -1), 154: ('Agility', -1), 155: ('Intelligence', -1),
    156: ('Wisdom', -1), 157: ('Strength', -1), 152: ('Chance', -1),
    175: ('Prospecting', -1), 168: ('AP', -1), 169: ('MP', -1),
    166: ('AP', 1), 177: ('Dodge', 1), 173: ('Lock', 1),
    194: ('Pods', 1),
}

# Condition code -> English stat name (only stat-gating codes; class/sub/align skipped).
CONDITION_MAP = {
    'CS': 'Strength', 'CI': 'Intelligence', 'CA': 'Agility',
    'CV': 'Vitality', 'CC': 'Chance', 'CW': 'Wisdom',
}


def _hex(x):
    try:
        return int(x, 16)
    except (ValueError, TypeError):
        return None


def decode_stats(ista_string):
    """ISTA string -> list of [min, max, english_stat_name]."""
    stats = []
    for part in (ista_string or '').split(','):
        if not part:
            continue
        fields = part.split('#')
        eid = _hex(fields[0])
        if eid is None or eid not in EFFECT_MAP:
            continue
        name, sign = EFFECT_MAP[eid]
        jmin = _hex(fields[1]) if len(fields) > 1 and fields[1] != '' else None
        jmax = _hex(fields[2]) if len(fields) > 2 and fields[2] != '' else None
        value = jmax if jmax not in (None, 0) else jmin
        if value is None:
            continue
        v = sign * value
        stats.append([v, v, name])
    return stats


def decode_conditions(c_string):
    """Retro condition string -> ['Strength > 34', ...] (stat conditions only)."""
    import re
    out = []
    if not c_string:
        return out
    for code, op, val in re.findall(r'(C[A-Z])\s*([<>])\s*(\d+)', str(c_string)):
        stat = CONDITION_MAP.get(code)
        if stat:
            out.append(f'{stat} {op} {val}')
    return out


def build(items_root, sets_root, names_en=None):
    items = items_root['u']
    equipment = []
    for iid, it in items.items():
        if not isinstance(it, dict):
            continue
        type_id = str(it.get('t'))
        if type_id not in TYPE_MAP:
            continue
        w_type, weapon_type = TYPE_MAP[type_id]
        try:
            ankama_id = int(iid)
        except (TypeError, ValueError):
            continue
        name_fr = it.get('n') or ''
        name_en = (names_en or {}).get(iid, name_fr)
        try:
            level = int(it.get('l', 1))
        except (TypeError, ValueError):
            level = 1
        level = max(1, min(level, 200))  # structure.py indexes types by level 1..200
        rec = {
            'ankama_id': ankama_id,
            'ankama_type': 'equipment',
            'name_en': name_en, 'name_fr': name_fr,
            'name_es': name_fr, 'name_pt': name_fr, 'name_de': name_fr,
            'level': level,
            'w_type': w_type,
            'stats': decode_stats(it.get('istats', '')),
            'conditions': decode_conditions(it.get('c', '')),
        }
        if weapon_type:
            rec['weapon_type'] = weapon_type
        equipment.append(rec)

    sets = []
    for sid, sd in sets_root.items():
        if not isinstance(sd, dict) or not sd.get('i'):
            continue
        try:
            set_ankama_id = int(sid)
        except (TypeError, ValueError):
            continue
        name = sd.get('n') or ''
        sets.append({
            'ankama_id': set_ankama_id,
            'name_en': name, 'name_fr': name,
            'equipment_ids': [int(x) for x in sd['i']],
            'stats_list': [],  # Retro set bonuses: TODO (not in itemsets lang)
        })
    return equipment, sets


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw-dir', default='itemscraper/retro_raw')
    p.add_argument('--out-dir', default='itemscraper/retro')
    p.add_argument('--lang', default='fr')
    args = p.parse_args(argv)

    raw = Path(args.raw_dir)
    items_root = json.loads((raw / f'items_{args.lang}.json').read_text(encoding='utf-8'))['I']
    ista = json.loads((raw / f'itemstats_{args.lang}.json').read_text(encoding='utf-8'))['ISTA']
    sets_root = json.loads((raw / f'itemsets_{args.lang}.json').read_text(encoding='utf-8'))['IS']

    # Attach the stat strings onto each item under 'istats' for decode_stats.
    for iid, it in items_root['u'].items():
        if isinstance(it, dict) and iid in ista:
            it['istats'] = ista[iid]

    # Optional English names
    names_en = None
    en_path = raw / 'items_en.json'
    if en_path.exists():
        en_items = json.loads(en_path.read_text(encoding='utf-8'))['I']['u']
        names_en = {k: v.get('n') for k, v in en_items.items() if isinstance(v, dict)}

    equipment, sets = build(items_root, sets_root, names_en)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'transformed_equipment.json').write_text(
        json.dumps(equipment, ensure_ascii=False), encoding='utf-8')
    (out / 'transformed_sets.json').write_text(
        json.dumps(sets, ensure_ascii=False), encoding='utf-8')

    with_stats = sum(1 for e in equipment if e['stats'])
    print(f"Wrote {len(equipment)} equipment ({with_stats} with stats) "
          f"and {len(sets)} sets to {out}/")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
