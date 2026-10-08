#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""store_weapon_conversions.py - the potions, engravings and shards that turn a
weapon's neutral lines into an element, the gems that reset them and the
weapons the game will not forgemage, into
fashionistapulp/fashionistapulp/weapon_conversions/<version>.json.

    dofus3, beta, dofus2  itemscraper/raw/<tag>/items.json, effects.json and <lang>.json
    touch                 itemscraper/touch_raw/Items_<lang>.json
    retro                 itemscraper/retro_raw/items_<lang>.json, skills and effects

    python itemscraper/store_weapon_conversions.py --game-version dofus3 --tag 3.7.4.4
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

import fashionista_version  # noqa: E402
from get_spells import (ELEMENT_ID_TO_TOKEN, _load_datacenter_table,  # noqa: E402
                        _load_json, _load_translations, _unwrap_array, effect_id_of)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'fashionistapulp', 'fashionistapulp',
                          'weapon_conversions')

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
LANGUAGES = ('de', 'en', 'es', 'fr', 'pt')

DEFAULT_TAG = {
    'dofus3': fashionista_version.FASHIONISTA_VERSION,
    'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
    'dofus2': fashionista_version.FASHIONISTA_DOFUS2_VERSION,
}

CONVERSION_EFFECT = 700
RESET_EFFECT = 3185

# diceNum is the base effect of the neutral line taken, diceSide that of the line given
NEUTRAL = ELEMENT_ID_TO_TOKEN[0].lower()
KIND_BY_WORD = {'damage': 'damage', 'steal': 'steal', 'heals': 'heal', 'healing': 'heal'}
# Touch's client links no base effect to an effect: the codes its potions use
TOUCH_CODES = {14: ('damage', NEUTRAL), 53: ('damage', 'water'), 54: ('damage', 'earth'),
               55: ('damage', 'fire'), 56: ('damage', 'air')}
KINDS = ('damage', 'steal', 'heal')
TIERS = ('strong', 'medium', 'weak')

# m_flags bit of a 3.x item the game lets a smith forgemage
FORGEABLE_FLAG = 0x40

RETRO_DAMAGE_EFFECTS = (96, 97, 98, 99)
RETRO_LANGUAGE = 'fr'
RETRO_JOB_CRITERION = ('Pj', '=')
RATE_NOTE = 'not published by the game'

UNREPORTED_FIELDS = {'conversions', 'gems', 'unforgeable', 'data_version'}


def _modern_dir(version, tag=None):
    return os.path.join(CURRENT_DIRECTORY, 'raw', tag or DEFAULT_TAG[version])


def source_path(version, tag=None, language=RETRO_LANGUAGE):
    if version == 'touch':
        return os.path.join(CURRENT_DIRECTORY, 'touch_raw', 'Items_fr.json')
    if version == 'retro':
        return os.path.join(CURRENT_DIRECTORY, 'retro_raw', 'items_%s.json' % language)
    return os.path.join(_modern_dir(version, tag), 'items.json')


def available_languages(version, tag=None):
    if version == 'touch':
        pattern = os.path.join(CURRENT_DIRECTORY, 'touch_raw', 'Items_%s.json')
    elif version == 'retro':
        pattern = os.path.join(CURRENT_DIRECTORY, 'retro_raw', 'items_%s.json')
    else:
        pattern = os.path.join(_modern_dir(version, tag), '%s.json')
    return [language for language in LANGUAGES
            if os.path.exists(pattern % language)]


def touch_languages(previous=None):
    """([languages Touch still serves], notes); it answers the others in English."""
    from download_touch_data import served_languages
    on_disk = available_languages('touch')
    served = served_languages()
    if served:
        return [language for language in on_disk if language in served], []
    kept = (previous or {}).get('languages')
    if kept:
        return ([language for language in on_disk if language in kept],
                ['serverLanguages unreadable, kept %s' % ', '.join(kept)])
    return on_disk, ['serverLanguages unreadable, read every file on disk']


def _modern_items(folder):
    """({id: (record, effects, is_weapon)}, flag): the 3.x Unity export or the 2.73 list."""
    data = _load_json(Path(folder) / 'items.json')
    if isinstance(data, list):
        return {int(record['id']): (record, record.get('possibleEffects') or [],
                                    'apCost' in record)
                for record in data if record.get('id') is not None}, 'enhanceable'
    refs = {ref['rid']: ref for ref in data['references']['RefIds']}
    keys = data['objectsById']['m_keys']['Array']
    values = data['objectsById']['m_values']['Array']
    items = {}
    for key, value in zip(keys, values):
        ref = refs.get(value.get('rid'))
        if ref is None:
            continue
        record = ref['data']
        effects = [refs[effect['rid']]['data']
                   for effect in _unwrap_array(record.get('possibleEffects'))
                   if effect.get('rid') in refs]
        items[int(key)] = (record, effects,
                           ref['type']['class'] == 'WeaponData')
    return items, 'm_flags bit 0x%x' % FORGEABLE_FLAG


