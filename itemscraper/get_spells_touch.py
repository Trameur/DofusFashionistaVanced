#!/usr/bin/env python3
"""
Build the Dofus Touch damage spells per class from the Touch backend.

Output: fashionistapulp/dofus_constants_touch_spells.py
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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fashionistapulp'))

from fashionistapulp.reserved_filenames import safe_asset_stem  # noqa: E402

# Spell icons live on the assets CDN, prefixed "sort_".
SPELL_ICON_URL = "%s/gfx/spells/sort_%s.png"
SPELLS_STATIC = (Path(__file__).resolve().parent.parent / 'fashionsite' / 'chardata'
                 / 'static' / 'chardata' / 'spells' / 'touch')

# 96-100 elemental damage, 91-95 elemental steals (same hit, heals the caster).
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral',
                  91: 'water', 92: 'earth', 93: 'air', 94: 'fire', 95: 'neutral'}

# "#1 a #2 (meilleur element)": one hit in the caster's best element
BEST_ELEMENT_EFFECT = 1200

# Same label as the Dofus 3 table
BEST_ELEMENT_LABEL = 'Hit in best element'

# Not read: 293 (base damage bonus) and 2812 (% spell damage, Exaltation)

# Buffs and steals in points (1033/1078 are %). A steal counts as a self-buff
CHARACTERISTIC_EFFECTS = {
    138: 'buff_pow',
    118: 'buff_str', 119: 'buff_agi', 123: 'buff_cha', 126: 'buff_int',
    124: 'buff_wis', 125: 'buff_vit',
    271: 'buff_str', 268: 'buff_agi', 266: 'buff_cha', 269: 'buff_int',
    270: 'buff_wis', 267: 'buff_vit',
}
ROW_EFFECTS = dict(DAMAGE_EFFECTS)
ROW_EFFECTS.update(CHARACTERISTIC_EFFECTS)

# Buffs that don't reach the caster, with the description fragment that says so
NOT_A_SELF_BUFF = {
    52: 'augmente la puissance de tous les alli',          # Enutrof Cupidite
    9919: 'puissance des invocations',                     # Osamodas Crocs du Mulou
    3215: 'Sur un alli',                                   # Foggernaut Evolution
    9685: 'bonus Puissance sur les alli',                  # Osamodas Fouet
    # Ecaflip Roulette: fires one random effect
    7449: 'effet al',
}

# A kept buff whose description names one of these must be settled in a table
SOMEBODY_ELSE = ('invocation', 'alli', 'adversaire', 'ennemi')

BUFFS_THE_CASTER_TOO = {
    # Cra, Maitrise de l'Arc: allies and the caster
    5523: 'plus important sur le lanceur',
    # Iop, Puissance
    8137: 'le lanceur gagne',
    # Ecaflip, Perception
    7463: 'plus faible sur les alli',
    # Rogue, Dernier Souffle
    2810: 'Puissance du lanceur',
    # Xelor, Vortex: when the caster is targeted
    9737: 'Si le lanceur est cibl',
    # Xelor, Poussiere Temporelle: a Wisdom steal
    8031: 'vole de la Sagesse aux adversaires',
    # Sram, Larcin: an Intelligence steal
    8747: "l'Intelligence",
}

ELEMENT_TOKEN_TO_CONST = {'earth': 'EARTH', 'fire': 'FIRE', 'water': 'WATER',
                          'air': 'AIR', 'neutral': 'NEUTRAL'}
# Buff rows are quoted strings, like in the Dofus 2 and 3 tables
ELEMENT_TOKEN_TO_CONST.update(
    {token: repr(token) for token in CHARACTERISTIC_EFFECTS.values()})

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


def class_spells(breeds, spells):
    """{class: [spell rows]} for the whole book, damage spells or not."""
    out = {}
    for bid, app_name in CLASS_ID_TO_NAME.items():
        breed = breeds.get(str(bid)) or {}
        out[app_name] = [spells[str(sid)] for sid in breed.get('breedSpellsId') or []
                         if str(sid) in spells]
    return out


def download_spell_images(by_class, spells, assets_url):
    """Save each class spell's icon 96x96 as chardata/spells/touch/<French name>.png."""
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
            name = s.get('name') or s.get('nameId')
            if not name or name in seen:
                continue
            seen.add(name)
            icon_id = (spells.get(str(s['id'])) or {}).get('iconId')
            if icon_id is None:
                continue
            safe = safe_asset_stem(re.sub(r'[\\/*?:"<>|]', '', name).strip())
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


