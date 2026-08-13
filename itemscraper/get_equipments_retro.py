#!/usr/bin/env python3
"""
Turn the parsed Retro lang JSON (from download_retro_langs.py) into
transformed_equipment.json and transformed_sets.json, in the shape
get_equipments2.py produces for Dofus 3.

Effects come as ISTA entries "<effectId_hex>#<jetMin_hex>#<jetMax_hex>#<dice>";
the value taken is jetMax, falling back to jetMin.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
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
    '82': ('Shield', None),  # Retro 1.48 added shields
    # Backpacks share the cape slot on Retro.
    '81': ('Cloak', None),
    # Dragodinde mounts (Dragoturkey in English) share the Pet slot, gated by
    # the "Dragoturkeys" mount toggle.
    '97': ('Pet', None),
    # Two weapon categories Retro has and Dofus 3 dropped, named as the game
    # names them in I['t']. 102 is a single GM crossbow, 114 the Tormentators.
    '102': ('Weapon', 'Crossbow'),
    '114': ('Weapon', 'Magic Weapon'),
}

# Retro effect id -> (English stat name as used by get_equipments3, sign).
EFFECT_MAP = {
    118: ('Strength', 1), 119: ('Agility', 1), 123: ('Chance', 1),
    124: ('Wisdom', 1), 125: ('Vitality', 1), 126: ('Intelligence', 1),
    112: ('Damage', 1), 115: ('Critical Hits', 1), 117: ('Range', 1),
    # 138 = "Augmente les dommages de X%", Retro's percent-damage stat; the
    # model calls that Power.
    138: ('Power', 1),
    110: ('HP', 1), 174: ('Initiative', 1), 176: ('Prospecting', 1),
    # 220 = 'Renvoie X dommages', carried only by the Prespic ring and belt
    # and by Sulik.
    220: ('Reflects', 1),
    178: ('Heals', 1), 182: ('Summon', 1), 111: ('AP', 1), 128: ('MP', 1),
    96: ('Water Damage', 1), 97: ('Earth Damage', 1), 98: ('Air Damage', 1),
    99: ('Fire Damage', 1), 100: ('Neutral Damage', 1),
    210: ('% Earth Resist', 1), 211: ('% Water Resist', 1), 212: ('% Air Resist', 1),
    213: ('% Fire Resist', 1), 214: ('% Neutral Resist', 1),
    # 215-219 are the same five as a malus, "X% de faiblesse face a ...".
    215: ('% Earth Resist', -1), 216: ('% Water Resist', -1),
    217: ('% Air Resist', -1), 218: ('% Fire Resist', -1),
    219: ('% Neutral Resist', -1),
    240: ('Earth Resist', 1), 241: ('Water Resist', 1), 242: ('Air Resist', 1),
    243: ('Fire Resist', 1), 244: ('Neutral Resist', 1),
    # malus (negative)
    153: ('Vitality', -1), 154: ('Agility', -1), 155: ('Intelligence', -1),
    156: ('Wisdom', -1), 157: ('Strength', -1), 152: ('Chance', -1),
    175: ('Prospecting', -1), 168: ('AP', -1), 169: ('MP', -1),
    166: ('AP', 1), 177: ('Dodge', 1), 173: ('Lock', 1),
    194: ('Pods', 1),
    158: ('Pods', 1), 225: ('Trap Damage', 1), 226: ('% Trap Damage', 1),
    # PVP resists ("face aux combattants"), on Retro items (e.g. shields) but
    # removed from Dofus 3. % variants 250-254, flat variants 260-264.
    250: ('% Earth Resist in PVP', 1), 251: ('% Water Resist in PVP', 1),
    252: ('% Air Resist in PVP', 1), 253: ('% Fire Resist in PVP', 1),
    254: ('% Neutral Resist in PVP', 1),
    260: ('Earth Resist in PVP', 1), 261: ('Water Resist in PVP', 1),
    262: ('Air Resist in PVP', 1), 263: ('Fire Resist in PVP', 1),
    264: ('Neutral Resist in PVP', 1),
}

# Condition code -> English stat name (only stat-gating codes; class/sub/align skipped).
CONDITION_MAP = {
    'CS': 'Strength', 'CI': 'Intelligence', 'CA': 'Agility',
    'CV': 'Vitality', 'CC': 'Chance', 'CW': 'Wisdom',
}

# Elemental damage effect id -> element label. On a weapon these are hit lines
# (the weapon's damage roll), not flat characteristic bonuses.
ELEMENT_BY_EFFECT = {
    96: 'Water', 97: 'Earth', 98: 'Air', 99: 'Fire', 100: 'Neutral',
}

# Life-steal (vol de vie) damage effect ids -> element label. Same element order
# as ELEMENT_BY_EFFECT but 5 lower. On a weapon these are hit lines that deal
# damage and heal the caster.
STEAL_BY_EFFECT = {
    91: 'Water', 92: 'Earth', 93: 'Air', 94: 'Fire', 95: 'Neutral',
}

# Weapon heal, "PDV rendus". The game's effects file lists the heal ids as
# EHEL = {0: 108, 1: 81}; neither carries the 'e' element field every damage and
# steal effect has, so in 1.29 a heal has no element. Intelligence still scales
# it: base * (100 + Intelligence) / 100 + Soins.
HEAL_BY_EFFECT = {108, 81}

# What the lang says about an item beyond its stats, under the names Dofus 3
# already uses so the site's own translations apply.
#   795 "Arme de chasse": 0 on the Hunter's own tools, 1 on the weapons Dofus 3
#       lists as hunting weapons.
#   2151 "Lie au personnage", no parameter.
FLAG_BY_EFFECT = {795: 'Hunting Weapon', 2151: 'Linked to the character'}
FLAG_NEEDS_VALUE = {795: 1}

# 1.29 spell hats and capes carry no characteristic at all, only a modifier on
# one named spell. The optimizer has no notion of a per-spell modifier, so these
# are read lines, not stats. The French wording is the game's own, from
# effects_fr.json; the lang ships no translated effect table, so the other four
# are ours. Values are hex, like the rest of an ISTA field.
SPELL_EFFECT_TEMPLATES = {
    281: {'fr': 'Augmente la portée du sort %(spell)s de %(value)d',
          'en': 'Increases the range of %(spell)s by %(value)d',
          'es': 'Aumenta el alcance de %(spell)s en %(value)d',
          'pt': 'Aumenta o alcance de %(spell)s em %(value)d',
          'de': 'Erhöht die Reichweite von %(spell)s um %(value)d'},
    282: {'fr': 'Rend la portée du sort %(spell)s modifiable',
          'en': 'Makes the range of %(spell)s modifiable',
          'es': 'Hace modificable el alcance de %(spell)s',
          'pt': 'Torna o alcance de %(spell)s modificável',
          'de': 'Macht die Reichweite von %(spell)s veränderbar'},
    283: {'fr': '+%(value)d de dommages sur le sort %(spell)s',
          'en': '+%(value)d damage on %(spell)s',
          'es': '+%(value)d de daños en %(spell)s',
          'pt': '+%(value)d de danos em %(spell)s',
          'de': '+%(value)d Schaden bei %(spell)s'},
    284: {'fr': '+%(value)d de soins sur le sort %(spell)s',
          'en': '+%(value)d healing on %(spell)s',
          'es': '+%(value)d de curaciones en %(spell)s',
          'pt': '+%(value)d de curas em %(spell)s',
          'de': '+%(value)d Heilung bei %(spell)s'},
    285: {'fr': 'Réduit de %(value)d le coût en PA du sort %(spell)s',
          'en': 'Reduces the AP cost of %(spell)s by %(value)d',
          'es': 'Reduce en %(value)d el coste en PA de %(spell)s',
          'pt': 'Reduz em %(value)d o custo em PA de %(spell)s',
          'de': 'Senkt die AP-Kosten von %(spell)s um %(value)d'},
    286: {'fr': 'Réduit de %(value)d le délai de relance du sort %(spell)s',
          'en': 'Reduces the cooldown of %(spell)s by %(value)d',
          'es': 'Reduce en %(value)d el tiempo de reutilización de %(spell)s',
          'pt': 'Reduz em %(value)d o tempo de recarga de %(spell)s',
          'de': 'Senkt die Abklingzeit von %(spell)s um %(value)d'},
    287: {'fr': '+%(value)d aux CC sur le sort %(spell)s',
          'en': '+%(value)d critical hits on %(spell)s',
          'es': '+%(value)d a los golpes críticos de %(spell)s',
          'pt': '+%(value)d aos golpes críticos de %(spell)s',
          'de': '+%(value)d kritische Treffer bei %(spell)s'},
    288: {'fr': 'Désactive le lancer en ligne du sort %(spell)s',
          'en': 'Removes the line-only casting of %(spell)s',
          'es': 'Desactiva el lanzamiento en línea de %(spell)s',
          'pt': 'Desativa o lançamento em linha de %(spell)s',
          'de': 'Deaktiviert das Wirken in einer Linie von %(spell)s'},
    289: {'fr': 'Désactive la ligne de vue du sort %(spell)s',
          'en': 'Removes the line of sight requirement of %(spell)s',
          'es': 'Desactiva la línea de visión de %(spell)s',
          'pt': 'Desativa a linha de visão de %(spell)s',
          'de': 'Deaktiviert die Sichtlinie von %(spell)s'},
    290: {'fr': 'Augmente de %(value)d le nombre de lancer maximal par tour du sort %(spell)s',
          'en': 'Increases the maximum casts per turn of %(spell)s by %(value)d',
          'es': 'Aumenta en %(value)d el número máximo de lanzamientos por turno de %(spell)s',
          'pt': 'Aumenta em %(value)d o número máximo de lançamentos por turno de %(spell)s',
          'de': 'Erhöht die maximale Anzahl an Zaubern pro Runde von %(spell)s um %(value)d'},
    291: {'fr': 'Augmente de %(value)d le nombre de lancer maximal par cible du sort %(spell)s',
          'en': 'Increases the maximum casts per target of %(spell)s by %(value)d',
          'es': 'Aumenta en %(value)d el número máximo de lanzamientos por objetivo de %(spell)s',
          'pt': 'Aumenta em %(value)d o número máximo de lançamentos por alvo de %(spell)s',
          'de': 'Erhöht die maximale Anzahl an Zaubern pro Ziel von %(spell)s um %(value)d'},
}

# Set bonuses are NOT in the Ankama lang CDN (1.29 set bonuses are server-side),
# so they're sourced from a vendored community snapshot (retro-craft/scrapstuff,
# scraped from barbok.eratz.fr). Those use French stat labels; map them here.
_SET_STAT_FR_TO_EN = {
    'force': 'Strength', 'intelligence': 'Intelligence', 'agilite': 'Agility',
    'chance': 'Chance', 'sagesse': 'Wisdom', 'vitalite': 'Vitality', 'vie': 'HP',
    'dommages': 'Damage', 'dommage': 'Damage', 'soins': 'Heals', 'soin': 'Heals',
    'prospection': 'Prospecting', 'pa': 'AP', 'pm': 'MP', 'portee': 'Range',
    'po': 'Range', 'cc': 'Critical Hits', 'initiative': 'Initiative',
    'pods': 'Pods', 'invocation': 'Summon', 'creature invocable': 'Summon',
    'crea invocable': 'Summon', 'creatures invocables': 'Summon',
    'renvoie': 'Reflects',
}
_SET_ELEMENTS_FR = {'terre': 'Earth', 'feu': 'Fire', 'eau': 'Water',
                    'air': 'Air', 'neutre': 'Neutral'}


def _ascii(s):
    return unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode('ascii').lower().strip()


_SET_STAT_EN_PASSTHROUGH = (set(_SET_STAT_FR_TO_EN.values())
                            | {'%s Resist' % e for e in _SET_ELEMENTS_FR.values()}
                            | {'%% %s Resist' % e for e in _SET_ELEMENTS_FR.values()}
                            | {'Power', 'Trap Damage', '% Trap Damage', 'Vitality'})


def _map_set_stat(fr_type):
    """French set-bonus label -> English stat name (or None to skip).
    English stat names (from the committed-db fallback entries) pass through."""
    if fr_type in _SET_STAT_EN_PASSTHROUGH:
        return fr_type
    pct = '%' in fr_type
    n = ' '.join(_ascii(fr_type).replace('%', '').replace('.', '').split())
    if 'res' in n and 'faiblesse' not in n:
        for fr, en in _SET_ELEMENTS_FR.items():
            if fr in n:
                return ('%% %s Resist' % en) if pct else ('%s Resist' % en)
    if 'pieg' in n:
        return '% Trap Damage' if pct else 'Trap Damage'
    if pct and 'dommage' in n:
        return 'Power'  # "% Dommages" set bonus -> the model's percent-damage stat
    if pct:
        return None  # no other percent set stats on Retro
    return _SET_STAT_FR_TO_EN.get(n)


def load_set_bonuses(path):
    """Vendored scrapstuff sets.json -> [(ankama_id, frozenset(item_names), stats_list), ...].

    stats_list matches get_equipments3:
      [{'effect_key': num_pieces, 'effects': [[value, value, EnglishStat], ...]}, ...]

    The snapshot is Dofus Retro 1.29 while live Retro is 1.48: item stats come from
    the live CDN, only these set bonuses are 1.29, so the sets added since are missing.
    """
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding='utf-8'))
    out = []
    for s in data:
        ankama_id = s.get('ankama_id')
        stats_list = []
        # bonus[i] is the cumulative bonus for wearing (i+1) pieces: bonus[0] is the
        # 1-piece tier (always empty -- no 1-item set bonus in Dofus).
        for idx, tier in enumerate(s.get('bonus', [])):
            num_pieces = idx + 1
            effects = []
            for b in (tier or []):
                stat = _map_set_stat(b.get('type', ''))
                if not stat:
                    continue
                try:
                    val = int(b.get('value'))
                except (TypeError, ValueError):
                    continue
                effects.append([val, val, stat])
            if effects:
                stats_list.append({'effect_key': num_pieces, 'effects': effects})
        if stats_list:
            item_names = frozenset(_ascii(n) for n in s.get('items', []) if n)
            out.append((ankama_id, item_names, stats_list))
    return out


def _match_set_bonuses(lang_item_names, set_bonuses, set_ankama_id=None):
    """Pick the bonus entry for this lang set: by ankama id when the entry carries
    one, else by best item-name overlap (the legacy snapshot format has no ids)."""
    if set_ankama_id is not None:
        for ankama_id, _item_names, stats_list in set_bonuses:
            if ankama_id == set_ankama_id:
                return stats_list
    if not lang_item_names:
        return []
    best_stats, best_overlap, best_size = [], 0, 0
    for ankama_id, item_names, stats_list in set_bonuses:
        if ankama_id is not None:
            continue  # id-carrying entries only ever match by id
        overlap = len(lang_item_names & item_names)
        if overlap > best_overlap:
            best_overlap, best_stats, best_size = overlap, stats_list, len(item_names)
    if best_overlap >= max(2, best_size // 2):
        return best_stats
    return []


def _hex(x):
    try:
        return int(x, 16)
    except (ValueError, TypeError):
        return None


def _is_die_roll(dice):
    """ISTA dice field 'XdY+Z' is a real roll when Y>0 (weapon hit); a flat bonus
    is encoded as '0d0+Z'."""
    m = re.match(r'\s*(\d+)d(\d+)', dice or '')
    return bool(m) and int(m.group(2)) > 0


def decode_spell_lines(ista_string, spell_names_by_lang):
    """ISTA string -> {language: [read lines]} for the spell modifiers."""
    lines = {}
    for part in (ista_string or '').split(','):
        if not part:
            continue
        fields = part.split('#')
        eid = _hex(fields[0])
        templates = SPELL_EFFECT_TEMPLATES.get(eid)
        if templates is None:
            continue
        spell_id = _hex(fields[1]) if len(fields) > 1 and fields[1] != '' else None
        value = _hex(fields[3]) if len(fields) > 3 and fields[3] != '' else None
        if spell_id is None:
            continue
        for lang, template in templates.items():
            spell = (spell_names_by_lang.get(lang) or {}).get(spell_id)
            if not spell:
                spell = (spell_names_by_lang.get('fr') or {}).get(spell_id)
            if not spell:
                continue
            lines.setdefault(lang, []).append(
                template % {'spell': spell, 'value': value or 0})
    return lines


def load_spell_names(raw_dir):
    """language -> {spell id: name}, from the game's own per-language lang."""
    by_lang = {}
    for lang in ('fr', 'en', 'es', 'pt', 'de'):
        path = raw_dir / f'spells_{lang}.json'
        if not path.exists():
            continue
        spells = json.loads(path.read_text(encoding='utf-8')).get('S') or {}
        names = {}
        for sid, spell in spells.items():
            if isinstance(spell, dict) and spell.get('n'):
                try:
                    names[int(sid)] = spell['n']
                except (TypeError, ValueError):
                    continue
        by_lang[lang] = names
    return by_lang