def _named(effect, english):
    """(kind, element) of an effect: its elementId, and the last word of its English text."""
    if effect is None:
        return None
    element = ELEMENT_ID_TO_TOKEN.get(effect.get('elementId'))
    words = re.findall(r'[a-z]+', (english.get(str(effect.get('descriptionId'))) or '').lower())
    kind = KIND_BY_WORD.get(words[-1]) if words else None
    return (kind, element.lower()) if kind and element else None


def client_codes(folder, items=None, english=None):
    """{base effect id: (kind, element)}, from 3.x effectId or 2.73 baseEffectId."""
    folder = Path(folder)
    effects = _load_datacenter_table(folder / 'effects.json')
    if english is None:
        english = _load_translations(folder, ['en'])['en']
    if items is None:
        items, _flag = _modern_items(folder)
    carried = {}
    for record in effects.values():
        if record.get('effectId') is not None:
            carried.setdefault(int(record['effectId']), set()).add(int(record['id']))
    for item in items.values():
        for line in item[1]:
            if line.get('baseEffectId') is not None:
                carried.setdefault(int(line['baseEffectId']), set()).add(effect_id_of(line))
    codes = {}
    for base, effect_ids in carried.items():
        named = {_named(effects.get(effect_id), english) for effect_id in effect_ids}
        if len(named) == 1 and None not in named:
            codes[base] = named.pop()
    return codes


def _tiers(levels):
    """{level: tier}, the highest level strong and the lowest weak; None past three levels."""
    ordered = sorted(set(levels), reverse=True)
    names = {1: TIERS[:1], 2: (TIERS[0], TIERS[-1]), 3: TIERS}.get(len(ordered))
    return dict(zip(ordered, names)) if names else None


def _ranked(rows, notes):
    kept = []
    for kind in KINDS:
        of_kind = [row for row in rows if row['kind'] == kind]
        if not of_kind:
            continue
        tiers = _tiers(row['level'] for row in of_kind)
        if tiers is None:
            notes.append('%s items at %d levels, no tier read: %s' % (
                kind, len({row['level'] for row in of_kind}),
                ', '.join(str(row['ankama_id']) for row in of_kind)))
            continue
        rates = {}
        seen = set()
        for row in of_kind:
            row['tier'] = tiers[row['level']]
            rates.setdefault(row['tier'], set()).add(row['rate'])
            if (row['tier'], row['element']) in seen:
                notes.append('%s %s %s held by more than one item'
                             % (kind, row['tier'], row['element']))
            seen.add((row['tier'], row['element']))
        for tier, values in sorted(rates.items()):
            if len(values) > 1:
                notes.append('%s %s items disagree on the rate: %s'
                             % (kind, tier, sorted(values, key=_rate_order)))
        known = [min(rates[tier], key=_rate_order) for tier in TIERS if tier in rates]
        if None not in known and known != sorted(known, reverse=True):
            notes.append('%s rates do not fall with the level: %s' % (kind, known))
        kept.extend(of_kind)
    return sorted(kept, key=lambda row: row['ankama_id'])


def _rate_order(rate):
    return -1 if rate is None else rate


def _effect_rows(items, names_of, notes, codes):
    """(conversion rows, gem rows) of {id: (record, effects, ...)}."""
    rows = []
    gems = []
    for ankama_id, item in sorted(items.items()):
        record, effects = item[0], item[1]
        for effect in effects:
            effect_id = effect_id_of(effect)
            if effect_id == RESET_EFFECT:
                gems.append({'ankama_id': ankama_id,
                             'level': record.get('level'),
                             'max_weapon_level': effect.get('value'),
                             'type_id': record.get('typeId'),
                             'names': names_of(ankama_id, record)})
                continue
            if effect_id != CONVERSION_EFFECT:
                continue
            source = codes.get(effect.get('diceNum'))
            target = codes.get(effect.get('diceSide'))
            if (source is None or target is None or source[1] != NEUTRAL
                    or source[0] != target[0] or effect.get('value') is None):
                notes.append('%d: unknown conversion %s -> %s at %s, skipped' % (
                    ankama_id, effect.get('diceNum'), effect.get('diceSide'),
                    effect.get('value')))
                continue
            rows.append({'ankama_id': ankama_id, 'kind': source[0],
                         'element': target[1],
                         'rate': effect['value'] / 100,
                         'level': record.get('level'),
                         'type_id': record.get('typeId'),
                         'names': names_of(ankama_id, record)})
    return _ranked(rows, notes), gems


