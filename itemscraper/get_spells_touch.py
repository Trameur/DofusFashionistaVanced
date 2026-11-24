#!/usr/bin/env python3
"""
Build the Dofus Touch damage spells per class from the Touch backend.

Output: fashionistapulp/dofus_constants_touch_spells.py
"""

from __future__ import annotations

import argparse
import io
import json
import pprint
import re
import sys
import textwrap
from pathlib import Path

import requests

import touch_channels

LANGS = ['fr', 'en', 'es', 'pt', 'de']
CONFIG_URL = touch_channels.config_url('login')
FALLBACK_DATA_URL = touch_channels.fallback_data_url('login')
UA = "Dofus/2 CFNetwork"
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fashionistapulp'))

from fashionistapulp.reserved_filenames import safe_asset_stem  # noqa: E402

# Spell icons live on the assets CDN, prefixed "sort_".
SPELL_ICON_URL = "%s/gfx/spells/sort_%s.png"
SPELLS_ROOT = (Path(__file__).resolve().parent.parent / 'fashionsite' / 'chardata'
               / 'static' / 'chardata' / 'spells')
SPELLS_STATIC = SPELLS_ROOT / 'touch'
MODULE_DIR = Path(__file__).resolve().parent.parent / 'fashionistapulp' / 'fashionistapulp'

# 96-100 elemental damage, 91-95 elemental steals (same hit, heals the caster).
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral',
                  91: 'water', 92: 'earth', 93: 'air', 94: 'fire', 95: 'neutral'}
STEAL_EFFECTS = frozenset((91, 92, 93, 94, 95))
# The token of a steal row that lands beside a damage row of its element
STEAL_TOKEN = 'steal_%s'

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
ELEMENT_TOKEN_TO_CONST.update(
    {STEAL_TOKEN % token: ELEMENT_TOKEN_TO_CONST[token] for token in set(DAMAGE_EFFECTS.values())})

# Touch breed id -> Fashionista class name; a breed the channel's Breeds table lacks is skipped
CLASS_ID_TO_NAME = {
    1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor', 6: 'Ecaflip',
    7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida', 11: 'Sacrier', 12: 'Pandawa',
    13: 'Rogue', 14: 'Masqueraider', 15: 'Foggernaut', 21: 'Bellaphone',
}


def resolve_config(channel=touch_channels.DEFAULT_CHANNEL):
    """Return (dataUrl, assetsUrl) from the client config of the channel."""
    try:
        cfg = requests.get(touch_channels.config_url(channel) + '?lang=fr',
                           headers={'User-Agent': UA}, timeout=30).json()
        return ((cfg.get('dataUrl') or touch_channels.fallback_data_url(channel)).rstrip('/'),
                (cfg.get('assetsUrl') or '').rstrip('/'))
    except Exception:
        return touch_channels.fallback_data_url(channel), ''


def class_spells(breeds, spells):
    """{class: [spell rows]} for the whole book, damage spells or not."""
    out = {}
    for bid, app_name in CLASS_ID_TO_NAME.items():
        breed = breeds.get(str(bid))
        if breed is None:
            continue
        out[app_name] = [spells[str(sid)] for sid in breed.get('breedSpellsId') or []
                         if str(sid) in spells]
    return out


def icon_stem(name):
    """The file name, without its extension, of the icon of a spell of this name."""
    return safe_asset_stem(re.sub(r'[\\/*?:"<>|]', '', name).strip())


def unchanged_spell_names(by_class, spells, reference, icon_folder=None):
    """The names of class spells whose (name, iconId) are the same in the reference spell table and, given icon_folder, whose icon that folder really holds."""
    same = set()
    for class_spells in by_class.values():
        for s in class_spells:
            now = spells.get(str(s['id'])) or {}
            before = reference.get(str(s['id'])) or {}
            pair = (now.get('nameId'), now.get('iconId'))
            if now.get('iconId') is None or pair != (before.get('nameId'), before.get('iconId')):
                continue
            name = s.get('name') or s.get('nameId')
            if icon_folder is None or (Path(icon_folder) / ('%s.png' % icon_stem(name))).is_file():
                same.add(name)
    return same