# Row triggers: "I" on cast, "TB" at turn begin, "TE" at turn end
DELAYED_TRIGGERS = {'TB': 'turn_begin', 'TE': 'turn_end'}


def when_it_lands(triggers):
    """The moment a row waits for, or None when it lands with the cast."""
    codes = {code for code in str(triggers or '').split('|') if code}
    if len(codes) != 1:
        return None
    return DELAYED_TRIGGERS.get(next(iter(codes)))


# No neutral: it scales on Strength like Earth, so it is never the best
BEST_ELEMENT_TOKENS = ('earth', 'fire', 'water', 'air')

# Spells whose only damage is the best-element row, with the fragment that says so
BEST_ELEMENT_IS_THE_WHOLE_HIT = {
    5513: 'occasionne des dommages dans le meilleur ',   # Cra, Fleche Cinglante
    5901: 'occasionne des dommages dans le meilleur ',   # Sacrieur, Punition
    7987: 'occasionne des dommages dans le meilleur ',   # Xelor, Vol du Temps
    8131: 'dommages en croix dans le meilleur ',         # Iop, Epee Divine
    8133: 'occasionne des dommages dans le meilleur ',   # Iop, Intimidation
    12433: 'occasionne des dommages dans le meilleur ',  # Sacrieur, Projection
}

# Left out: 6997 (the thrown target deals it), 9685 (kills a summon), 6095 (state)


def _best_element_is_the_whole_hit(spell):
    """True when Ankama's sentence says the best-element row is the caster's hit."""
    quote = BEST_ELEMENT_IS_THE_WHOLE_HIT.get(spell.get('id'))
    if quote is None:
        return False
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    if quote.lower() not in str(text).lower():
        raise SystemExit(
            'touch spell %s no longer says %r, so nothing says its '
            'best-element row is damage the caster deals. Re-read Ankama '
            'before regenerating. It now says: %r'
            % (spell.get('id'), quote, str(text)[:200]))
    return True


def collect_damage(effect_list, best_element_rows=False):
    """One effect list -> {row token: (min, max, when)}, strongest line per token."""
    out = {}
    for e in (effect_list or []):
        eid = e.get('effectId')
        if eid == BEST_ELEMENT_EFFECT and best_element_rows:
            # One row per element, emit_aggregates groups them as one hit
            tokens = BEST_ELEMENT_TOKENS
        elif eid in ROW_EFFECTS:
            tokens = (ROW_EFFECTS[eid],)
        else:
            continue
        lo = e.get('diceNum') or 0
        hi = e.get('diceSide') or 0
        if hi < lo:                          # diceSide==0 (or < min) => fixed hit
            hi = lo
        for elem in tokens:
            prev = out.get(elem)
            if prev is None or lo + hi > prev[0] + prev[1]:
                out[elem] = (lo, hi, when_it_lands(e.get('triggers')))
    return out


# dice min names the placed spell (a bomb monster for 1008), dice max its grade
PLACED_BY_EFFECT = {
    400: ('trap', 'trap'),
    401: ('glyph', 'turn_begin'),
    402: ('glyph', 'turn_end'),
    1091: ('glyph', 'aura'),
    1008: ('bomb', 'bomb'),
}
BOMB_EFFECT_ID = 1008
# The table naming each bomb monster's explosion spell
BOMB_TABLE = 'SpellBombs'
# Damage that waits for something (an enemy, a detonation, a state); the rest is only late
PLACED_WAITS = frozenset(('trap', 'bomb', 'glyph', 'aura', 'state'))
# The heads generate_damage_spells.py writes; the site reads these
PLACED_LABELS = {'trap': 'Trap damage', 'glyph': 'Glyph damage', 'bomb': 'Bomb damage'}
# "A,*E951": a placement made only in that state
STATE_IN_TARGET_MASK = re.compile(r'\b\*?[eE]\d+\b')