def _modern(version, tag, languages, notes):
    folder = _modern_dir(version, tag)
    items, flag = _modern_items(folder)
    texts = _load_translations(Path(folder), languages)
    codes = client_codes(folder, items, texts.get('en'))

    def names_of(_ankama_id, record):
        key = str(record.get('nameId'))
        return {language: texts[language].get(key) for language in languages}

    rows, gems = _effect_rows(items, names_of, notes, codes)
    if flag == 'enhanceable':
        unforgeable = [key for key, (record, _effects, weapon) in items.items()
                       if weapon and not record.get('enhanceable')]
    else:
        unforgeable = [key for key, (record, _effects, weapon) in items.items()
                       if weapon and not record.get('m_flags', 0) & FORGEABLE_FLAG]
    return {'conversions': rows, 'gems': gems, 'rate_published': True,
            'unforgeable': sorted(unforgeable), 'unforgeable_source': flag}


def _touch(languages, notes):
    folder = Path(CURRENT_DIRECTORY) / 'touch_raw'
    texts = {language: _load_json(folder / ('Items_%s.json' % language))
             for language in languages}
    items = {}
    for record in _load_json(folder / 'Items_fr.json').values():
        if isinstance(record, dict) and record.get('id') is not None:
            items[int(record['id'])] = (record, record.get('possibleEffects') or [],
                                        record.get('_type') == 'Weapon')

    def names_of(ankama_id, _record):
        return {language: (table.get(str(ankama_id)) or {}).get('nameId')
                for language, table in texts.items()}

    rows, gems = _effect_rows(items, names_of, notes, TOUCH_CODES)
    unforgeable = [key for key, (record, _effects, weapon) in items.items()
                   if weapon and not record.get('enhanceable')]
    return {'conversions': rows, 'gems': gems, 'rate_published': True,
            'unforgeable': sorted(unforgeable), 'unforgeable_source': 'enhanceable'}


def _retro_file(name, language):
    return Path(CURRENT_DIRECTORY) / 'retro_raw' / ('%s_%s.json' % (name, language))


def _retro_items(language):
    return _load_json(_retro_file('items', language))['I']['u']


def retro_element_words(language=RETRO_LANGUAGE):
    """{word: element}, as Retro's own damage effects end on it: '(eau)'."""
    from get_equipments_retro import ELEMENT_BY_EFFECT
    effects = _load_json(_retro_file('effects', language))['E']
    words = {}
    for effect_id in RETRO_DAMAGE_EFFECTS:
        match = re.search(r'\(([^()]+)\)\s*$', effects[str(effect_id)]['d'])
        if match:
            words[match.group(1).strip().lower()] = ELEMENT_BY_EFFECT[effect_id].lower()
    return words


def _retro_jobs(criteria):
    """Jobs whose members the criteria let use the item."""
    from item_criteria import CriteriaError, atoms, parse
    try:
        tree = parse(criteria)
    except CriteriaError:
        return set()
    return {int(value) for code, operator, value in atoms(tree)
            if (code, operator) == RETRO_JOB_CRITERION and value.isdigit()}


def _retro(languages, notes, source_language=RETRO_LANGUAGE):
    from get_equipments_retro import mage_item_types
    items = _retro_items(source_language)
    texts = {language: _retro_items(language) for language in languages}
    skills = _load_json(_retro_file('skills', source_language))['SK']
    words = retro_element_words(source_language)
    if len(words) != len(RETRO_DAMAGE_EFFECTS):
        notes.append('effects_%s.json names %d elements, not %d'
                     % (source_language, len(words), len(RETRO_DAMAGE_EFFECTS)))
    # Pieces the language misses come from the others, as get_equipments_retro reads them
    catalogue = dict(items)
    for table in texts.values():
        for key, record in table.items():
            catalogue.setdefault(key, record)
    weapons = {key: record for key, record in catalogue.items()
               if isinstance(record, dict) and 'e' in record}
    weapon_types = {record.get('t') for record in weapons.values()}
    smiths = {skill.get('j') for skill in skills.values()
              if isinstance(skill, dict) and skill.get('f') in weapon_types}
    # No effect on Retro's potions: the weapon smiths use them, their text names the element
    naming = re.compile(r'\b(%s)\b' % '|'.join(map(re.escape, sorted(words))), re.I)
    rows = []
    for key, record in items.items():
        if not isinstance(record, dict) or key in weapons:
            continue
        jobs = _retro_jobs(record.get('c'))
        if not jobs or not jobs <= smiths:
            continue
        named = {words[word.lower()] for word in naming.findall(record.get('d') or '')}
        if len(named) != 1:
            notes.append('%s: a weapon smith item naming %d elements, skipped'
                         % (key, len(named)))
            continue
        rows.append({'ankama_id': int(key), 'kind': 'damage',
                     'element': named.pop(), 'rate': None,
                     'level': record.get('l'), 'type_id': record.get('t'),
                     'names': {language: (table.get(key) or {}).get('n')
                               for language, table in texts.items()}})
    mage_types = mage_item_types(skills)
    unforgeable = [int(key) for key, record in weapons.items()
                   if str(record.get('t')) not in mage_types or record.get('fm') is False]
    return {'conversions': _ranked(rows, notes), 'gems': [],
            'rate_published': False, 'rate_note': RATE_NOTE,
            'unforgeable': sorted(unforgeable),
            'unforgeable_source': 'smithmagic skill types and the fm flag'}