def download_spell_images(by_class, spells, assets_url, dest_dir=None, skip_names=()):
    """Save each class spell's icon 96x96 as chardata/spells/touch/<French name>.png, leaving out skip_names."""
    dest_dir = Path(dest_dir) if dest_dir else SPELLS_STATIC
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow not installed; skipping spell images", file=sys.stderr)
        return
    if not assets_url:
        print("  no assetsUrl; skipping spell images", file=sys.stderr)
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    seen, written, missing = set(), 0, 0
    for class_spells in by_class.values():
        for s in class_spells:
            name = s.get('name') or s.get('nameId')
            if not name or name in seen or name in skip_names:
                continue
            seen.add(name)
            icon_id = (spells.get(str(s['id'])) or {}).get('iconId')
            if icon_id is None:
                continue
            dest = dest_dir / ('%s.png' % icon_stem(name))
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
    13569: 'occasionne des dommages dans le meilleur ',  # Bellaphone, Domoko
    13769: 'occasionne des d\u00e9g\u00e2ts dans le meilleur ',  # Bellaphone, Nogdra
    13771: 'occasionne des dommages dans le meilleur ',  # Bellaphone, Drosera
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


# Mask letters naming only summons (static or not, allied or enemy)
SUMMON_MASK_LETTERS = frozenset('iIsS')
# a and A are every ally and every enemy, summons included
EVERY_FIGHTER_MASK_LETTERS = frozenset('aA')
ENEMY_ONLY_MASK = frozenset('A')
ALLY_ONLY_MASKS = (frozenset('a'),)


def _mask_letters(effect):
    return {token for token in str(effect.get('targetMask') or '').split(',')
            if len(token) == 1}


def _same_hit(effect):
    """Row token, zone and mask gates (states, exclusions), shared by the faces of one hit."""
    gates = frozenset(token for token in str(effect.get('targetMask') or '').split(',')
                      if len(token) > 1)
    return DAMAGE_EFFECTS[effect.get('effectId')], effect.get('rawZone'), gates


def _summons_only(effect):
    letters = _mask_letters(effect)
    return bool(letters) and letters <= SUMMON_MASK_LETTERS


def _spares_summons(effect):
    letters = _mask_letters(effect)
    return bool(letters) and not letters & (SUMMON_MASK_LETTERS
                                            | EVERY_FIGHTER_MASK_LETTERS)


# "E580" in a mask: the target is in state 580; "e580": it is not; "*E891": the caster is
TARGET_STATE_TOKEN = re.compile(r'^E\d+$')

# What the line a target in a state takes, in place of the plain one, waits for; the site reads this
TARGET_STATE_COPY = 'target_in_a_state'


def _target_states(effect):
    """The states a row needs its target in."""
    return frozenset(token for token in str(effect.get('targetMask') or '').split(',')
                     if TARGET_STATE_TOKEN.match(token))


def _hit_key(effect):
    return (DAMAGE_EFFECTS[effect.get('effectId')], effect.get('targetMask'), effect.get('rawZone'),
            effect.get('triggers'), bool(effect.get('isPreview')))


def _steals_beside_their_hit(effect_list):
    """Ids of the steal rows that land beside a damage row of their element, mask, zone and trigger."""
    hits = {_hit_key(e) for e in effect_list
            if e.get('effectId') in DAMAGE_EFFECTS and e.get('effectId') not in STEAL_EFFECTS}
    return {id(e) for e in effect_list
            if e.get('effectId') in STEAL_EFFECTS and _hit_key(e) in hits}


