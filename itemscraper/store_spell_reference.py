#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""store_spell_reference.py - every class spell of a version, with what the
game says about it, into fashionsite/chardata/spell_reference/<version>.json.

    python itemscraper/store_spell_reference.py --game-version dofus3

The spells page only ever knew the spells that deal damage or give a buff, and
only their damage. This carries the rest: the game's own description, the AP,
the range, how often a turn allows the cast, and the critical rate, for every
spell of every class.

What each version can answer differs, and the file only holds what its own
source has:
  dofus3, beta  the datacenter class-spell dump: everything
  touch         the production proxy: everything
  retro         the 1.29 lang files: everything
  dofus2        the 2.73 archive ships no spell level at all, so names,
                descriptions and types only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

import fashionista_version  # noqa: E402
from untranslated_tag import clean_description  # noqa: E402

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'fashionsite', 'chardata',
                          'spell_reference')

# Dofus 2 and Retro keep the class ids the game has always used.
CLASS_ID_TO_NAME = {
    1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor',
    6: 'Ecaflip', 7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida',
    11: 'Sacrier', 12: 'Pandawa', 13: 'Rogue', 14: 'Masqueraider',
    15: 'Foggernaut', 16: 'Eliotrope', 17: 'Huppermage', 18: 'Ouginak',
    19: 'Forgelance',
}


# The client writes its own markup inside the text: a spell reference as
# {{spell,id,rank::label}}, an element icon as <sprite name="terre">, and Unity
# rich text for emphasis and colour. The label of a reference is the readable
# part, the icon always sits in front of the word it illustrates, and the rest
# is decoration, so the text keeps only what a reader needs.
_SPELL_REFERENCE = re.compile(r'\{\{\s*spell\s*,[^:}]*::(.*?)\}\}', re.S)
_SPRITE = re.compile(r'<sprite[^>]*>')
_RICH_TEXT = re.compile(r'</?(?:b|i|u|strong|em|color|size|font)\b[^>]*>', re.I)
_SPACES = re.compile(r'[ \t]{2,}')


def clean_text(text):
    """The game's own words, with the client's markup taken out."""
    if not text:
        return ''
    cleaned = clean_description(text)
    cleaned = _SPELL_REFERENCE.sub(lambda match: match.group(1), cleaned)
    cleaned = _SPRITE.sub('', cleaned)
    cleaned = _RICH_TEXT.sub('', cleaned)
    cleaned = _SPACES.sub(' ', cleaned)
    return '\n'.join(line.strip() for line in cleaned.split('\n')).strip()


def _clean_map(values):
    return {lang: clean_text(text) for lang, text in (values or {}).items()}


def _rank_values(levels, key, transform=None):
    """One value per rank, or None when the source never states it."""
    out = []
    for level in levels:
        value = level.get(key)
        out.append(transform(value) if transform else value)
    return out if any(value not in (None, 0) for value in out) else None


def _drop_empty(spell):
    for key in ('name', 'description', 'kind'):
        if key in spell:
            spell[key] = _clean_map(spell[key])
    return {key: value for key, value in spell.items() if value not in (None, {})}


# The client's own push effects. 1103 is stated as dealing no damage; the rest
# damage the target when it stops against an obstacle.
PUSH_EFFECT_IDS = {5: True, 1021: True, 4002: True, 1103: False}


def _state_requirement(target_mask):
    """The state a row needs, from the client's own target mask.

    '*E5282' means the state must be present, '*e5282' that it must be absent.
    Torrent and Froth carry both branches at once: they push at High Tide and
    attract at Low, so recording the push without its gate credits the Steamer
    a push it only makes half the time.
    """
    for token in (target_mask or '').split(','):
        token = token.strip()
        if len(token) < 3 or not token.startswith('*'):
            continue
        flag, digits = token[1], token[2:]
        if flag not in 'Ee' or not digits.isdigit():
            continue
        return {'state': int(digits), 'present': flag == 'E'}
    return None


# Effect 417 takes pushback resistance off the target. Checked against Ankama's
# own wording on all ten spells that carry it: nine say they reduce it and the
# tenth, Break-In, says it steals it, which is the same for the target. The
# target masks are not read: their grammar is undocumented and guessing at it
# is how a spell ends up in its own trigger list.
PUSHBACK_RESIST_REMOVED = 417


def _target_pushback_resist_per_rank(levels):
    """How much pushback resistance the target loses, per rank, or None."""
    out = []
    for level in levels:
        worst = 0
        for effect in level.get('effects') or []:
            if effect.get('effect_id') != PUSHBACK_RESIST_REMOVED:
                continue
            worst = max(worst, (effect.get('dice') or {}).get('min') or 0)
        out.append(worst or None)
    return out if any(out) else None