def placed_child(effect, spells, bombs):
    """(spell id, grade) of the thing a placing effect puts down, or None."""
    effect_id = effect.get('effectId')
    if effect_id not in PLACED_BY_EFFECT:
        return None
    target, grade = effect.get('diceNum'), effect.get('diceSide')
    if effect_id == BOMB_EFFECT_ID:
        target = ((bombs or {}).get(str(target)) or {}).get('explodSpellId')
    if not target or str(target) not in (spells or {}):
        return None
    return int(target), int(grade or 0)


def child_rank(child, grade, spell_levels):
    """The child's record at that grade: rank N is its Nth level."""
    level_ids = child.get('spellLevels') or []
    if not 1 <= grade <= len(level_ids):
        return {}
    return spell_levels.get(str(level_ids[grade - 1])) or {}


def _damage_only(rows):
    return {token: value for token, value in rows.items()
            if not str(token).startswith('buff_')}


def placed_blocks(placements, gated, spells, spell_levels):
    """One block per placed thing, its rows read at the grade each rank places."""
    blocks = []
    for (effect_id, child_id), grades in placements.items():
        child = spells[str(child_id)]
        per_nc, per_cr, tokens = [], [], []
        for grade in grades:
            rank = child_rank(child, grade, spell_levels) if grade else {}
            for key in ('effects', 'criticalEffect'):
                if any(row.get('effectId') == BEST_ELEMENT_EFFECT
                       for row in (rank.get(key) or [])):
                    raise SystemExit(
                        'touch spell %s places %s, which hits in the best '
                        'element; that block has no rule yet'
                        % (effect_id, child_id))
            nc = _damage_only(collect_damage(rank.get('effects')))
            cr = _damage_only(collect_damage(rank.get('criticalEffect')))
            per_nc.append(nc)
            per_cr.append(cr)
            for token in list(nc) + list(cr):
                if token not in tokens:
                    tokens.append(token)
        if not tokens:
            continue
        kind, when = PLACED_BY_EFFECT[effect_id]
        if (effect_id, child_id) in gated:
            when = 'state'
        blocks.append({'kind': kind, 'when': when, 'tokens': tokens,
                       'per_nc': per_nc, 'per_cr': per_cr})
    return blocks


def _own_groups(aggregates, elements):
    """The spell's own rows as groups, so a placed block can follow them."""
    if aggregates:
        return [(label, list(indices)) for label, indices in aggregates]
    damage = [index for index, token in enumerate(elements)
              if not str(token).startswith('buff_')]
    groups = [('', damage)] if damage else []
    groups.extend(('', [index]) for index, token in enumerate(elements)
                  if str(token).startswith('buff_'))
    return groups


# Touch uses the same percentage crit as Dofus
CASTING_FIELDS = {'ap': 'apCost', 'per_turn': 'maxCastPerTurn',
                  'per_target': 'maxCastPerTarget', 'cooldown': 'minCastInterval',
                  'crit': 'criticalHitProbability'}


def _check_still_says(spell):
    """True when NOT_A_SELF_BUFF excludes the spell; stops if its quote is gone."""
    quote = NOT_A_SELF_BUFF.get(spell.get('id'))
    if quote is None:
        return False
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    if quote.lower() not in str(text).lower():
        raise SystemExit(
            'spell %s no longer says %r; its buff was excluded on that '
            'sentence and the exclusion has to be decided again'
            % (spell.get('id'), quote))
    return True


def _description_of(spell):
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    return str(text)


def _screen_kept_buff(spell):
    """Stop the run if a kept buff's description names somebody else."""
    text = _description_of(spell)
    lowered = text.lower()
    named = [word for word in SOMEBODY_ELSE if word in lowered]
    if not named:
        return
    spell_id = spell.get('id')
    quote = BUFFS_THE_CASTER_TOO.get(spell_id)
    if quote is None:
        raise SystemExit(
            'touch spell %s (%s) keeps a characteristic buff and its own '
            'description names %s. Settle it in NOT_A_SELF_BUFF or in '
            'BUFFS_THE_CASTER_TOO before regenerating. Ankama wrote: %r'
            % (spell_id, spell.get('nameId'), '/'.join(named), text[:160]))
    if quote.lower() not in lowered:
        raise SystemExit(
            'touch spell %s no longer says %r; re-read it before trusting that '
            'the caster is among those it buffs' % (spell_id, quote))