def collect_damage(effect_list, best_element_rows=False, on_ally=None, on_state=None):
    """One effect list -> {row token: (min, max, when)}, strongest line per token."""
    out = {}
    effect_list = effect_list or []
    # A hit with its own line on summons keeps the line the other targets take
    spared = {_same_hit(e) for e in effect_list
              if e.get('effectId') in DAMAGE_EFFECTS and _spares_summons(e)}
    # An enemy takes its own line; one that only allies take goes to on_ally
    on_enemies = {DAMAGE_EFFECTS[e.get('effectId')] for e in effect_list
                  if e.get('effectId') in DAMAGE_EFFECTS
                  and _mask_letters(e) == ENEMY_ONLY_MASK}
    paired = _steals_beside_their_hit(effect_list)

    def route(e):
        """(tokens, True when only allies take it) of a row read, else None."""
        eid = e.get('effectId')
        if eid == BEST_ELEMENT_EFFECT and best_element_rows:
            # One row per element, emit_aggregates groups them as one hit
            return BEST_ELEMENT_TOKENS, False
        if eid not in ROW_EFFECTS:
            return None
        # A buff or steal only a target in a state gives is not the caster's on a plain target
        if eid in CHARACTERISTIC_EFFECTS and _target_states(e):
            return None
        token = STEAL_TOKEN % ROW_EFFECTS[eid] if id(e) in paired else ROW_EFFECTS[eid]
        if eid in DAMAGE_EFFECTS and _summons_only(e) and _same_hit(e) in spared:
            return None
        if (eid in DAMAGE_EFFECTS and _mask_letters(e) in ALLY_ONLY_MASKS
                and ROW_EFFECTS[eid] in on_enemies):
            return ((token,), True) if on_ally is not None else None
        return (token,), False

    routes = [(e, route(e)) for e in effect_list]
    plain = {found[0][0] for e, found in routes
             if found and not found[1] and e.get('effectId') in DAMAGE_EFFECTS
             and not _target_states(e)}
    held = {}
    for e, found in routes:
        if found is None:
            continue
        tokens, allies_only = found
        target = on_ally if allies_only else out
        if (not allies_only and e.get('effectId') in DAMAGE_EFFECTS and _target_states(e)
                and tokens[0] in plain):
            # The plain line is the hit; the one on a target in a state is held apart
            target = held
        lo = e.get('diceNum') or 0
        hi = e.get('diceSide') or 0
        if hi < lo:                          # diceSide==0 (or < min) => fixed hit
            hi = lo
        for elem in tokens:
            prev = target.get(elem)
            if prev is None or lo + hi > prev[0] + prev[1]:
                target[elem] = (lo, hi, when_it_lands(e.get('triggers')))
    for token, line in held.items():
        if on_state is not None and line[0] + line[1] > out[token][0] + out[token][1]:
            on_state[token] = line
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


# Rows acting on the spell's own later casts: 293 raises its base damage, 2985 its AP cost, by value
OWN_DAMAGE_BOOST = 293
OWN_AP_COST_BOOST = 2985

# Spells whose damage grows with each cast of the turn, with the fragment that says so
DAMAGE_GROWS_EACH_CAST = {
    12439: 'qui augmentent pour chaque lancer durant le m\u00eame tour',   # Cra, Fleche Harcelante
}

# Spells whose AP cost grows with each cast of the turn, with the fragment that says so
AP_COST_GROWS_EACH_CAST = {
    12439: 'le co\u00fbt en PA du sort augmente \u00e0 chaque lancer',   # Cra, Fleche Harcelante
}

# Spells whose cast boosts their casts of the next turns through a spell it casts, with the fragment
BOOSTS_ITS_NEXT_TURNS = {
    8119: 'augment\u00e9s apr\u00e8s chaque lancer (cumul maximum de 2)',   # Iop, Colere de Iop
}

# (delay, duration, max stack) of that boost: it waits a turn, lasts 3 and stacks twice
NEXT_TURNS_BOOST = (1, 3, 2)

# What the copy raised by one, then two, stacked boosts waits for; the site reads these
NEXT_TURNS_COPIES = ('later_cast_within_3_turns', 'cast_after_two_casts')


def _own_rows(rows, effect_id, spell_id):
    """Indices of the rows acting on the spell itself, the tooltip's own copies left out."""
    return [index for index, row in enumerate(rows or [])
            if row.get('effectId') == effect_id and row.get('diceNum') == spell_id
            and not row.get('isPreview')]


def _for_the_turn(row):
    """A row the cast puts on its caster until the turn ends."""
    value = row.get('value')
    return (row.get('targetMask') == 'C' and row.get('triggers') == 'I' and not row.get('delay')
            and row.get('duration') == 1 and not row.get('random')
            and isinstance(value, int) and value > 0)


def _recast_this_turn(ranks):
    return any(rank.get('maxCastPerTurn') != 1 and rank.get('maxCastPerTarget') != 1
               for rank in ranks)