def decode_stats(ista_string, is_weapon=False):
    """ISTA string -> (stats, hits).

    stats = list of [min, max, english_stat_name] (characteristic bonuses).
    hits  = list of [min, max, '(<Element> damage)' / '(<Element> steal)'] weapon
            hit lines (weapons only). On a weapon the elemental damage and steal
            effects are the weapon's roll, not a flat characteristic.
    """
    stats = []
    hits = []
    for part in (ista_string or '').split(','):
        if not part:
            continue
        fields = part.split('#')
        eid = _hex(fields[0])
        if eid is None:
            continue
        jmin = _hex(fields[1]) if len(fields) > 1 and fields[1] != '' else None
        jmax = _hex(fields[2]) if len(fields) > 2 and fields[2] != '' else None
        dice = fields[3] if len(fields) > 3 else ''
        hit_element = ELEMENT_BY_EFFECT.get(eid)
        hit_kind = 'damage'
        if hit_element is None and eid in STEAL_BY_EFFECT:
            hit_element = STEAL_BY_EFFECT[eid]
            hit_kind = 'steal'
        if hit_element is not None:
            hit_label = '(%s %s)' % (hit_element, hit_kind)
        elif eid in HEAL_BY_EFFECT:
            hit_label = '(heals)'
        else:
            hit_label = None
        if is_weapon and hit_label is not None and _is_die_roll(dice):
            lo = jmin if jmin is not None else jmax
            hi = jmax if jmax is not None else jmin
            if hi is not None:
                hits.append([lo if lo is not None else 0, hi, hit_label])
            continue
        if eid in FLAG_BY_EFFECT:
            wanted = FLAG_NEEDS_VALUE.get(eid)
            if wanted is None or _hex(dice) == wanted:
                stats.append([None, None, FLAG_BY_EFFECT[eid]])
            continue
        if eid not in EFFECT_MAP:
            continue
        name, sign = EFFECT_MAP[eid]
        value = jmax if jmax not in (None, 0) else jmin
        if value is None:
            continue
        v = sign * value
        stats.append([v, v, name])
    return stats, hits