def _push_per_rank(levels):
    """[{'cells': n, 'damaging': bool, 'needs': {...}}, ...], one per rank,
    None when it never pushes. A rank that both pushes and pushes-without-damage
    keeps the larger damaging push: that is the branch a damage model cares
    about."""
    out = []
    for level in levels:
        best = None
        for effect in level.get('effects') or []:
            damaging = PUSH_EFFECT_IDS.get(effect.get('effect_id'))
            if damaging is None:
                continue
            cells = (effect.get('dice') or {}).get('min') or 0
            if not cells:
                continue
            candidate = {'cells': cells, 'damaging': bool(damaging)}
            needs = _state_requirement(effect.get('target_mask'))
            if needs:
                candidate['needs'] = needs
            if best is None:
                best = candidate
            elif candidate['damaging'] and not best['damaging']:
                best = candidate
            elif candidate['damaging'] == best['damaging'] \
                    and candidate['cells'] > best['cells']:
                best = candidate
        out.append(best)
    return out if any(out) else None


from version_tags import latest_tag  # noqa: E402

SUMMON_EFFECT_ID = 181


def _monsters_by_id(raw_dir):
    """The client's monster table, flattened to {id: entry}."""
    path = os.path.join(raw_dir, 'monsters.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    found = {}

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get('id'), int) and 'spells' in node:
                found[node['id']] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return found


def _spell_ids_of(monster):
    array = (monster.get('spells') or {})
    if isinstance(array, str):
        return []
    return [int(value) for value in (array.get('Array') or [])
            if isinstance(value, int)]


def _summon_push_per_rank(levels, monsters, pushes_by_spell):
    """{'least': n, 'most': n} the thing this spell places can push, per rank.

    Tacturret carries no push of its own; the turret it summons does, through
    Barycentre, whose own text says the push "increases based on the level of
    evolution". Its three rows are 2, 4 and 6 cells, so a single number would
    either flatter a fresh turret or rob an evolved one.
    """
    out = []
    for level in levels:
        least = most = 0
        for effect in level.get('effects') or []:
            if effect.get('effect_id') != SUMMON_EFFECT_ID:
                continue
            monster = monsters.get((effect.get('dice') or {}).get('min'))
            if not monster:
                continue
            for spell_id in _spell_ids_of(monster):
                spread = pushes_by_spell.get(spell_id)
                if not spread:
                    continue
                least = min(least or spread[0], spread[0])
                most = max(most, spread[1])
        out.append({'least': least, 'most': most} if most else None)
    return out if any(out) else None


def _pushes_by_spell(spells):
    """{spell id: (least, most)} cells, for every spell that pushes damagingly.

    Both ends, because one spell can carry several push rows: a summon that
    grows keeps them all on one spell rather than on several ranks.
    """
    out = {}
    for spell in spells:
        cells = []
        for level in spell.get('levels') or []:
            for effect in level.get('effects') or []:
                if not PUSH_EFFECT_IDS.get(effect.get('effect_id')):
                    continue
                value = (effect.get('dice') or {}).get('min') or 0
                if value:
                    cells.append(value)
        if cells:
            out[spell.get('ankama_id')] = (min(cells), max(cells))
    return out


def read_modern(path):
    """dofus3 and beta: the transformed class-spell dump carries it all."""
    with open(path, encoding='utf-8') as handle:
        classes = json.load(handle)
    # The push a summon performs lives on the summon's own spell, so the whole
    # spell dump and the monster table are both needed to see it.
    raw_dir = os.path.join(CURRENT_DIRECTORY, 'raw', latest_tag(os.path.join(CURRENT_DIRECTORY, 'raw')))
    monsters = _monsters_by_id(raw_dir)
    every_spell = []
    dump = os.path.join(CURRENT_DIRECTORY, 'transformed_spells.json')
    if monsters and os.path.exists(dump):
        with open(dump, encoding='utf-8') as handle:
            every_spell = json.load(handle)
    pushes_by_spell = _pushes_by_spell(every_spell)
    out = {}
    for class_name, block in classes.items():
        spells = []
        for spell in block.get('spells') or []:
            levels = spell.get('levels') or []
            variant = (spell.get('variant_group') or {}).get('variant_id')
            spells.append(_drop_empty({
                'id': spell.get('ankama_id'),
                'name': {lang: spell.get('name_%s' % lang) or ''
                         for lang in LANGUAGES},
                'description': {lang: spell.get('description_%s' % lang) or ''
                                for lang in LANGUAGES},
                'kind': {lang: spell.get('type_name_%s' % lang) or ''
                         for lang in LANGUAGES},
                'levels': spell.get('level_requirements') or [],
                'ap': _rank_values(levels, 'ap_cost'),
                'range': [[(level.get('range') or {}).get('min'),
                           (level.get('range') or {}).get('max')]
                          for level in levels] or None,
                'per_turn': _rank_values(levels, 'max_cast_per_turn'),
                'per_target': _rank_values(levels, 'max_cast_per_target'),
                'cooldown': _rank_values(levels, 'min_cast_interval'),
                'crit': _rank_values(levels, 'critical_hit_probability'),
                'stacks': _rank_values(levels, 'max_stack'),
                'push': _push_per_rank(levels),
                'strips_pushback_resist': _target_pushback_resist_per_rank(levels),
                'summon_push': _summon_push_per_rank(levels, monsters,
                                                     pushes_by_spell),
                'variant': variant,
            }))
        if spells:
            out[class_name] = spells
    return out