def _says_best_element(level):
    """Does this grade carry Ankama's best-element row?"""
    for key in ('effects', 'criticalEffect'):
        for row in (level.get(key) or []):
            if isinstance(row, dict) and row.get('effectId') == BEST_ELEMENT_EFFECT:
                return True
    return False


# Spells whose named rows land beside the best-element hit, not as its faces
NAMED_ROWS_ALSO_LAND = {
    3218: 'Feu, Eau et Terre ainsi que',        # Foggernaut Embuscade
    7612: 'Air, Eau, Terre et dans le meilleur',  # Ecaflip Fanfaronnade
}


def _named_rows_also_land(spell):
    """True when Ankama's sentence says the named rows land with the best one."""
    quote = NAMED_ROWS_ALSO_LAND.get(spell.get('id'))
    if quote is None:
        return False
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    if quote.lower() not in str(text).lower():
        raise SystemExit(
            'touch spell %s no longer says %r, so nothing says its named '
            'elemental rows land beside the best-element hit. Re-read Ankama '
            'before regenerating. It now says: %r'
            % (spell.get('id'), quote, str(text)[:200]))
    return True


def emit_aggregates(best_element, elements, spell=None):
    """One group per row when the rows are alternatives, else None."""
    if not best_element or len(elements) < 2:
        return None
    if any(str(token).startswith('buff_') for token in elements):
        return None
    if spell is not None and _named_rows_also_land(spell):
        return None
    return [(BEST_ELEMENT_LABEL if index == 0 else '', [index])
            for index in range(len(elements))]


def decode_spell(spell, spell_levels, spells=None, bombs=None):
    """Touch spell -> damage-spell dict (buff-only spells kept), or None if no row."""
    per_nc, per_cr, levels_req, elements, stacks = [], [], [], [], []
    casting_levels = []
    best_element = False
    # {(effect id, child id): {rank index: grade}} of the things the spell places
    placements, gated = {}, set()
    # True when the only damage is the best-element row
    lire_le_meilleur = _best_element_is_the_whole_hit(spell)
    for lid in (spell.get('spellLevels') or []):
        lv = spell_levels.get(str(lid))
        if not lv:
            continue
        best_element = best_element or _says_best_element(lv)
        for effect in lv.get('effects') or []:
            child = placed_child(effect, spells, bombs)
            if child is None:
                continue
            key = (effect.get('effectId'), child[0])
            placements.setdefault(key, {}).setdefault(len(per_nc), child[1])
            if STATE_IN_TARGET_MASK.findall(str(effect.get('targetMask') or '')):
                gated.add(key)
        nc = collect_damage(lv.get('effects'), lire_le_meilleur)
        cr = collect_damage(lv.get('criticalEffect'), lire_le_meilleur)
        if _check_still_says(spell):
            # The buff goes to someone else, keep only the damage
            nc = {k: v for k, v in nc.items() if not k.startswith('buff_')}
            cr = {k: v for k, v in cr.items() if not k.startswith('buff_')}
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
    blocks = placed_blocks(
        {key: [grades.get(index) for index in range(len(per_nc))]
         for key, grades in placements.items()},
        gated, spells, spell_levels)
    if not elements and not blocks:
        return None

    def when_by_row(per_level):
        """{row index: moment}, and only when every rank that has it agrees."""
        late = {}
        for index, elem in enumerate(elements):
            moments = {level[elem][2] for level in per_level if elem in level}
            if len(moments) == 1:
                moment = moments.pop()
                if moment:
                    late[index] = moment
        return late

    def rows_of(per_nc_levels, per_cr_levels, elem):
        """The ladder of one row, a crit rank falling back on the plain one."""
        nc_row, cr_row = [], []
        for i in range(len(per_nc_levels)):
            n = per_nc_levels[i].get(elem)
            c = per_cr_levels[i].get(elem) or n
            nc_row.append('%d-%d' % (n[0], n[1]) if n else '0-0')
            cr_row.append('%d-%d' % (c[0], c[1]) if c else '0-0')
        return nc_row, cr_row

    non_crit, crit = [], []
    for elem in elements:
        nc_row, cr_row = rows_of(per_nc, per_cr, elem)
        non_crit.append(nc_row)
        crit.append(cr_row)
    # Rows that are alternatives, not a sum. See emit_aggregates.
    aggregates = emit_aggregates(best_element, elements, spell)
    delayed = when_by_row(per_nc)
    delayed_crit = when_by_row(per_cr)
    if delayed_crit == delayed:
        delayed_crit = None
    conditional = {}
    if blocks:
        # The placed things' rows after the spell's own, each block a labelled group
        aggregates = _own_groups(aggregates, elements)
    for block in blocks:
        start = len(elements)
        for token in block['tokens']:
            nc_row, cr_row = rows_of(block['per_nc'], block['per_cr'], token)
            non_crit.append(nc_row)
            crit.append(cr_row)
            elements.append(token)
        indices = list(range(start, len(elements)))
        aggregates.append((PLACED_LABELS[block['kind']], indices))
        for index in indices:
            if block['when'] in PLACED_WAITS:
                conditional[index] = block['when']
            else:
                delayed[index] = block['when']
                if delayed_crit is not None:
                    delayed_crit[index] = block['when']
    return {
        'id': spell['id'],
        'name': spell.get('nameId') or '',
        'levels_req': levels_req,
        'elements': elements,
        'non_crit_ranges': non_crit,
        'crit_ranges': crit,
        'aggregates': aggregates,
        # maxStack in the game data: the buff can accumulate.
        'stacks': max(stacks) if stacks else None,
        # A cast limit of 0 means no limit, so all-zero keys are dropped.
        'casting': {key: [level[key] for level in casting_levels]
                    for key in CASTING_FIELDS
                    if any(level[key] for level in casting_levels)} or None,
        'conditional': conditional or None,
        'delayed': delayed or None,
        'delayed_crit': delayed_crit,
    }


