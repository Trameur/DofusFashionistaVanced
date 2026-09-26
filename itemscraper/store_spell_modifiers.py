#!/usr/bin/env python
# coding=utf-8

"""Store what items change on a spell into chardata/spell_modifiers/<version>.json.

    python itemscraper/store_spell_modifiers.py --game-version dofus3|beta|dofus2|retro|touch
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY,
             os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

from fashionistapulp.game_versions import dofus_versions  # noqa: E402
from store_item_obtainment import get_items_db_path  # noqa: E402

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'fashionsite', 'chardata',
                          'spell_modifiers')
EQUIPMENT_DIR = {'dofus3': '', 'beta': 'beta', 'dofus2': 'dofus2'}

KIND_BY_EFFECT = {
    280: ('min_range', 1),
    281: ('max_range', 1),
    282: ('modifiable_range', 0),
    283: ('damage', 1),
    284: ('heals', 1),
    285: ('ap_cost', -1),
    286: ('cooldown', -1),
    287: ('critical', 1),
    288: ('straight_line', 0),
    289: ('line_of_sight', 0),
    290: ('per_turn', 1),
    291: ('per_target', 1),
    292: ('cooldown_set', 0),
    293: ('base_damage', 1),
    294: ('max_range', -1),
    295: ('min_range', -1),
    296: ('ap_cost', 1),
    297: ('occupied_cell', 0),
    298: ('free_cell', 0),
    299: ('free_cell', 0),
    314: ('occupied_cell', 0),
    798: ('visible_target', 0),
    799: ('visible_target', 0),
}


def _load(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def _items_of(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get('items') or list(payload.values())
    return []


def _plain(text):
    text = unicodedata.normalize('NFC', text or '')
    text = re.sub(r'[  ]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _template_pattern(template):
    """A regex reading #1 and #3 back out of a sentence the template wrote."""
    parts = re.split(r'(#1|#3|\{\{?~p\w\}\}?|\{\{?~\w+\}\}?)', _plain(template))
    pattern = []
    for part in parts:
        if part == '#1':
            pattern.append(r'(?P<spell>.+?)')
        elif part == '#3':
            pattern.append(r'(?P<value>\d+)')
        elif re.match(r'^\{\{?~p\w\}\}?$', part):
            pattern.append(r'(?:s)?')
        elif re.match(r'^\{\{?~\w+\}\}?$', part):
            continue
        else:
            pattern.append(re.escape(part))
    return re.compile('^%s$' % ''.join(pattern))


def archive_tag(game_version, tag=None):
    """The raw/<tag> archive read; None for retro_raw and touch_raw, which carry no version."""
    if game_version not in EQUIPMENT_DIR:
        return None
    if tag:
        return tag
    import fashionista_version
    return {'dofus3': fashionista_version.FASHIONISTA_VERSION,
            'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
            'dofus2': fashionista_version.FASHIONISTA_DOFUS2_VERSION}[game_version]


def _dofusdude_rows(game_version, tag):
    """({ankama id: [[spell, effect, value]]}, {effect id: template}, misses)"""
    from pathlib import Path
    from get_spells import _load_datacenter_table, _load_translations
    root = Path(CURRENT_DIRECTORY) / 'raw' / tag
    effects = _load_datacenter_table(root / 'effects.json')
    french = _load_translations(root, ['fr'])['fr']
    spells = _load_datacenter_table(root / 'spells.json')
    templates = {}
    for effect_id, record in effects.items():
        text = french.get(str(record.get('descriptionId'))) or ''
        if record.get('category') == 3 and '#1' in text:
            templates[effect_id] = text
    patterns = sorted((effect_id, _template_pattern(text))
                      for effect_id, text in templates.items())

    directory = os.path.join(CURRENT_DIRECTORY, EQUIPMENT_DIR[game_version])
    rows = {}
    misses = {'unread': 0, 'other_spell_name': 0}
    for item in _items_of(_load(os.path.join(directory, 'all_equipment_fr.json'))):
        if not isinstance(item, dict) or item.get('ankama_id') is None:
            continue
        for effect in item.get('effects') or []:
            spell_id = effect.get('int_minimum')
            if not spell_id or spell_id not in spells:
                continue
            sentence = _plain(effect.get('formatted'))
            name = _plain(french.get(str(spells[spell_id].get('nameId'))))
            found = None
            for effect_id, pattern in patterns:
                match = pattern.match(sentence)
                if match:
                    found = (effect_id, match)
                    break
            if found is None:
                if name and name in sentence:
                    misses['unread'] += 1
                continue
            effect_id, match = found
            if name and name != match.group('spell'):
                misses['other_spell_name'] += 1
                continue
            value = (int(match.group('value'))
                     if 'value' in match.groupdict() else None)
            rows.setdefault(int(item['ankama_id']), []).append(
                [int(spell_id), effect_id, value])
    return rows, templates, misses