def _step_per_cast(spell, ranks, effect_id, listed, after_the_hit=False):
    """Each rank's step a cast adds to the spell's next casts of the turn, None for an unlisted spell."""
    spell_id = spell.get('id')
    quote = listed.get(spell_id)
    if quote is None:
        for rank in ranks:
            for key in ('effects', 'criticalEffect'):
                rows = rank.get(key) or []
                for index in _own_rows(rows, effect_id, spell_id):
                    if (not rows[index].get('delay') and rows[index].get('duration')
                            and _recast_this_turn(ranks)):
                        raise SystemExit(
                            'touch spell %s: its effect %s rows raise its next casts of the '
                            'turn and no rule reads them yet' % (spell_id, effect_id))
        return None
    if quote.lower() not in _description_of(spell).lower():
        raise SystemExit('touch spell %s no longer says %r; its casts of the turn were made '
                         'to grow on that sentence' % (spell_id, quote))
    steps = []
    for rank in ranks:
        values = set()
        casts = int(rank.get('maxCastPerTurn') or 0)
        cap = int(rank.get('maxStack') or 0)
        for key in ('effects', 'criticalEffect'):
            rows = rank.get(key) or []
            own = _own_rows(rows, effect_id, spell_id)
            hits = [index for index, row in enumerate(rows)
                    if row.get('effectId') in DAMAGE_EFFECTS]
            if (len(own) != 1 or not _for_the_turn(rows[own[0]]) or casts < 2
                    or 0 < cap < casts - 1
                    or (after_the_hit and (not hits or own[0] < max(hits)))):
                values.add(None)
            else:
                values.add(rows[own[0]]['value'])
        steps.append(values.pop() if len(values) == 1 else None)
    if not steps or None in steps:
        raise SystemExit('touch spell %s: its rows no longer raise each of its next casts of '
                         'the turn by one step' % spell_id)
    return steps


def _raised_ranges(ranges, steps, times):
    """Each rank's 'min-max' raised by `times` of its step."""
    out = []
    for literal, step in zip(ranges, steps):
        low, high = (int(part) for part in literal.split('-'))
        out.append('%d-%d' % (low + times * step, high + times * step))
    return out


def _one_plain_row(entry):
    return (len(entry['elements']) == 1 and not entry['aggregates']
            and not entry['conditional'] and not entry['delayed']
            and entry['delayed_crit'] is None
            and '0-0' not in entry['non_crit_ranges'][0] + entry['crit_ranges'][0])


def _turn_ladder(entry, steps, ranks):
    """The entry with one Stack group per cast of the turn, each raised by one more step."""
    casts = {int(rank.get('maxCastPerTurn') or 0) for rank in ranks}
    if not _one_plain_row(entry) or len(casts) != 1:
        raise SystemExit('touch spell %s: its casts of the turn grow on a hit that is not '
                         'its one row' % entry['id'])
    count = casts.pop()
    return dict(entry,
                elements=[entry['elements'][0]] * count,
                non_crit_ranges=[_raised_ranges(entry['non_crit_ranges'][0], steps, stack)
                                 for stack in range(count)],
                crit_ranges=[_raised_ranges(entry['crit_ranges'][0], steps, stack)
                             for stack in range(count)],
                aggregates=[('Stack %d' % stack, [stack]) for stack in range(count)],
                stacks_on_recast=True)


def _next_turns_boost(spell, ranks, spells, spell_levels):
    """Each rank's boost a cast leaves on the spell's casts of its next turns, None for an unlisted spell."""
    spell_id = spell.get('id')
    quote = BOOSTS_ITS_NEXT_TURNS.get(spell_id)
    if quote is None:
        return None
    if quote.lower() not in _description_of(spell).lower():
        raise SystemExit('touch spell %s no longer says %r; its casts of the next turns were '
                         'boosted on that sentence' % (spell_id, quote))
    boosts = []
    for rank in ranks:
        values = set() if rank.get('maxCastPerTurn') == 1 else {None}
        for key in ('effects', 'criticalEffect'):
            rows = rank.get(key) or []
            cast = [row for row in rows if row.get('effectId') in CASTS_A_SPELL]
            child = ((spells or {}).get(str(cast[0].get('diceNum')))
                     if len(cast) == 1 and not cast[0].get('delay')
                     and cast[0].get('triggers') == 'I' else None)
            level = (child_rank(child, int(cast[0].get('diceSide') or 0), spell_levels)
                     if child else {})
            boost = level.get('effects') or []
            if (_own_rows(rows, OWN_DAMAGE_BOOST, spell_id) or level.get('criticalEffect')
                    or len(boost) != 1 or boost[0].get('effectId') != OWN_DAMAGE_BOOST
                    or boost[0].get('diceNum') != spell_id or boost[0].get('isPreview')
                    or boost[0].get('targetMask') != 'C' or boost[0].get('triggers') != 'I'
                    or boost[0].get('random') or not isinstance(boost[0].get('value'), int)
                    or boost[0]['value'] <= 0
                    or (boost[0].get('delay'), boost[0].get('duration'),
                        level.get('maxStack')) != NEXT_TURNS_BOOST):
                values.add(None)
            else:
                values.add(boost[0]['value'])
        boosts.append(values.pop() if len(values) == 1 else None)
    if not boosts or None in boosts:
        raise SystemExit('touch spell %s: its rows no longer leave one boost of its casts on '
                         'its next turns' % spell_id)
    return boosts