def read_dofus2(tag):
    """The 2.73 archive has the spells and the five languages, but not one
    spell level, so the numbers stay out."""
    root = os.path.join(CURRENT_DIRECTORY, 'raw', tag)

    def load(name):
        with open(os.path.join(root, name), encoding='utf-8') as handle:
            return json.load(handle)

    texts = {}
    for lang in LANGUAGES:
        entries = load('%s.json' % lang)
        table = entries.get('texts', entries) if isinstance(entries, dict) else {}
        texts[lang] = {str(key): value for key, value in table.items()}
    spells = {str(row['id']): row for row in load('spells.json')}
    types = {str(row['id']): row for row in load('spell_types.json')}

    def text(lang, text_id):
        return texts.get(lang, {}).get(str(text_id)) or ''

    out = {}
    for breed in load('breeds.json'):
        class_name = CLASS_ID_TO_NAME.get(breed.get('id'))
        if not class_name:
            continue
        found = []
        for variant in (breed.get('breedSpellsId') or []):
            spell = spells.get(str(variant))
            if spell is None:
                continue
            type_row = types.get(str(spell.get('typeId'))) or {}
            found.append(_drop_empty({
                'id': spell.get('id'),
                'name': {lang: text(lang, spell.get('nameId'))
                         for lang in LANGUAGES},
                'description': {lang: text(lang, spell.get('descriptionId'))
                                for lang in LANGUAGES},
                'kind': {lang: text(lang, type_row.get('longNameId'))
                         for lang in LANGUAGES},
            }))
        if found:
            out[class_name] = found
    return out


def read_retro(raw_dir):
    """The 1.29 lang files: one per language, each holding every spell."""
    def load(name):
        with open(os.path.join(raw_dir, name), encoding='utf-8') as handle:
            return json.load(handle)

    per_lang = {}
    for lang in LANGUAGES:
        path = os.path.join(raw_dir, 'spells_%s.json' % lang)
        per_lang[lang] = load('spells_%s.json' % lang)['S'] \
            if os.path.exists(path) else {}
    classes = load('classes_fr.json')['G']
    french = per_lang['fr']

    # The 21-wide level array, as get_spells_retro decodes it.
    SLOTS = {'cooldown': 6, 'per_turn': 7, 'per_target': 8, 'crit': 15,
             'range_max': 16, 'range_min': 17, 'ap': 18}
    RANKS = ('l1', 'l2', 'l3', 'l4', 'l5', 'l6')

    out = {}
    for class_id, class_name in CLASS_ID_TO_NAME.items():
        block = classes.get(str(class_id))
        if not isinstance(block, dict) or not block.get('s'):
            continue
        found = []
        for spell_id in block['s']:
            spell = french.get(str(spell_id))
            if not isinstance(spell, dict) or not spell.get('n'):
                continue
            ranks = [spell.get(key) for key in RANKS]
            ranks = [rank for rank in ranks if isinstance(rank, list)
                     and len(rank) >= 21]

            def per_rank(slot):
                values = [rank[SLOTS[slot]] for rank in ranks]
                values = [value if isinstance(value, int) else None
                          for value in values]
                return values if any(values) else None

            names, descriptions = {}, {}
            for lang, table in per_lang.items():
                localized = table.get(str(spell_id)) or {}
                names[lang] = localized.get('n') or spell.get('n') or ''
                descriptions[lang] = localized.get('d') or spell.get('d') or ''
            ranges = [[rank[SLOTS['range_min']], rank[SLOTS['range_max']]]
                      for rank in ranks]
            found.append(_drop_empty({
                'id': spell_id,
                'name': names,
                'description': descriptions,
                'levels': [rank[2] for rank in ranks
                           if isinstance(rank[2], int)],
                'ap': per_rank('ap'),
                'range': ranges or None,
                'per_turn': per_rank('per_turn'),
                'per_target': per_rank('per_target'),
                'cooldown': per_rank('cooldown'),
                # The X of 1/X, not a percentage.
                'crit': per_rank('crit'),
            }))
        if found:
            out[class_name] = found
    return out