def decode_weapon_e(e):
    """Retro weapon 'e' array -> {ap, crit_chance, crit_bonus}.

    Layout:
      [twoHanded, _, crit_chance, crit_failure, maxRange, minRange, ap, crit_bonus]
    """
    out = {}
    if isinstance(e, list) and len(e) >= 8:
        ap, crit, cbonus = e[6], e[2], e[7]
        # -1 means the game has no weapon data for the item, not a cost.
        if isinstance(ap, (int, float)) and ap > 0:
            out['ap'] = int(ap)
        if isinstance(crit, (int, float)):
            out['crit_chance'] = int(crit)
        if isinstance(cbonus, (int, float)):
            out['crit_bonus'] = int(cbonus)
    return out


def decode_conditions(c_string):
    """Retro condition string -> ['Strength > 34', ...] (stat conditions only)."""
    out = []
    if not c_string:
        return out
    for code, op, val in re.findall(r'(C[A-Z])\s*([<>])\s*(\d+)', str(c_string)):
        stat = CONDITION_MAP.get(code)
        if stat:
            out.append(f'{stat} {op} {val}')
    return out


def min_player_level(c_string):
    """Minimum character level required by a 'PL>NN' condition, 1 when there is none.

    'PL>NN' is strictly greater, so the minimum is NN+1. 'PL<NN' is a max-level
    condition and does not raise the minimum.
    """
    best = 1
    for val in re.findall(r'PL\s*>\s*(\d+)', str(c_string or '')):
        best = max(best, int(val) + 1)
    return best


