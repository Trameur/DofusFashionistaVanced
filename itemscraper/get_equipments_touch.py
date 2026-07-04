#!/usr/bin/env python3
"""
Turn the raw Touch tables (touch_raw/) into transformed_equipment.json and
transformed_sets.json, in the same shape get_equipments2.py produces for Dofus 3.
That lets get_equipments3.py and load_item_db.py --game-version touch reuse the
existing dump/load path unchanged via --input-dir.

Touch is a Dofus 2 fork, so item records are Ankama's raw d2o objects:
  - possibleEffects[]  effectId -> Effects table (characteristic + operator),
                       diceNum/diceSide = the value range (min..max).
  - criteria           equip conditions, e.g. "CS>20&CV>6".
  - typeId             the slot (see TYPE_MAP); _type=='Weapon' marks weapons.
  - itemSetId          set membership (the sets carry the per-piece bonuses).

Touch keeps a few stats Dofus 3 dropped or reworked: PvP resists, AP/MP parry
(Esquive) and reduction (Retrait), dodge/lock (Fuite/Tacle) and traps. The maps
below come from Touch's Effects table and are checked against a handful of known
items (Gelano gives +1 AP, the Gobball headgear gives Str/Int/Lock/MP-parry, the
7-piece Gobball set gives +1 AP).

We only emit stat names that exist in STAT_NAME_TO_KEY (get_equipments3.py); the
dump drops anything else, which is fine since the rest is cosmetic/flavour.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# typeId -> (slot w_type, weapon subtype or None). Only real equipment is kept;
# resources / consumables / quest items / cosmetic "d'apparat" types are dropped.
# Weapon subtypes must match WEAPON_TYPES in get_equipments3.py.
# ---------------------------------------------------------------------------
TYPE_MAP = {
    1: ('Amulet', None),
    9: ('Ring', None),
    10: ('Belt', None),
    11: ('Boots', None),
    16: ('Hat', None),
    17: ('Cloak', None),
    81: ('Cloak', None),    # Sac a dos (Backpack) -> Cloak slot
    82: ('Shield', None),
    18: ('Pet', None),      # Familier (pet)
    121: ('Pet', None),     # Montilier (mount) -> shares the Pet slot
    23: ('Dofus', None),
    151: ('Trophy', None),  # Trophee: get_equipments3 puts it back on the Dofus slot and flags it Trophy
    # weapons
    2: ('Weapon', 'Bow'), 3: ('Weapon', 'Wand'), 4: ('Weapon', 'Staff'),
    5: ('Weapon', 'Dagger'), 6: ('Weapon', 'Sword'), 7: ('Weapon', 'Hammer'),
    8: ('Weapon', 'Shovel'), 19: ('Weapon', 'Axe'), 21: ('Weapon', 'Pickaxe'),
    22: ('Weapon', 'Scythe'),
}

# Ankama "characteristic" id -> internal stat name (STAT_NAME_TO_KEY in
# get_equipments3.py). characteristic 0 is overloaded (HP, elemental hits,
# steals, flavour) so those are handled by effectId below, not here.
CHAR_TO_STAT = {
    1: 'AP', 23: 'MP',
    10: 'Strength', 11: 'Vitality', 12: 'Wisdom', 13: 'Chance',
    14: 'Agility', 15: 'Intelligence',
    16: 'Damage', 17: 'Power', 18: 'Critical Hits', 19: 'Range', 26: 'Summon',
    27: 'AP Loss Resist', 28: 'MP Loss Resist',     # Esquive PA / PM (parry)
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
    69: '% Trap Damage', 70: 'Trap Damage',         # Puissance (pieges) / Dommages Pieges
    78: 'Dodge', 79: 'Lock',                         # Fuite / Tacle
    82: 'AP Reduction', 83: 'MP Reduction',          # Retrait PA / PM
    84: 'Pushback Damage', 85: 'Pushback Resist',
    86: 'Critical Damage', 87: 'Critical Resist',
    88: 'Earth Damage', 89: 'Fire Damage', 90: 'Water Damage',
    91: 'Air Damage', 92: 'Neutral Damage',
}

# characteristic-0 effects that ARE stats (resolved by effectId, not char).
CHAR0_EFFECT_TO_STAT = {
    110: 'HP',
    158: 'Pods', 159: 'Pods',
}

# Weapon hit lines (characteristic 0, only meaningful on a weapon). diceNum..diceSide
# is the weapon's damage roll. Routed to "(<Element> damage|steal)" so get_equipments3
# turns them into weapon_hits rather than flat characteristic bonuses.
WEAPON_DAMAGE_BY_EFFECT = {96: 'Water', 97: 'Earth', 98: 'Air', 99: 'Fire', 100: 'Neutral'}
WEAPON_STEAL_BY_EFFECT = {91: 'Water', 92: 'Earth', 93: 'Air', 94: 'Fire', 95: 'Neutral'}

# Weapon AP-removal hit: effect 101 ("removes X AP from the enemy", e.g. the Worn
# Koulosse Staff). It shares characteristic id 1 with the +AP bonus but has
# bonusType 0, so it isn't a wielder stat; on a weapon it's a hit line, routed to
# "(removes ap)" so get_equipments3 stores it as a weapon_hit (like life/MP steal).
WEAPON_AP_REMOVAL_BY_EFFECT = {101}

# Equip-condition codes -> internal stat (only the 6 unambiguous primaries, like
# Retro; alignment Ps/Pa and the rarer CP/CM are skipped to avoid mis-gating).
CONDITION_MAP = {
    'CS': 'Strength', 'CI': 'Intelligence', 'CA': 'Agility',
    'CV': 'Vitality', 'CC': 'Chance', 'CW': 'Wisdom',
}

LANGS = ['en', 'fr', 'es', 'pt', 'de']


def load_effects(raw_dir: Path) -> dict:
    """effectId(str) -> {'characteristic': int, 'operator': str}."""
    effs = json.loads((raw_dir / 'Effects_fr.json').read_text(encoding='utf-8'))
    return effs


def stat_for_effect(eid: int, effects: dict):
    """Return (stat_name, sign) for a characteristic effect, or None if it isn't
    a stat the optimizer models."""
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
    # A characteristic id is shared by the real item bonus AND by combat-only
    # effects with the same characteristic: e.g. "removes 1-2 AP from the enemy",
    # "AP lost by the caster", weapon hits, in-fight steals. Ankama flags wielder
    # stats with bonusType 1 (bonus) / -1 (malus); bonusType 0 is an in-fight
    # effect and must NOT become a flat characteristic (was turning "removes X AP"
    # into a phantom "+X AP" bonus, e.g. Worn Koulosse Staff).
    if e.get('bonusType') not in (1, -1):
        return None
    return name, sign


def decode_effects(possible_effects, effects, is_weapon):
    """possibleEffects[] -> (stats, hits).

    stats: [[min, max, stat_name], ...] characteristic bonuses (signed).
    hits : [[min, max, '(<Element> damage|steal)'], ...] weapon hit lines.
    """
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
        resolved = stat_for_effect(eid, effects)
        if resolved is None:
            continue
        name, sign = resolved
        # Positive stats: get_equipments3 keeps the max (best roll); negatives:
        # it keeps stat[0]. Signing both ends gives the right "best case" either way.
        stats.append([sign * lo, sign * hi, name])
    return stats, hits


def decode_conditions(criteria: str):
    """'CS>20&CV>6' -> ['Strength > 20', 'Vitality > 6'] (AND, stat gates). Also maps
    the set-bonus gate 'Pk<N' -> 'Set bonus < N' so trophies that limit panoply bonuses
    get the 'light_set' weird condition downstream (get_equipments3.py)."""
    out = []
    if not criteria or criteria == 'null':
        return out
    for code, op, val in re.findall(r'(C[A-Z])\s*([<>])\s*(\d+)', criteria):
        stat = CONDITION_MAP.get(code)
        if stat:
            out.append('%s %s %s' % (stat, op, val))
    for val in re.findall(r'Pk\s*<\s*(\d+)', criteria):
        out.append('Set bonus < %s' % val)
    return out


def loc_name(tables_by_lang, lang, item_id, fallback):
    rec = (tables_by_lang.get(lang) or {}).get(item_id)
    if rec and rec.get('nameId'):
        return rec['nameId']
    return fallback


def build_equipment(items_by_lang, effects):
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
        # Skip non-wearable "sets" (Cubes/Gems/etc.) whose members aren't equipment.
        if len(equipment_ids) < 2:
            continue

        # The LP supports set bonuses for at most 8 equipped pieces (ss index =
        # num_pieces+1, capped at 9 in model.py); tiers above the set's own item
        # count are unreachable too. All other versions cap at 8 as well.
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
    """Read the scraped Touch mounts (download_touch_mounts.py) as Pet-slot records.

    Mounts share Ankama ids with equipment, so get_equipments3 offsets their db id;
    the model's dragoturkey toggle gates them by "Dragoturkey" in the English name.
    """
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

    equipment = build_equipment(items_by_lang, effects)
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
