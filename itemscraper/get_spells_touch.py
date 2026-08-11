#!/usr/bin/env python3
"""
Build the Dofus Touch damage-spells dataset (per class) from the Touch backend.

Unlike items, the spell data is fully in Touch's own data backend: Breeds gives
each class its spell ids (breedSpellsId), Spells gives each spell its grades
(spellLevels), and SpellLevels carries the per-grade effects, including separate
non-crit (`effects`) and crit (`criticalEffect`) lists, so no encyclopedia scrape
is needed. Elemental damage uses the same effect ids as items (96 Water, 97 Earth,
98 Air, 99 Fire, 100 Neutral); diceNum/diceSide are the min/max of the hit.

Output: fashionistapulp/dofus_constants_touch_spells.py defining TOUCH_DAMAGE_SPELLS
(Spell/Effects objects) and TOUCH_SPELL_NAMES ({fr_name: {lang: name}}), shaped
exactly like the retro module and consumed by chardata.spell_buffs.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import requests

LANGS = ['fr', 'en', 'es', 'pt', 'de']
CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json"
FALLBACK_DATA_URL = "https://dt-proxy-production-login.ankama-games.com"
UA = "Dofus/2 CFNetwork"
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
# Spell icons live on the assets CDN, prefixed "sort_" (from the client bundle).
SPELL_ICON_URL = "%s/gfx/spells/sort_%s.png"
SPELLS_STATIC = (Path(__file__).resolve().parent.parent / 'fashionsite' / 'chardata'
                 / 'static' / 'chardata' / 'spells' / 'touch')

# 96-100 = elemental damage, 91-95 = elemental steals (same hit, heals the
# caster); both families verified against the proxy Effects table.
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral',
                  91: 'water', 92: 'earth', 93: 'air', 94: 'fire', 95: 'neutral'}
ELEMENT_TOKEN_TO_CONST = {'earth': 'EARTH', 'fire': 'FIRE', 'water': 'WATER',
                          'air': 'AIR', 'neutral': 'NEUTRAL'}

# Touch breed id -> Fashionista class name (the 15 Touch classes).
CLASS_ID_TO_NAME = {
    1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor', 6: 'Ecaflip',
    7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida', 11: 'Sacrier', 12: 'Pandawa',
    13: 'Rogue', 14: 'Masqueraider', 15: 'Foggernaut',
}


def resolve_config():
    """Return (dataUrl, assetsUrl) from the live client config."""
    try:
        cfg = requests.get(CONFIG_URL + '?lang=fr', headers={'User-Agent': UA}, timeout=30).json()
        return ((cfg.get('dataUrl') or FALLBACK_DATA_URL).rstrip('/'),
                (cfg.get('assetsUrl') or '').rstrip('/'))
    except Exception:
        return FALLBACK_DATA_URL, ''


def download_spell_images(by_class, spells, assets_url):
    """Fetch each damage spell's icon from the Touch assets CDN, save it 96x96 under
    its French name (what spells_view expects: chardata/spells/touch/<name>.png)."""
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow not installed; skipping spell images", file=sys.stderr)
        return
    if not assets_url:
        print("  no assetsUrl; skipping spell images", file=sys.stderr)
        return
    SPELLS_STATIC.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    seen, written, missing = set(), 0, 0
    for class_spells in by_class.values():
        for s in class_spells:
            name = s['name']
            if name in seen:
                continue
            seen.add(name)
            icon_id = (spells.get(str(s['id'])) or {}).get('iconId')
            if icon_id is None:
                continue
            safe = re.sub(r'[\\/*?:"<>|]', '', name).strip()
            dest = SPELLS_STATIC / ('%s.png' % safe)
            try:
                r = session.get(SPELL_ICON_URL % (assets_url, icon_id),
                                headers={'User-Agent': WEB_UA}, timeout=30)
                if r.status_code != 200 or not r.content:
                    missing += 1
                    continue
                img = Image.open(io.BytesIO(r.content)).convert('RGBA').resize((96, 96), Image.LANCZOS)
                out = io.BytesIO()
                img.save(out, format='PNG')
                dest.write_bytes(out.getvalue())
                written += 1
            except Exception:
                missing += 1
    print(f"  spell images: written={written} missing={missing}")


def fetch_table(data_url, cls, lang='fr'):
    return requests.post(f"{data_url}/data/map", json={'class': cls, 'lang': lang},
                         headers={'User-Agent': UA, 'Accept': 'application/json'},
                         timeout=180).json()


def collect_damage(effect_list):
    """One effect list -> {element: (min, max)} for elemental damage hits.

    A spell level can carry several lines of the same element: state-dependent
    branches (targetMask '#A,E<state>' or 'v50') and damage/steal pairs. Keep
    the strongest line per element (by midpoint): mutually exclusive branches
    resolve to the best case, which is also how the aggregated Dofus 3 spells
    are modeled ("Hit in best element")."""
    out = {}
    for e in (effect_list or []):
        eid = e.get('effectId')
        if eid in DAMAGE_EFFECTS:
            lo = e.get('diceNum') or 0
            hi = e.get('diceSide') or 0
            if hi < lo:                      # diceSide==0 (or < min) => fixed hit
                hi = lo
            elem = DAMAGE_EFFECTS[eid]
            prev = out.get(elem)
            if prev is None or lo + hi > prev[0] + prev[1]:
                out[elem] = (lo, hi)
    return out


# What a cast costs and how often the game allows it. The level dict carried
# these all along and decode_spell read past them, so Touch shipped no casting
# data at all and the combo panel never appeared on that version.
CASTING_FIELDS = {'ap': 'apCost', 'per_turn': 'maxCastPerTurn',
                  'per_target': 'maxCastPerTarget', 'cooldown': 'minCastInterval'}


def decode_spell(spell, spell_levels):
    """Touch spell -> damage-spell dict, or None if it deals no elemental damage."""
    per_nc, per_cr, levels_req, elements, stacks = [], [], [], [], []
    casting_levels = []
    for lid in (spell.get('spellLevels') or []):
        lv = spell_levels.get(str(lid))
        if not lv:
            continue
        nc = collect_damage(lv.get('effects'))
        cr = collect_damage(lv.get('criticalEffect'))
        per_nc.append(nc)
        per_cr.append(cr)
        levels_req.append(max(1, int(lv.get('minPlayerLevel') or 1)))
        try:
            stack = int(lv.get('maxStack') or 0)
        except (TypeError, ValueError):
            stack = 0
        if stack > 1:
            stacks.append(stack)
        level_casting = {}
        for key, field in CASTING_FIELDS.items():
            try:
                level_casting[key] = int(lv.get(field) or 0)
            except (TypeError, ValueError):
                level_casting[key] = 0
        casting_levels.append(level_casting)
        for elem in list(nc) + list(cr):
            if elem not in elements:
                elements.append(elem)
    if not elements:
        return None
    non_crit, crit = [], []
    for elem in elements:
        nc_row, cr_row = [], []
        for i in range(len(per_nc)):
            n = per_nc[i].get(elem)
            c = per_cr[i].get(elem) or n
            nc_row.append('%d-%d' % n if n else '0-0')
            cr_row.append('%d-%d' % c if c else '0-0')
        non_crit.append(nc_row)
        crit.append(cr_row)
    return {
        'id': spell['id'],
        'name': spell.get('nameId') or '',
        'levels_req': levels_req,
        'elements': elements,
        'non_crit_ranges': non_crit,
        'crit_ranges': crit,
        # The buff can accumulate (maxStack in the game data): the damage
        # simulator shows the multiplier like on Dofus 3.
        'stacks': max(stacks) if stacks else None,
        # A key only ships when some level uses it: a spell with no per-turn
        # cap reads 0 everywhere, and an all-zero list would read as a limit.
        'casting': {key: [level[key] for level in casting_levels]
                    for key in CASTING_FIELDS
                    if any(level[key] for level in casting_levels)} or None,
    }


def build(breeds, spells, spell_levels):
    by_class = {}
    for bid, app_name in CLASS_ID_TO_NAME.items():
        breed = breeds.get(str(bid))
        spell_ids = (breed or {}).get('breedSpellsId') or []
        damage_spells = []
        seen = set()
        for sid in spell_ids:
            spell = spells.get(str(sid))
            if not spell or sid in seen:
                continue
            seen.add(sid)
            decoded = decode_spell(spell, spell_levels)
            if decoded:
                damage_spells.append(decoded)
        by_class[app_name] = damage_spells
    return by_class


def build_spell_names(by_class, spells_by_lang):
    """{fr_name: {lang: localized name}} for every damage spell."""
    out = {}
    for spells in by_class.values():
        for s in spells:
            sid = str(s['id'])
            fr = s['name']
            names = {}
            for lang in LANGS:
                rec = (spells_by_lang.get(lang) or {}).get(sid)
                names[lang] = (rec or {}).get('nameId') or fr
            out[fr] = names
    return out


def emit_module(by_class, spell_names, path):
    lines = [
        "# AUTO-GENERATED by itemscraper/get_spells_touch.py -- do not edit by hand.",
        "# Dofus Touch damage spells per class, decoded from the Touch spell data.",
        "from .dofus_constants import Spell, Effects, EARTH, FIRE, WATER, AIR, NEUTRAL",
        "",
        "TOUCH_DAMAGE_SPELLS = {",
    ]
    for cls, spells in sorted(by_class.items()):
        lines.append("    %s: [" % json.dumps(cls))
        for s in sorted(spells, key=lambda sp: (sp['name'], sp['id'])):
            elems = ", ".join(ELEMENT_TOKEN_TO_CONST[e] for e in s['elements'])
            lines.append("        Spell(%s, %s, Effects(" % (
                json.dumps(s['name'], ensure_ascii=False), s['levels_req']))
            lines.append("            %s," % json.dumps(s['non_crit_ranges']))
            lines.append("            %s," % json.dumps(s['crit_ranges']))
            lines.append("            [%s]," % elems)
            tail = []
            if s.get('stacks'):
                tail.append("stacks=%d" % s['stacks'])
            if s.get('casting'):
                tail.append("casting=%s" % json.dumps(s['casting'], sort_keys=True))
            lines.append("        )%s)," % (", " + ", ".join(tail) if tail else ""))
        lines.append("    ],")
    lines.append("    'default': [],")
    lines.append("}")
    lines.append("")
    lines.append("TOUCH_SPELL_NAMES = " + json.dumps(spell_names, ensure_ascii=False, indent=1, sort_keys=True))
    Path(path).write_text("\n".join(lines) + "\n", encoding='utf-8')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--module-out',
                   default=str(Path(__file__).resolve().parent.parent
                               / 'fashionistapulp' / 'fashionistapulp'
                               / 'dofus_constants_touch_spells.py'))
    p.add_argument('--skip-images', action='store_true', help='Skip the spell-icon download')
    args = p.parse_args(argv)

    data_url, assets_url = resolve_config()
    print(f"Dofus Touch data proxy: {data_url}")
    breeds = fetch_table(data_url, 'Breeds')
    spell_levels = fetch_table(data_url, 'SpellLevels')
    spells_by_lang = {lang: fetch_table(data_url, 'Spells', lang) for lang in LANGS}
    spells = spells_by_lang['fr']
    print(f"  Breeds={len(breeds)} Spells={len(spells)} SpellLevels={len(spell_levels)}")

    by_class = build(breeds, spells, spell_levels)
    spell_names = build_spell_names(by_class, spells_by_lang)
    emit_module(by_class, spell_names, args.module_out)

    total = sum(len(v) for v in by_class.values())
    print(f"Wrote {total} damage spells across {len(by_class)} classes to {args.module_out}")
    empty = [c for c, v in by_class.items() if not v]
    if empty:
        print("  classes with no damage spells: " + ", ".join(empty))

    if not args.skip_images:
        download_spell_images(by_class, spells, assets_url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