def read_touch():
    """Dofus Touch answers from the production proxy, one pass per language."""
    import requests

    sys.path.insert(0, CURRENT_DIRECTORY)
    import get_spells_touch as touch  # noqa: E402

    config = requests.get(touch.CONFIG_URL + '?lang=fr',
                          headers={'User-Agent': touch.UA}, timeout=30).json()
    data_url = config.get('dataUrl') or touch.FALLBACK_DATA_URL
    breeds = touch.fetch_table(data_url, 'Breeds', 'fr')
    levels = touch.fetch_table(data_url, 'SpellLevels', 'fr')
    spells_by_lang = {lang: touch.fetch_table(data_url, 'Spells', lang)
                      for lang in LANGUAGES}
    types_by_lang = {lang: touch.fetch_table(data_url, 'SpellTypes', lang)
                     for lang in LANGUAGES}
    french = spells_by_lang['fr']

    out = {}
    for breed_id, class_name in touch.CLASS_ID_TO_NAME.items():
        breed = breeds.get(str(breed_id))
        if not breed:
            continue
        found = []
        for spell_id in (breed.get('breedSpellsId') or []):
            spell = french.get(str(spell_id))
            if not spell:
                continue
            ranks = [levels.get(str(level_id)) or {}
                     for level_id in (spell.get('spellLevels') or [])]
            names, descriptions, kinds = {}, {}, {}
            for lang in LANGUAGES:
                localized = (spells_by_lang.get(lang) or {}).get(str(spell_id)) or {}
                names[lang] = localized.get('nameId') or ''
                descriptions[lang] = localized.get('descriptionId') or ''
                type_row = ((types_by_lang.get(lang) or {})
                            .get(str(spell.get('typeId'))) or {})
                kinds[lang] = type_row.get('longNameId') or ''
            found.append(_drop_empty({
                'id': spell.get('id'),
                'name': names,
                'description': descriptions,
                'kind': kinds,
                'levels': _rank_values(ranks, 'minPlayerLevel') or [],
                'ap': _rank_values(ranks, 'apCost'),
                'range': [[rank.get('minRange'), rank.get('range')]
                          for rank in ranks] or None,
                'per_turn': _rank_values(ranks, 'maxCastPerTurn'),
                'per_target': _rank_values(ranks, 'maxCastPerTarget'),
                'cooldown': _rank_values(ranks, 'minCastInterval'),
                'crit': _rank_values(ranks, 'criticalHitProbability'),
                'stacks': _rank_values(ranks, 'maxStack'),
            }))
        if found:
            out[class_name] = found
    return out


def build(game_version, tag=None):
    if game_version in ('dofus3', 'beta'):
        name = ('transformed_class_spells.json' if game_version == 'dofus3'
                else 'transformed_class_spells_beta.json')
        return read_modern(os.path.join(CURRENT_DIRECTORY, name))
    if game_version == 'dofus2':
        return read_dofus2(tag or fashionista_version.FASHIONISTA_DOFUS2_VERSION)
    if game_version == 'retro':
        return read_retro(os.path.join(CURRENT_DIRECTORY, 'retro_raw'))
    if game_version == 'touch':
        return read_touch()
    raise SystemExit('unknown version %s' % game_version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=('dofus3', 'beta', 'dofus2', 'touch', 'retro'))
    parser.add_argument('--tag', default=None)
    args = parser.parse_args()

    classes = build(args.game_version, args.tag)
    if not classes:
        raise SystemExit('%s: no class spell found' % args.game_version)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, '%s.json' % args.game_version)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        json.dump(classes, handle, ensure_ascii=False, indent=1,
                  sort_keys=True)
    total = sum(len(spells) for spells in classes.values())
    with_numbers = sum(1 for spells in classes.values()
                       for spell in spells if spell.get('ap'))
    print('%s: %d spells across %d classes, %d with their cast numbers'
          % (args.game_version, total, len(classes), with_numbers))


if __name__ == '__main__':
    main()