def build(items_root, sets_root, names_by_lang=None, set_bonuses=None,
          set_names_by_lang=None, spell_names_by_lang=None):
    items = items_root['u']
    names_by_lang = names_by_lang or {}
    set_names_by_lang = set_names_by_lang or {}
    spell_names_by_lang = spell_names_by_lang or {}
    set_bonuses = set_bonuses or []
    item_name_by_id = {iid: _ascii(it.get('n', ''))
                       for iid, it in items.items() if isinstance(it, dict)}
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

        def loc(lang):
            return (names_by_lang.get(lang) or {}).get(iid) or name_fr

        try:
            level = int(it.get('l', 1))
        except (TypeError, ValueError):
            level = 1
        # Mount certificates and a few other retro items gate usage by character
        # level with a "PL>NN" condition, not the item-level field `l` (which for
        # a certificate is just the mount tier, 1..10).
        level = max(level, min_player_level(it.get('c', '')))
        level = max(1, min(level, 200))  # structure.py indexes types by level 1..200
        is_weapon = weapon_type is not None
        stats, hits = decode_stats(it.get('istats', ''), is_weapon=is_weapon)
        rec = {
            'ankama_id': ankama_id,
            'ankama_type': 'equipment',
            'name_en': loc('en'), 'name_fr': name_fr,
            'name_es': loc('es'), 'name_pt': loc('pt'), 'name_de': loc('de'),
            'level': level,
            'w_type': w_type,
            'stats': stats + hits,
            'conditions': decode_conditions(it.get('c', '')),
        }
        for lang, lines in decode_spell_lines(it.get('istats', ''),
                                              spell_names_by_lang).items():
            rec['special_spell_%s' % lang] = '\n'.join(lines)
        if weapon_type:
            rec['weapon_type'] = weapon_type
            rec.update(decode_weapon_e(it.get('e')))
        equipment.append(rec)

    sets = []
    for sid, sd in sets_root.items():
        if not isinstance(sd, dict) or not sd.get('i'):
            continue
        try:
            set_ankama_id = int(sid)
        except (TypeError, ValueError):
            continue
        name_fr = sd.get('n') or ''

        def set_loc(lang):
            return (set_names_by_lang.get(lang) or {}).get(sid) or name_fr

        equipment_ids = [int(x) for x in sd['i']]
        # Set membership comes from the lang; per-piece bonuses from the vendored
        # snapshot. The model has 9 slots, so tiers above that are dropped.
        lang_item_names = {item_name_by_id.get(str(i), '') for i in sd['i']}
        lang_item_names.discard('')
        max_pieces = min(len(equipment_ids), 9)
        stats_list = [t for t in _match_set_bonuses(lang_item_names, set_bonuses,
                                                    set_ankama_id)
                      if t['effect_key'] <= max_pieces]
        # Canonical name is English (structure.py uses sets.name as the 'en' name);
        # other languages flow into the set_names table.
        sets.append({
            'ankama_id': set_ankama_id,
            'name_en': set_loc('en'), 'name_fr': name_fr,
            'name_es': set_loc('es'), 'name_pt': set_loc('pt'), 'name_de': set_loc('de'),
            'equipment_ids': equipment_ids,
            'stats_list': stats_list,
        })
    return equipment, sets


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw-dir', default='itemscraper/retro_raw')
    p.add_argument('--out-dir', default='itemscraper/retro')
    p.add_argument('--set-bonuses', default='itemscraper/retro_set_bonuses.json',
                   help='Vendored community set-bonus snapshot (not in the lang CDN)')
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

    # No lang file is complete, French least of all, so items missing from the
    # chosen one are taken from whichever language carries them.
    for lang in ('en', 'es', 'pt', 'de'):
        if lang == args.lang:
            continue
        items_path = raw / f'items_{lang}.json'
        stats_path = raw / f'itemstats_{lang}.json'
        if not items_path.exists():
            continue
        other = json.loads(items_path.read_text(encoding='utf-8'))['I']['u']
        other_stats = (json.loads(stats_path.read_text(encoding='utf-8'))['ISTA']
                       if stats_path.exists() else {})
        for iid, it in other.items():
            if iid in items_root['u'] or not isinstance(it, dict):
                continue
            it = dict(it)
            if iid in other_stats:
                it['istats'] = other_stats[iid]
            items_root['u'][iid] = it

    # Localized item names from the per-language lang files.
    names_by_lang = {}
    for lang in ('en', 'es', 'pt', 'de'):
        path = raw / f'items_{lang}.json'
        if path.exists():
            lang_items = json.loads(path.read_text(encoding='utf-8'))['I']['u']
            names_by_lang[lang] = {k: v.get('n') for k, v in lang_items.items()
                                   if isinstance(v, dict)}

    # Localized set names from the per-language itemsets lang files.
    set_names_by_lang = {}
    for lang in ('en', 'fr', 'es', 'pt', 'de'):
        path = raw / f'itemsets_{lang}.json'
        if path.exists():
            lang_sets = json.loads(path.read_text(encoding='utf-8'))['IS']
            set_names_by_lang[lang] = {sid: sd.get('n') for sid, sd in lang_sets.items()
                                       if isinstance(sd, dict)}

    set_bonuses = load_set_bonuses(args.set_bonuses)

    equipment, sets = build(items_root, sets_root, names_by_lang, set_bonuses,
                            set_names_by_lang, load_spell_names(raw))

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