def build(breeds, spells, spell_levels, bombs=None):
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
            decoded = decode_spell(spell, spell_levels, spells, bombs)
            if decoded and any(str(token).startswith('buff_')
                               for token in decoded.get('elements') or []):
                _screen_kept_buff(spell)
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
            if s.get('aggregates'):
                tail.append("aggregates=%r" % (s['aggregates'],))
            if s.get('stacks'):
                tail.append("stacks=%d" % s['stacks'])
            if s.get('casting'):
                tail.append("casting=%s" % json.dumps(s['casting'], sort_keys=True))
            # Links to chardata/spell_reference/touch.json
            if s.get('id') is not None:
                tail.append("spell_id=%d" % s['id'])
            # repr, not json: json would turn the int row index into "0"
            if s.get('conditional'):
                tail.append("conditional=%r"
                            % (dict(sorted(s['conditional'].items())),))
            if s.get('delayed'):
                tail.append("delayed=%r" % (dict(sorted(s['delayed'].items())),))
            if s.get('delayed_crit') is not None:
                tail.append("delayed_crit=%r"
                            % (dict(sorted(s['delayed_crit'].items())),))
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
    bombs = fetch_table(data_url, BOMB_TABLE)
    print(f"  Breeds={len(breeds)} Spells={len(spells)} SpellLevels={len(spell_levels)} "
          f"{BOMB_TABLE}={len(bombs)}")

    by_class = build(breeds, spells, spell_levels, bombs)
    spell_names = build_spell_names(by_class, spells_by_lang)
    emit_module(by_class, spell_names, args.module_out)

    total = sum(len(v) for v in by_class.values())
    print(f"Wrote {total} damage spells across {len(by_class)} classes to {args.module_out}")
    empty = [c for c, v in by_class.items() if not v]
    if empty:
        print("  classes with no damage spells: " + ", ".join(empty))

    if not args.skip_images:
        download_spell_images(class_spells(breeds, spells), spells, assets_url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
