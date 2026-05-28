#!/usr/bin/env python3
"""
get_spells_retro.py - extract Dofus Retro (1.29) damage spells per class.

Reads the parsed Retro lang files (spells_<lang>.json + classes_<lang>.json from
download_retro_langs.py) and emits a per-class damage-spell dataset shaped to feed
dofus_constants' DAMAGE_SPELLS (Spell/Effects), consumed by chardata.spells_view.

Decoding notes (validated against known spells):
  - A spell "level" array ends with two effect lists; each effect entry is
    [dice, ..., effect_id]. Elemental damage uses the same effect ids as items
    (96 Water, 97 Earth, 98 Air, 99 Fire, 100 Neutral). e.g. Attaque Naturelle ->
    fire 2-6 (l1) ... 9-13 (l6), confirming the dice -> min/max mapping.
  - The two lists are the normal and critical effects, but their order is not
    fixed; we assign crit = the higher-valued roll (crit >= normal always holds).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Retro effect id -> element token (matches dofus_constants element tokens).
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral'}

# Standard Dofus class id -> Fashionista class name (Retro = the original 12).
CLASS_ID_TO_NAME = {
    1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor', 6: 'Ecaflip',
    7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida', 11: 'Sacrier', 12: 'Pandawa',
}

LEVELS = ('l1', 'l2', 'l3', 'l4', 'l5', 'l6')


def dice_range(d):
    """'1d5+1' -> (2, 6); '0d0+8' -> (8, 8); None for unparseable."""
    m = re.match(r'(\d+)d(\d+)([+-]\d+)?', d or '')
    if not m:
        return None
    x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if y == 0:
        return (z, z)
    return (x + z, x * y + z)


def _collect(effect_list):
    """One effect list -> {element_token: (min, max)} for elemental damage."""
    out = {}
    for e in (effect_list or []):
        if isinstance(e, list) and len(e) >= 2 and e[-1] in DAMAGE_EFFECTS:
            rng = dice_range(e[0])
            if rng:
                out[DAMAGE_EFFECTS[e[-1]]] = rng
    return out


def decode_level(level_arr):
    """Spell level array -> {element: (normal_range, crit_range)}."""
    if not isinstance(level_arr, list) or len(level_arr) < 2:
        return {}
    a, b = _collect(level_arr[-2]), _collect(level_arr[-1])
    result = {}
    for elem in set(a) | set(b):
        ra, rb = a.get(elem), b.get(elem)
        if ra and rb:
            normal, crit = (rb, ra) if ra[1] >= rb[1] else (ra, rb)
        else:
            normal = crit = (ra or rb)
        result[elem] = (normal, crit)
    return result


def decode_spell(spell):
    """Retro spell record -> damage-spell dict, or None if it deals no damage."""
    per_level = []
    elements = []
    for lv in LEVELS:
        if lv not in spell:
            continue
        decoded = decode_level(spell[lv])
        per_level.append(decoded)
        for elem in decoded:
            if elem not in elements:
                elements.append(elem)
    if not elements or not per_level:
        return None
    # Build, per element, the per-level normal/crit "min-max" strings.
    non_crit_ranges, crit_ranges = [], []
    for elem in elements:
        nc, cr = [], []
        for decoded in per_level:
            normal, crit = decoded.get(elem, (None, None))
            nc.append('%d-%d' % normal if normal else '0-0')
            cr.append('%d-%d' % crit if crit else '0-0')
        non_crit_ranges.append(nc)
        crit_ranges.append(cr)
    return {
        'name': spell.get('n') or '',
        'level_count': len(per_level),
        'elements': elements,
        'non_crit_ranges': non_crit_ranges,
        'crit_ranges': crit_ranges,
    }


def build(spells_root, classes_root):
    by_class = {}
    missing_classes = []
    for cid, app_name in CLASS_ID_TO_NAME.items():
        cdata = classes_root.get(str(cid))
        if not isinstance(cdata, dict) or not cdata.get('s'):
            missing_classes.append(app_name)
            continue
        damage_spells = []
        for spell_id in cdata['s']:
            spell = spells_root.get(str(spell_id))
            if not isinstance(spell, dict):
                continue
            decoded = decode_spell(spell)
            if decoded:
                damage_spells.append(decoded)
        by_class[app_name] = damage_spells
    return by_class, missing_classes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw-dir', default='itemscraper/retro_raw')
    p.add_argument('--out', default='itemscraper/retro/retro_damage_spells.json')
    p.add_argument('--lang', default='fr')
    args = p.parse_args(argv)

    raw = Path(args.raw_dir)
    spells_root = json.loads((raw / f'spells_{args.lang}.json').read_text(encoding='utf-8'))['S']
    classes_root = json.loads((raw / f'classes_{args.lang}.json').read_text(encoding='utf-8'))['G']

    by_class, missing = build(spells_root, classes_root)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(by_class, ensure_ascii=False, indent=1), encoding='utf-8')

    total = sum(len(v) for v in by_class.values())
    print(f"Wrote {total} damage spells across {len(by_class)} classes to {out_path}")
    if missing:
        print(f"  classes with no spell data in lang: {', '.join(missing)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