def _next_turns_copies(entry, boosts):
    """The entry with one held copy of its hit per stacked boost, each waiting for its later cast."""
    if not _one_plain_row(entry):
        raise SystemExit('touch spell %s: its boosted later casts raise a hit that is not '
                         'its one row' % entry['id'])
    elements = list(entry['elements'])
    non_crit, crit = list(entry['non_crit_ranges']), list(entry['crit_ranges'])
    conditional = {}
    for times, trigger in enumerate(NEXT_TURNS_COPIES, 1):
        elements.append(entry['elements'][0])
        non_crit.append(_raised_ranges(entry['non_crit_ranges'][0], boosts, times))
        crit.append(_raised_ranges(entry['crit_ranges'][0], boosts, times))
        conditional[len(elements) - 1] = trigger
    return dict(entry, elements=elements, non_crit_ranges=non_crit, crit_ranges=crit,
                conditional=conditional)


def grown_by_its_casts(spell, ranks, entry, spells=None, spell_levels=None):
    """The entry once the boosts its casts leave on its next casts are read."""
    damage_steps = _step_per_cast(spell, ranks, OWN_DAMAGE_BOOST, DAMAGE_GROWS_EACH_CAST,
                                  after_the_hit=True)
    ap_steps = _step_per_cast(spell, ranks, OWN_AP_COST_BOOST, AP_COST_GROWS_EACH_CAST)
    boosts = _next_turns_boost(spell, ranks, spells, spell_levels or {})
    if damage_steps:
        entry = _turn_ladder(entry, damage_steps, ranks)
    if ap_steps:
        entry = dict(entry, casting=dict(entry['casting'] or {}, ap_growth=ap_steps))
    if boosts:
        entry = _next_turns_copies(entry, boosts)
    return entry


