#!/usr/bin/env python3
"""Extract Dofus Retro damage spells per class from the spell lang files.

    python get_spells_retro.py [--raw-dir retro_raw] [--module-out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Retro effect id -> element. 96-100 damage, 91-95 steals
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral',
                  91: 'water', 92: 'earth', 93: 'air', 94: 'fire', 95: 'neutral'}

# Not read: 88, 89 and 672 hit for a share of the caster's HP


# Retro numbers its effects its own way: 138 is % damage there, our Power
CHARACTERISTIC_EFFECTS = {118: 'buff_str', 119: 'buff_agi', 123: 'buff_cha',
                          126: 'buff_int', 125: 'buff_vit', 138: 'buff_pow'}
ROW_EFFECTS = dict(DAMAGE_EFFECTS)
ROW_EFFECTS.update(CHARACTERISTIC_EFFECTS)

# spells_view translates this label
RANDOM_ELEMENT_LABEL = 'Hit in one random element'

# Elemental rows that are one random roll; 1.29 says so only in the text
ONE_ELEMENT_AT_RANDOM = {
    109: "ou d'eau",                       # Ecaflip, Bluff
}


# Slot 3 of an effect row is its chance in percent; one draw sums to 100
CHANCE_SLOT = 3


def _screen_random_element(spell, spell_id):
    """Stop if the text or the draw no longer says one random element."""
    quote = ONE_ELEMENT_AT_RANDOM.get(spell_id)
    if quote is None:
        return
    text = (spell.get('d') or '').lower()
    if quote not in text:
        raise SystemExit(
            'retro spell %s no longer says %r, so nothing says its elemental '
            'rows are one roll rather than several hits. Re-read Ankama '
            'before regenerating. It now says: %r'
            % (spell_id, quote, (spell.get('d') or '')[:160]))
    for rank in ('l1', 'l2', 'l3', 'l4', 'l5', 'l6'):
        level = spell.get(rank)
        if not isinstance(level, list) or len(level) < 2:
            continue
        for effects in (level[-2], level[-1]):
            chances = [effect[CHANCE_SLOT] for effect in (effects or [])
                       if isinstance(effect, list)
                       and len(effect) > CHANCE_SLOT and effect[CHANCE_SLOT]]
            if not chances:
                continue
            if sum(chances) != 100 or len(set(chances)) != 1:
                raise SystemExit(
                    'retro spell %s rank %s is no longer drawn evenly: its '
                    'rows carry %s. The turn averages its faces, so re-read '
                    'Ankama before regenerating.'
                    % (spell_id, rank, chances))


def emit_aggregates(spell_id, elements):
    """One group per row when the rows are one roll, else None."""
    if spell_id not in ONE_ELEMENT_AT_RANDOM:
        return None
    if len(elements) < 2 or any(str(t).startswith('buff_') for t in elements):
        return None
    return [(RANDOM_ELEMENT_LABEL if index == 0 else '', [index])
            for index in range(len(elements))]


# Buffs that are not the caster's; the target codes in slot 5 can't tell
NOT_A_SELF_BUFF = {
    # Ecaflip, Roulette: one random effect, on random targets
    101: 'sur vos adversaires',
    # Osamodas, Resistance Naturelle: summons and allies only
    32: 'des invocations',
    # Osamodas, Crocs du Mulou
    29: 'des invocations',
}

# Words in a buff description that name someone other than the caster
SOMEBODY_ELSE = ('invocation', 'alli', 'adversaire', 'ennemi',
                 'autres personnages')

BUFFS_THE_CASTER_TOO = {
    # Enutrof, Cupidite: every player, the caster included
    52: 'tous les joueurs',
    # Iop, Puissance
    153: 'le lanceur ou un alli',
}


def _not_a_self_buff(spell, spell_id):
    """True when this spell's buff rows are not the caster's."""
    quote = NOT_A_SELF_BUFF.get(spell_id)
    if quote is None:
        return False
    text = str(spell.get('d') or '')
    if quote.lower() not in text.lower():
        raise SystemExit(
            'retro spell %s no longer says %r; re-read its description before '
            'trusting this exclusion' % (spell_id, quote))
    return True


def _screen_kept_buff(spell, spell_id):
    """Stop if a kept buff's description names someone else."""
    text = str(spell.get('d') or '')
    lowered = text.lower()
    named = [word for word in SOMEBODY_ELSE if word in lowered]
    if not named:
        return
    quote = BUFFS_THE_CASTER_TOO.get(spell_id)
    if quote is None:
        raise SystemExit(
            'retro spell %s (%s) keeps a characteristic buff and its own '
            'description names %s. Settle it in NOT_A_SELF_BUFF or in '
            'BUFFS_THE_CASTER_TOO before regenerating. Ankama wrote: %r'
            % (spell_id, spell.get('n'), '/'.join(named), text[:160]))
    if quote.lower() not in lowered:
        raise SystemExit(
            'retro spell %s no longer says %r; re-read it before trusting that '
            'the caster is among those it buffs' % (spell_id, quote))

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
    """One effect list -> {row token: (min, max)}, strongest line per token."""
    out = {}
    for e in (effect_list or []):
        if isinstance(e, list) and len(e) >= 2 and e[-1] in ROW_EFFECTS:
            rng = dice_range(e[0])
            if rng:
                elem = ROW_EFFECTS[e[-1]]
                prev = out.get(elem)
                if prev is None or rng[0] + rng[1] > prev[0] + prev[1]:
                    out[elem] = rng
    return out