def extract(version, tag=None, languages=None, source_language=RETRO_LANGUAGE):
    """(table, notes): what the version's client states, and what it could not read."""
    notes = []
    if languages is None:
        languages = available_languages(version, tag)
    languages = [language for language in LANGUAGES if language in languages]
    if version == 'touch':
        body = _touch(languages, notes)
    elif version == 'retro':
        body = _retro(languages, notes, source_language)
    else:
        body = _modern(version, tag, languages, notes)
    table = {'game_version': version, 'languages': languages}
    if version in DEFAULT_TAG:
        table['data_version'] = tag or DEFAULT_TAG[version]
    table.update(body)
    return table, notes


def _by_id(rows):
    return {row['ankama_id']: row for row in rows or []}


def changes(previous, table):
    lines = []
    for section in ('conversions', 'gems'):
        before, after = _by_id(previous.get(section)), _by_id(table.get(section))
        for ankama_id in sorted(set(before) | set(after)):
            old, new = before.get(ankama_id), after.get(ankama_id)
            if old is None:
                lines.append('%s %d added' % (section, ankama_id))
            elif new is None:
                lines.append('%s %d removed' % (section, ankama_id))
            else:
                for field in sorted(set(old) | set(new)):
                    if old.get(field) != new.get(field):
                        lines.append('%s %d %s changed: %s -> %s' % (
                            section, ankama_id, field, old.get(field),
                            new.get(field)))
    before = set(previous.get('unforgeable') or [])
    after = set(table.get('unforgeable') or [])
    if after - before:
        lines.append('unforgeable added: %s' % sorted(after - before))
    if before - after:
        lines.append('unforgeable removed: %s' % sorted(before - after))
    for field in sorted((set(previous) | set(table)) - UNREPORTED_FIELDS):
        if previous.get(field) != table.get(field):
            lines.append('%s changed: %s -> %s' % (
                field, previous.get(field), table.get(field)))
    return lines


def summary(table):
    rates = {}
    for row in table['conversions']:
        rates.setdefault((row['kind'], row['tier']), set()).add(row['rate'])
    parts = ['%s %s %s' % (kind, tier, '/'.join(
        'null' if rate is None else '%g' % rate
        for rate in sorted(rates[(kind, tier)], key=_rate_order)))
        for kind in KINDS for tier in TIERS if (kind, tier) in rates]
    unforgeable = table.get('unforgeable')
    return '%d conversions (%s), %d gems, %s unforgeable weapons' % (
        len(table['conversions']), ', '.join(parts) or 'none',
        len(table['gems']),
        'unknown' if unforgeable is None else len(unforgeable))


def output_path(version):
    return os.path.join(OUTPUT_DIR, '%s.json' % version)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', required=True, choices=VERSIONS)
    parser.add_argument('--tag', default=None,
                        help='archive under itemscraper/raw to read; touch_raw '
                             'and retro_raw carry no version')
    parser.add_argument('--lang', default=RETRO_LANGUAGE,
                        help='retro: language of the lang files update_data_retro.py '
                             'downloaded first')
    args = parser.parse_args(argv)
    version = args.game_version

    source = source_path(version, args.tag, args.lang)
    if not os.path.exists(source):
        print('%s: no %s on this machine, weapon conversions kept as they were'
              % (version, os.path.relpath(source, PROJECT_ROOT)))
        return 0

    path = output_path(version)
    previous = _load_json(Path(path)) if os.path.exists(path) else None
    languages = None
    if version == 'touch':
        languages, notes = touch_languages(previous)
        for line in notes:
            print('warning: touch: %s' % line)
    table, notes = extract(version, args.tag, languages, args.lang)
    for line in notes:
        print('warning: %s: %s' % (version, line))
    if previous is not None:
        for line in changes(previous, table):
            print('warning: %s %s' % (version, line))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        json.dump(table, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write('\n')
    label = table.get('data_version')
    print('%s%s: %s' % (version, ' ' + label if label else '', summary(table)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