def decode_spell(spell, spell_levels, spells=None, bombs=None):
    """Touch spell -> damage-spell dict (buff-only spells kept), or None if no row."""
    per_nc, per_cr, levels_req, elements, stacks = [], [], [], [], []
    ally_nc, ally_cr = [], []
    state_nc, state_cr = [], []
    casting_levels = []
    ranks = []
    best_element = False
    # {(effect id, child id): {rank index: grade}} of the things the spell places
    placements, gated = {}, set()
    # True when the only damage is the best-element row
    lire_le_meilleur = _best_element_is_the_whole_hit(spell)
    for lid in (spell.get('spellLevels') or []):
        lv = spell_levels.get(str(lid))
        if not lv:
            continue
        ranks.append(lv)
        best_element = best_element or _says_best_element(lv)
        for effect in lv.get('effects') or []:
            child = placed_child(effect, spells, bombs)
            if child is None:
                continue
            key = (effect.get('effectId'), child[0])
            placements.setdefault(key, {}).setdefault(len(per_nc), child[1])
            if STATE_IN_TARGET_MASK.findall(str(effect.get('targetMask') or '')):
                gated.add(key)
        ally_nc.append({})
        ally_cr.append({})
        state_nc.append({})
        state_cr.append({})
        nc = collect_damage(lv.get('effects'), lire_le_meilleur, ally_nc[-1], state_nc[-1])
        cr = collect_damage(lv.get('criticalEffect'), lire_le_meilleur,
                            ally_cr[-1], state_cr[-1])
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
    ally_tokens = []
    for level in ally_nc + ally_cr:
        for token in level:
            if token not in ally_tokens:
                ally_tokens.append(token)
    if ally_tokens and (aggregates or blocks):
        raise SystemExit(
            'touch spell %s has a line only allies take beside a grouped or '
            'placed hit; that shape has no rule yet' % spell.get('id'))
    for token in ally_tokens:
        nc_row, cr_row = rows_of(ally_nc, ally_cr, token)
        non_crit.append(nc_row)
        crit.append(cr_row)
        elements.append(token)
        conditional[len(elements) - 1] = 'on_ally'
    state_tokens = []
    for level in state_nc + state_cr:
        for token in level:
            if token not in state_tokens:
                state_tokens.append(token)
    if state_tokens and (aggregates or blocks or ally_tokens):
        raise SystemExit(
            'touch spell %s has a line only a target in a state takes beside a grouped, '
            'placed or ally-only hit; that shape has no rule yet' % spell.get('id'))
    for token in state_tokens:
        if any((token in nc_level) != (token in cr_level)
               or (nc_level.get(token) or (0, 0, None))[2]
               or (cr_level.get(token) or (0, 0, None))[2]
               for nc_level, cr_level in zip(state_nc, state_cr)):
            raise SystemExit(
                'touch spell %s: its line on a target in a state is stronger on one kind of hit '
                'only, or lands later; that shape has no rule yet' % spell.get('id'))
        nc_row, cr_row = rows_of(state_nc, state_cr, token)
        non_crit.append(nc_row)
        crit.append(cr_row)
        elements.append(token)
        conditional[len(elements) - 1] = TARGET_STATE_COPY
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
    entry = {
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
    return grown_by_its_casts(spell, ranks, entry, spells, spell_levels)


# "x#1% damage sustained" on the fighters the row targets
DAMAGE_TAKEN_EFFECT = 1163
# Removes the effects of a spell, the spell id in value
REMOVES_SPELL_EFFECTS = 406
# Direct damage, and damage from an enemy of the bearer
DIRECT_DAMAGE_TRIGGERS = frozenset(('D', 'DBE'))
# Rows casting the spell in diceNum at the rank in diceSide
CASTS_A_SPELL = frozenset((792, 1160, 2960))


def _ungated(effect):
    """True for a target mask of plain letters, no state, life or id test."""
    tokens = [token for token in str(effect.get('targetMask') or '').split(',') if token]
    return bool(tokens) and all(len(token) == 1 and token.isalpha() for token in tokens)


def _on_direct_damage(triggers):
    codes = {code for code in str(triggers or '').split('|') if code}
    return bool(codes) and codes <= DIRECT_DAMAGE_TRIGGERS


def _damage_taken_on_enemy(effect):
    """A row multiplying what any enemy it lands on takes, the tooltip's own copy left out."""
    return (effect.get('effectId') == DAMAGE_TAKEN_EFFECT and not effect.get('isPreview')
            and _ungated(effect) and 'A' in _mask_letters(effect)
            and _on_direct_damage(effect.get('triggers'))
            and not effect.get('delay') and not effect.get('random')
            and bool(effect.get('duration')))


def raises_damage_taken(effect):
    """A row raising what any enemy it lands on takes from the caster's hits."""
    return _damage_taken_on_enemy(effect) and int(effect.get('diceNum') or 0) > 100


def _lands_a_hit_now(effect):
    return ((effect.get('effectId') in DAMAGE_EFFECTS
             or effect.get('effectId') == BEST_ELEMENT_EFFECT)
            and effect.get('triggers') == 'I' and not effect.get('delay')
            and bool(effect.get('diceNum') or effect.get('diceSide')))


def damage_taken_at(effects, spell_id):
    """(percent, ends on the next hit) one effect list puts on an enemy, or None."""
    effects = effects or []
    if (any(_damage_taken_on_enemy(effect) and not raises_damage_taken(effect)
            for effect in effects) and any(_lands_a_hit_now(effect) for effect in effects)):
        raise SystemExit('touch spell %s lowers the damage taken of an enemy it hits' % spell_id)
    rows = [effect for effect in effects if raises_damage_taken(effect)]
    if not rows:
        return None
    if len(rows) > 1:
        raise SystemExit('touch spell %s puts %d damage taken rows on one enemy'
                         % (spell_id, len(rows)))
    if any(_lands_a_hit_now(effect) for effect in effects[effects.index(rows[0]) + 1:]):
        raise SystemExit('touch spell %s raises the damage taken before its own hit' % spell_id)
    ends = any(effect.get('effectId') == REMOVES_SPELL_EFFECTS
               and effect.get('value') == spell_id
               and _on_direct_damage(effect.get('triggers'))
               for effect in effects)
    return int(rows[0].get('diceNum') or 0), ends


def _check_cast_spells(rank, spell_id, spells, spell_levels, seen=frozenset()):
    """Stop if a spell the rank casts puts a damage taken on an enemy, which no rule reads."""
    for key in ('effects', 'criticalEffect'):
        for effect in rank.get(key) or []:
            child = (spells or {}).get(str(effect.get('diceNum')))
            cast = (effect.get('diceNum'), effect.get('diceSide'))
            if effect.get('effectId') not in CASTS_A_SPELL or child is None or cast in seen:
                continue
            child_level = child_rank(child, int(effect.get('diceSide') or 0), spell_levels)
            if any(raises_damage_taken(row) for row_key in ('effects', 'criticalEffect')
                   for row in child_level.get(row_key) or []):
                raise SystemExit('touch spell %s casts %s, whose damage taken on an enemy '
                                 'has no rule yet' % (spell_id, child.get('id')))
            _check_cast_spells(child_level, spell_id, spells, spell_levels, seen | {cast})


def damage_taken_entry(spell, spell_levels, spells=None, bombs=None, text=None):
    """What a cast multiplies one enemy's damage taken by, per rank, or None."""
    levels_req, casting = [], []
    percents, criticals, stacks, ends, placed = [], [], [], [], []
    for lid in spell.get('spellLevels') or []:
        rank = spell_levels.get(str(lid))
        if not rank:
            continue
        levels_req.append(max(1, int(rank.get('minPlayerLevel') or 1)))
        casting.append({key: int(rank.get(field) or 0)
                        for key, field in CASTING_FIELDS.items()})
        _check_cast_spells(rank, spell.get('id'), spells, spell_levels)
        carriers = [(spell.get('id'), rank, None)]
        for effect in rank.get('effects') or []:
            child = placed_child(effect, spells, bombs)
            if child is None:
                continue
            when = ('state' if STATE_IN_TARGET_MASK.findall(str(effect.get('targetMask') or ''))
                    else PLACED_BY_EFFECT[effect.get('effectId')][1])
            carriers.append((child[0], child_rank(spells[str(child[0])], child[1], spell_levels),
                             when))
        found = None
        for carrier_id, carrier_rank, when in carriers:
            normal = damage_taken_at(carrier_rank.get('effects'), carrier_id)
            critical = (damage_taken_at(carrier_rank.get('criticalEffect'), carrier_id)
                        if carrier_rank.get('criticalHitProbability') else normal)
            if normal is None and critical is None:
                continue
            if found is not None:
                raise SystemExit('touch spell %s puts damage taken rows from two spells'
                                 % spell.get('id'))
            if normal is None or critical is None or critical[1] != normal[1]:
                raise SystemExit('touch spell %s puts damage taken on one kind of hit only, '
                                 'or one that ends otherwise on a critical hit' % carrier_id)
            cap = int(carrier_rank.get('maxStack') or 0)
            found = (normal[0], critical[0], cap if cap > 0 else None, normal[1], when)
        percents.append(found[0] if found else 0)
        criticals.append(found[1] if found else 0)
        stacks.append(found[2] if found else None)
        ends.append(found[3] if found else False)
        placed.append(found[4] if found else None)
    if not any(percents):
        return None
    entry = {
        'spell_id': spell['id'],
        'name': spell.get('nameId') or '',
        'levels': levels_req,
        'casting': {key: [level[key] for level in casting] for key in CASTING_FIELDS
                    if any(level[key] for level in casting)} or None,
        'percent': percents,
    }
    if criticals != percents:
        entry['percent_critical'] = criticals
    entry['stacks'] = stacks
    if any(ends):
        entry['ends_on_hit'] = ends
    if any(placed):
        entry['placed'] = placed
    if text:
        entry['text'] = dict(text)
    return entry


def build_damage_taken(breeds, spells, spell_levels, bombs=None, text=None):
    """{class: [damage_taken_entry]} over each class's spell book."""
    out = {}
    for bid, app_name in CLASS_ID_TO_NAME.items():
        seen = set()
        for sid in (breeds.get(str(bid)) or {}).get('breedSpellsId') or []:
            spell = spells.get(str(sid))
            if not spell or sid in seen:
                continue
            seen.add(sid)
            entry = damage_taken_entry(spell, spell_levels, spells, bombs, text)
            if entry:
                out.setdefault(app_name, []).append(entry)
    return out


def build(breeds, spells, spell_levels, bombs=None):
    by_class = {}
    for bid, app_name in CLASS_ID_TO_NAME.items():
        breed = breeds.get(str(bid))
        if breed is None:
            continue
        spell_ids = breed.get('breedSpellsId') or []
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


def render_damage_taken(taken_by_class):
    lines = ["TOUCH_DAMAGE_TAKEN = {"]
    for cls, entries in sorted((taken_by_class or {}).items()):
        lines.append("    %s: [" % json.dumps(cls))
        for entry in sorted(entries, key=lambda e: (e['name'], e['spell_id'])):
            text = pprint.pformat(entry, width=88, sort_dicts=False)
            lines.append(textwrap.indent(text, " " * 8) + ",")
        lines.append("    ],")
    lines.append("}")
    return lines


def emit_module(by_class, spell_names, path, taken_by_class=None):
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
            steals = [str(token).startswith(STEAL_TOKEN % '') for token in s['elements']]
            if any(steals):
                lines.append("            steals=%r," % (steals,))
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
            if s.get('stacks_on_recast'):
                tail.append("stacks_on_recast=True")
            lines.append("        )%s)," % (", " + ", ".join(tail) if tail else ""))
        lines.append("    ],")
    lines.append("    'default': [],")
    lines.append("}")
    lines.append("")
    lines.extend(render_damage_taken(taken_by_class))
    lines.append("")
    lines.append("TOUCH_SPELL_NAMES = " + json.dumps(spell_names, ensure_ascii=False, indent=1, sort_keys=True))
    Path(path).write_text("\n".join(lines) + "\n", encoding='utf-8')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--module-out', default=None,
                   help='Where the module is written (default: the module of the channel)')
    p.add_argument('--skip-images', action='store_true', help='Skip the spell-icon download')
    touch_channels.add_channel_argument(p)
    args = p.parse_args(argv)
    key = touch_channels.game_version(args.channel)
    module_out = args.module_out or str(MODULE_DIR / ('dofus_constants_%s_spells.py' % key))

    data_url, assets_url = resolve_config(args.channel)
    print(f"Dofus Touch data proxy ({args.channel}): {data_url}")
    breeds = fetch_table(data_url, 'Breeds')
    spell_levels = fetch_table(data_url, 'SpellLevels')
    spells_by_lang = {lang: fetch_table(data_url, 'Spells', lang) for lang in LANGS}
    spells = spells_by_lang['fr']
    bombs = fetch_table(data_url, BOMB_TABLE)
    taken_text = {lang: (fetch_table(data_url, 'Effects', lang).get(str(DAMAGE_TAKEN_EFFECT))
                         or {}).get('descriptionId') for lang in LANGS}
    print(f"  Breeds={len(breeds)} Spells={len(spells)} SpellLevels={len(spell_levels)} "
          f"{BOMB_TABLE}={len(bombs)}")

    by_class = build(breeds, spells, spell_levels, bombs)
    taken_by_class = build_damage_taken(
        breeds, spells, spell_levels, bombs,
        {lang: text for lang, text in taken_text.items() if text})
    spell_names = build_spell_names(by_class, spells_by_lang)
    emit_module(by_class, spell_names, module_out, taken_by_class)

    total = sum(len(v) for v in by_class.values())
    print(f"Wrote {total} damage spells across {len(by_class)} classes to {module_out}")
    print("  damage taken: " + ", ".join(
        "%s %s" % (cls, entry['name']) for cls, entries in sorted(taken_by_class.items())
        for entry in entries))
    empty = [c for c, v in by_class.items() if not v]
    if empty:
        print("  classes with no damage spells: " + ", ".join(empty))

    if not args.skip_images:
        by_class_spells = class_spells(breeds, spells)
        skip, dest_dir = (), SPELLS_STATIC
        if args.channel != touch_channels.DEFAULT_CHANNEL:
            reference = fetch_table(resolve_config()[0], 'Spells')
            skip = unchanged_spell_names(by_class_spells, spells, reference, SPELLS_STATIC)
            dest_dir = SPELLS_ROOT / touch_channels.static_subdir(args.channel)
            print(f"  {len(skip)} spell icons identical to login and on disk there, not fetched")
        download_spell_images(by_class_spells, spells, assets_url, dest_dir, skip)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