def _touch_rows():
    raw = os.path.join(CURRENT_DIRECTORY, 'touch_raw')
    effects = _load(os.path.join(raw, 'Effects_fr.json'))
    templates = {}
    for effect_id, record in effects.items():
        if not isinstance(record, dict):
            continue
        text = record.get('descriptionId') or ''
        if record.get('category') == 3 and '#1' in text:
            templates[int(effect_id)] = text
    rows = {}
    for ankama_id, item in _load(os.path.join(raw, 'Items_fr.json')).items():
        if not isinstance(item, dict):
            continue
        for effect in item.get('possibleEffects') or []:
            effect_id = effect.get('effectId')
            if effect_id not in templates or not effect.get('diceNum'):
                continue
            value = effect.get('value') if '#3' in templates[effect_id] else None
            rows.setdefault(int(ankama_id), []).append(
                [int(effect['diceNum']), effect_id, value])
    return rows, templates, {}


def _retro_rows():
    from get_equipments_retro import _hex
    raw = os.path.join(CURRENT_DIRECTORY, 'retro_raw')
    effects = _load(os.path.join(raw, 'effects_fr.json'))['E']
    templates = {}
    for effect_id, record in effects.items():
        if not isinstance(record, dict):
            continue
        text = record.get('d') or ''
        if 'sort #1' in text:
            templates[int(effect_id)] = text
    rows = {}
    for ankama_id, ista in _load(os.path.join(raw, 'itemstats_fr.json'))['ISTA'].items():
        for part in (ista or '').split(','):
            fields = part.split('#')
            effect_id = _hex(fields[0]) if fields and fields[0] else None
            if effect_id not in templates:
                continue
            spell_id = _hex(fields[1]) if len(fields) > 1 else None
            if not spell_id:
                continue
            value = (_hex(fields[3]) if len(fields) > 3 and '#3' in templates[effect_id]
                     else None)
            rows.setdefault(int(ankama_id), []).append([spell_id, effect_id, value])
    return rows, templates, {}


def collect(game_version, tag=None):
    if game_version in EQUIPMENT_DIR:
        return _dofusdude_rows(game_version, archive_tag(game_version, tag))
    if game_version == 'touch':
        return _touch_rows()
    if game_version == 'retro':
        return _retro_rows()
    raise SystemExit('unknown game version: %s' % game_version)


def items_the_site_holds(game_version):
    path = get_items_db_path(game_version).replace('\\', '/')
    conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        return {row[0] for row in conn.execute(
            "SELECT ankama_id FROM items WHERE ankama_id IS NOT NULL "
            "AND (ankama_type = 'equipment' OR ankama_type IS NULL)")}
    finally:
        conn.close()


def table(game_version, rows, templates, held, tag=None):
    kept = {}
    for ankama_id, item_rows in rows.items():
        if ankama_id not in held:
            continue
        unique = []
        for row in item_rows:
            if row not in unique:
                unique.append(row)
        kept[ankama_id] = unique
    used = sorted({row[1] for item_rows in kept.values() for row in item_rows})
    effects = {}
    for effect_id in used:
        kind, sign = KIND_BY_EFFECT.get(effect_id, ('other', 0))
        effects[effect_id] = {'kind': kind, 'sign': sign,
                              'text': _plain(templates.get(effect_id))}
    payload = {'game_version': game_version}
    read = archive_tag(game_version, tag)
    if read:
        payload['data_version'] = read
    payload.update({'effects': effects, 'items': kept})
    return payload


def write(payload, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, '%s.json' % payload['game_version'])
    lines = ['{', ' "game_version": %s,' % json.dumps(payload['game_version'])]
    if payload.get('data_version'):
        lines.append(' "data_version": %s,' % json.dumps(payload['data_version']))
    lines.append(' "effects": {')
    effect_lines = ['  "%d": %s' % (effect_id, json.dumps(entry, ensure_ascii=False,
                                                          sort_keys=True))
                    for effect_id, entry in sorted(payload['effects'].items())]
    lines.append(',\n'.join(effect_lines))
    lines.append(' },')
    lines.append(' "items": {')
    item_lines = ['  "%d": %s' % (ankama_id, json.dumps(item_rows))
                  for ankama_id, item_rows in sorted(payload['items'].items())]
    lines.append(',\n'.join(item_lines))
    lines.append(' }')
    lines.append('}')
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(line for line in lines if line != '') + '\n')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=dofus_versions())
    parser.add_argument('--tag', default=None,
                        help='archive under itemscraper/raw to read')
    parser.add_argument('--output-dir', default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows, templates, misses = collect(args.game_version, args.tag)
    payload = table(args.game_version, rows, templates,
                    items_the_site_holds(args.game_version), args.tag)
    path = write(payload, args.output_dir)
    count = sum(len(item_rows) for item_rows in payload['items'].values())
    unknown = sorted(effect_id for effect_id, entry in payload['effects'].items()
                     if entry['kind'] == 'other')
    print('[%s] Stored %d spell modifier rows on %d items (%d items in the '
          'files, %s) to %s' % (args.game_version, count, len(payload['items']),
                                len(rows), misses or 'no miss', path))
    if unknown:
        print('[%s] Effects with no kind, need attention: %s'
              % (args.game_version, unknown))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
