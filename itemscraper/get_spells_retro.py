#!/usr/bin/env python3
"""
Extract Dofus Retro (1.29) damage spells per class, for dofus_constants'
DAMAGE_SPELLS, from the lang files download_retro_langs.py writes.

    python get_spells_retro.py [--raw-dir retro_raw] [--module-out PATH]

A spell "level" array ends with two effect lists; each entry is
[dice, ..., effect_id], with the item effect ids for elemental damage.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Retro effect id -> element token. 96-100 elemental damage, 91-95 elemental
# steals (same hit, heals the caster).
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral',
                  91: 'water', 92: 'earth', 93: 'air', 94: 'fire', 95: 'neutral'}

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
    """One effect list -> {element_token: (min, max)}. A level can carry several
    lines of one element (conditional branches, damage/steal pairs); the
    strongest by midpoint wins."""
    out = {}
    for e in (effect_list or []):
        if isinstance(e, list) and len(e) >= 2 and e[-1] in DAMAGE_EFFECTS:
            rng = dice_range(e[0])
            if rng:
                elem = DAMAGE_EFFECTS[e[-1]]
                prev = out.get(elem)
                if prev is None or rng[0] + rng[1] > prev[0] + prev[1]:
                    out[elem] = rng
    return out


def decode_level(level_arr):
    """Spell level array -> {element: (normal_range, crit_range)}.

    The two effect lists are the normal and the critical effects, in no fixed
    order; the crit is the higher roll.
    """
    if not isinstance(level_arr, list) or len(level_arr) < 2:
        return {}
    a, b = _collect(level_arr[-2]), _collect(level_arr[-1])
    result = {}
    for elem in ('water', 'earth', 'air', 'fire', 'neutral'):
        ra, rb = a.get(elem), b.get(elem)
        if not ra and not rb:
            continue
        if ra and rb:
            normal, crit = (rb, ra) if ra[1] >= rb[1] else (ra, rb)
        else:
            normal = crit = (ra or rb)
        result[elem] = (normal, crit)
    return result


# Slots of the 21-wide level array carrying what a cast costs and how often the
# game allows it.
# Slot 15 is the critical hit rate as the X of 1/X, 0 when the spell cannot
# crit: it is the only slot that improves with the rank (151 spells of the 156
# that move it get a smaller X at a higher rank), while slot 14, the critical
# failure, sits at 100 for most spells and barely moves.
CASTING_SLOTS = {'cooldown': 6, 'per_turn': 7, 'per_target': 8, 'ap': 18,
                 'crit': 15}


def decode_casting(level_arr):
    """The cast cost and limits of one spell level."""
    out = {}
    if not isinstance(level_arr, list):
        return out
    for key, index in CASTING_SLOTS.items():
        if index < len(level_arr):
            value = level_arr[index]
            if isinstance(value, int) and not isinstance(value, bool):
                out[key] = value
    return out


def decode_spell(spell):
    """Retro spell record -> damage-spell dict, or None if it deals no damage."""
    per_level = []
    elements = []
    casting_levels = []
    for lv in LEVELS:
        if lv not in spell:
            continue
        decoded = decode_level(spell[lv])
        per_level.append(decoded)
        casting_levels.append(decode_casting(spell[lv]))
        for elem in decoded:
            if elem not in elements:
                elements.append(elem)
    if not elements or not per_level:
        return None
    non_crit_ranges, crit_ranges = [], []
    for elem in elements:
        nc, cr = [], []
        for decoded in per_level:
            normal, crit = decoded.get(elem, (None, None))
            nc.append('%d-%d' % normal if normal else '0-0')
            cr.append('%d-%d' % crit if crit else '0-0')
        non_crit_ranges.append(nc)
        crit_ranges.append(cr)
    # An absent limit reads 0 at every level, which would pass for a real one.
    casting = {}
    for key in CASTING_SLOTS:
        values = [level.get(key, 0) for level in casting_levels]
        if any(values):
            casting[key] = values
    return {
        'name': spell.get('n') or '',
        'level_count': len(per_level),
        'elements': elements,
        'non_crit_ranges': non_crit_ranges,
        'crit_ranges': crit_ranges,
        'casting': casting or None,
    }


# Element token -> dofus_constants constant name (NEUTRAL == 'neut', not 'neutral').
ELEMENT_TOKEN_TO_CONST = {
    'earth': 'EARTH', 'fire': 'FIRE', 'water': 'WATER', 'air': 'AIR',
    'neutral': 'NEUTRAL',
}


def _level_req(n):
    """Character level per spell rank: rank 6 needs level 100, ranks 1-5 are
    reachable at level 1 (Retro gates ranks by spell points, not level)."""
    if n <= 1:
        return [100]
    return [1] * (n - 1) + [100]


def emit_module(by_class, spell_names, path):
    """Write a Python module defining RETRO_DAMAGE_SPELLS (Spell/Effects objects)
    and RETRO_SPELL_NAMES ({french_name: {lang: localized_name}})."""
    lines = [
        "# AUTO-GENERATED by itemscraper/get_spells_retro.py -- do not edit by hand.",
        "# Dofus Retro (1.29) damage spells per class, decoded from the spell lang.",
        "from .dofus_constants import Spell, Effects, EARTH, FIRE, WATER, AIR, NEUTRAL",
        "",
        "RETRO_DAMAGE_SPELLS = {",
    ]
    for cls, spells in sorted(by_class.items()):
        lines.append("    %s: [" % json.dumps(cls))
        for s in sorted(spells, key=lambda sp: (sp['name'], sp['level_count'])):
            elems = ", ".join(ELEMENT_TOKEN_TO_CONST[e] for e in s['elements'])
            lines.append("        Spell(%s, %s, Effects(" % (
                json.dumps(s['name'], ensure_ascii=False),
                _level_req(s['level_count'])))
            lines.append("            %s," % json.dumps(s['non_crit_ranges']))
            lines.append("            %s," % json.dumps(s['crit_ranges']))
            lines.append("            [%s]," % elems)
            # The id ties the spell to what the game says about it, in
            # chardata/spell_reference/retro.json.
            tail = []
            if s.get('casting'):
                tail.append("casting=%s" % json.dumps(s['casting'],
                                                      sort_keys=True))
            if s.get('id') is not None:
                tail.append("spell_id=%d" % s['id'])
            lines.append("        )%s)," % (', ' + ', '.join(tail) if tail
                                            else ''))
        lines.append("    ],")
    lines.append("    'default': [],")
    lines.append("}")
    lines.append("")
    lines.append("RETRO_SPELL_NAMES = " + json.dumps(spell_names, ensure_ascii=False, indent=1, sort_keys=True))
    Path(path).write_text("\n".join(lines) + "\n", encoding='utf-8')


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
                decoded['id'] = spell_id
                damage_spells.append(decoded)
        by_class[app_name] = damage_spells
    return by_class, missing_classes


def build_spell_names(by_class, names_by_lang):
    """{french_name: {lang: localized_name}}; Spell.name carries the French name."""
    out = {}
    for spells in by_class.values():
        for s in spells:
            sid, fr = str(s.get('id')), s['name']
            names = {'fr': fr}
            for lang, id_to_name in names_by_lang.items():
                names[lang] = id_to_name.get(sid) or fr
            out[fr] = names
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    _here = Path(__file__).resolve().parent  # itemscraper/
    _root = _here.parent                     # repo root
    p.add_argument('--raw-dir', default=str(_here / 'retro_raw'))
    p.add_argument('--out', default=str(_here / 'retro' / 'retro_damage_spells.json'))
    p.add_argument('--module-out',
                   default=str(_root / 'fashionistapulp' / 'fashionistapulp'
                               / 'dofus_constants_retro_spells.py'),
                   help='Path for the generated RETRO_DAMAGE_SPELLS Python module')
    p.add_argument('--lang', default='fr')
    args = p.parse_args(argv)

    raw = Path(args.raw_dir)
    spells_root = json.loads((raw / f'spells_{args.lang}.json').read_text(encoding='utf-8'))['S']
    classes_root = json.loads((raw / f'classes_{args.lang}.json').read_text(encoding='utf-8'))['G']

    by_class, missing = build(spells_root, classes_root)

    # Every language is required: retro_raw is not committed, so run
    # download_retro_langs.py for the missing ones first.
    names_by_lang = {}
    for lang in ('en', 'es', 'pt', 'de'):
        path = raw / f'spells_{lang}.json'
        if not path.exists():
            sys.exit('missing %s: download the spell langs for every '
                     'language before regenerating the module' % path)
        lang_spells = json.loads(path.read_text(encoding='utf-8'))['S']
        names_by_lang[lang] = {k: v.get('n') for k, v in lang_spells.items()
                               if isinstance(v, dict) and v.get('n')}
    spell_names = build_spell_names(by_class, names_by_lang)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(by_class, ensure_ascii=False, indent=1), encoding='utf-8')

    if args.module_out:
        emit_module(by_class, spell_names, args.module_out)

    total = sum(len(v) for v in by_class.values())
    print(f"Wrote {total} damage spells across {len(by_class)} classes to {out_path}")
    if args.module_out:
        print(f"Wrote RETRO_DAMAGE_SPELLS module to {args.module_out}")
    if missing:
        print(f"  classes with no spell data in lang: {', '.join(missing)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