def decode_level(level_arr):
    """Spell level array -> {element: (normal_range, crit_range)}."""
    if not isinstance(level_arr, list) or len(level_arr) < 2:
        return {}
    critical, normal = _collect(level_arr[-2]), _collect(level_arr[-1])
    result = {}
    tokens = list(('water', 'earth', 'air', 'fire', 'neutral'))
    tokens += sorted((set(critical) | set(normal)) - set(tokens))
    for elem in tokens:
        hit, crit = normal.get(elem), critical.get(elem)
        if not hit and not crit:
            continue
        # No crit row when the spell cannot crit
        result[elem] = (hit or crit, crit or hit)
    return result


# Level array slots; 15 is the crit rate as X of 1/X, 0 if it cannot crit
CASTING_SLOTS = {'cooldown': 6, 'per_turn': 7, 'per_target': 8, 'ap': 18,
                 'crit': 15}

# Slot 2 is the character level the rank asks for
LEVEL_REQ_SLOT = 2


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


def decode_spell(spell, spell_id=None):
    """Retro spell record -> damage-spell dict, or None if it carries no row."""
    drop_buffs = _not_a_self_buff(spell, spell_id)
    _screen_random_element(spell, spell_id)
    per_level = []
    elements = []
    casting_levels = []
    level_reqs = []
    for lv in LEVELS:
        if lv not in spell:
            continue
        decoded = decode_level(spell[lv])
        if drop_buffs:
            decoded = {token: value for token, value in decoded.items()
                       if not token.startswith('buff_')}
        per_level.append(decoded)
        casting_levels.append(decode_casting(spell[lv]))
        arr = spell[lv]
        level_reqs.append(arr[LEVEL_REQ_SLOT]
                          if isinstance(arr, list)
                          and len(arr) > LEVEL_REQ_SLOT
                          and isinstance(arr[LEVEL_REQ_SLOT], int)
                          and not isinstance(arr[LEVEL_REQ_SLOT], bool)
                          else None)
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
    # All zeros means no limit
    casting = {}
    for key in CASTING_SLOTS:
        values = [level.get(key, 0) for level in casting_levels]
        if any(values):
            casting[key] = values
    groupes = emit_aggregates(spell_id, elements)
    return {
        'name': spell.get('n') or '',
        'level_count': len(per_level),
        'level_reqs': level_reqs,
        'elements': elements,
        'non_crit_ranges': non_crit_ranges,
        'crit_ranges': crit_ranges,
        'casting': casting or None,
        # Rows that are one roll, not a sum
        **({'aggregates': groupes} if groupes else {}),
    }


# Element token -> dofus_constants constant name (NEUTRAL == 'neut', not 'neutral').
ELEMENT_TOKEN_TO_CONST = {
    'earth': 'EARTH', 'fire': 'FIRE', 'water': 'WATER', 'air': 'AIR',
    'neutral': 'NEUTRAL',
}
# Buff rows go in as plain strings
ELEMENT_TOKEN_TO_CONST.update(
    {token: repr(token) for token in CHARACTERISTIC_EFFECTS.values()})


def _level_req(level_reqs, name=''):
    """Character level per spell rank."""
    read = [value for value in level_reqs if value is not None]
    if len(read) != len(level_reqs) or not read:
        raise ValueError('no level requirement for %s: %s'
                         % (name or '?', level_reqs))
    # The site's rank reader needs levels that never go down
    floor = read[0]
    out = []
    for value in read:
        floor = max(floor, value)
        out.append(floor)
    return out


def emit_module(by_class, spell_names, path):
    """Write the RETRO_DAMAGE_SPELLS and RETRO_SPELL_NAMES module."""
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
                _level_req(s['level_reqs'], s['name'])))
            lines.append("            %s," % json.dumps(s['non_crit_ranges']))
            lines.append("            %s," % json.dumps(s['crit_ranges']))
            lines.append("            [%s]," % elems)
            # spell_id is the key in chardata/spell_reference/retro.json
            tail = []
            if s.get('aggregates'):
                tail.append("aggregates=%r" % (s['aggregates'],))
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
            decoded = decode_spell(spell, spell_id)
            if decoded and any(str(token).startswith('buff_')
                               for token in decoded.get('elements') or []):
                _screen_kept_buff(spell, spell_id)
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

    # retro_raw is not committed: run download_retro_langs.py first
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
