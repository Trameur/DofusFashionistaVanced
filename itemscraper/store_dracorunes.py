#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""store_dracorunes.py - the dracorunes of a client dump, into
fashionistapulp/fashionistapulp/dracorunes/<version>.json.

A rune is an item whose effects carry action 4081 (an element, named by the
effect's diceSide), 4082 (resistances) or 4083 (power). Nothing in the client
defines those actions, so the rounding is the devblog's. The power rune's keep
rate is the value of its 4083 effect. A rune's name comes from the <lang>.json
files of the dump, when it has them. A dump without rune items writes nothing
and removes the file a previous run left for that version.

    python itemscraper/store_dracorunes.py --game-version beta --tag 3.8.1.2
    python itemscraper/store_dracorunes.py path/to/raw/3.8.1.2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY,
             os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

import fashionista_version  # noqa: E402
from data_file_ops import replace_file  # noqa: E402
from fashionistapulp.dracorunes import DEFAULT_FOLDER, ELEMENT_PAIRS  # noqa: E402
from fashionistapulp.exo_options import FORGEABLE_TYPES  # noqa: E402
from get_spells import (  # noqa: E402
    ELEMENT_ID_TO_TOKEN, LANGUAGES, _load_json, _load_translations, _unwrap_array)

DEFAULT_TAG = {'beta': fashionista_version.FASHIONISTA_BETA_VERSION}

ELEMENT_RUNE = 4081
RESISTANCE_RUNE = 4082
POWER_RUNE = 4083
RUNE_ACTIONS = (ELEMENT_RUNE, RESISTANCE_RUNE, POWER_RUNE)

ITEM_TYPES = FORGEABLE_TYPES + ('Weapon',)

ROUNDING = 'floor'
UNVERIFIED = ['rounding', 'power_takes_neutral']
UNVERIFIED_SOURCE = 'devblog 1772495'

STAT_BY_ELEMENT = {
    code: stat
    for code, token in ELEMENT_ID_TO_TOKEN.items()
    for stat, damage in ELEMENT_PAIRS if damage == token.lower() + 'dam'}


def _items(folder):
    """{item id: ([effect records], name id)} for the Unity export of items.json."""
    data = _load_json(Path(folder) / 'items.json')
    refs = {ref['rid']: ref for ref in data['references']['RefIds']}
    keys = data['objectsById']['m_keys']['Array']
    values = data['objectsById']['m_values']['Array']
    items = {}
    for key, value in zip(keys, values):
        ref = refs.get(value.get('rid'))
        if ref is None:
            continue
        effects = [
            refs[effect['rid']]['data']
            for effect in _unwrap_array(ref['data'].get('possibleEffects'))
            if effect.get('rid') in refs]
        items[int(key)] = (effects, ref['data'].get('nameId'))
    return items


def _translations(folder):
    """{lang: {text id: text}} for the languages whose file the dump has."""
    languages = [lang for lang in LANGUAGES
                 if (Path(folder) / ('%s.json' % lang)).exists()]
    return _load_translations(Path(folder), languages)


def _names(name_id, translations):
    names = {lang: texts[str(name_id)] for lang, texts in translations.items()
             if name_id is not None and texts.get(str(name_id))}
    return dict(sorted(names.items()))


def _rune(item_id, effects):
    """The rune an item is, or None. A rune the data cannot describe is
    skipped with a warning."""
    by_action = {effect.get('actionId', effect.get('effectId')): effect
                 for effect in effects}
    if ELEMENT_RUNE in by_action:
        code = by_action[ELEMENT_RUNE].get('diceSide')
        target = STAT_BY_ELEMENT.get(code)
        if target is None:
            print('warning: rune %s has unknown element code %s, skipped'
                  % (item_id, code))
            return None
        return {'item_id': item_id, 'kind': 'element', 'target': target}
    if RESISTANCE_RUNE in by_action:
        return {'item_id': item_id, 'kind': 'resistance'}
    if POWER_RUNE in by_action:
        value = by_action[POWER_RUNE].get('value')
        if not value:
            print('warning: rune %s has no keep rate in its power effect, '
                  'skipped' % item_id)
            return None
        return {'item_id': item_id, 'kind': 'power', 'keep': value / 100}
    return None


def read_runes(folder):
    translations = _translations(folder)
    runes = []
    for item_id, (effects, name_id) in sorted(_items(folder).items()):
        rune = _rune(item_id, effects)
        if rune is None:
            continue
        names = _names(name_id, translations)
        if names:
            rune['names'] = names
        runes.append(rune)
    return runes


def build(folder, tag):
    runes = read_runes(folder)
    if not runes:
        return None
    return {'source_tag': tag, 'runes': runes, 'item_types': list(ITEM_TYPES),
            'rounding': ROUNDING, 'power_takes_neutral': False,
            'unverified': UNVERIFIED, 'unverified_source': UNVERIFIED_SOURCE}


def _is_rune_table(path):
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    return (isinstance(data, dict) and isinstance(data.get('runes'), list)
            and 'unverified_source' in data)


def write(folder, tag, version, output_folder=None):
    """The path written, or None when the dump has no rune."""
    if version in ('', '.', '..') or os.path.basename(version) != version:
        raise ValueError('not a version name: %r' % version)
    table = build(folder, tag)
    output_folder = output_folder or DEFAULT_FOLDER
    path = os.path.join(output_folder, '%s.json' % version)
    if table is None:
        if not os.path.exists(path):
            return None
        if _is_rune_table(path):
            os.remove(path)
            print('warning: no dracorune in %s, removed the stale %s'
                  % (folder, path))
        else:
            print('warning: no dracorune in %s, kept %s, which is not a '
                  'dracorune table' % (folder, path))
        return None
    os.makedirs(output_folder, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=output_folder, prefix='.%s.' % version, suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as handle:
            json.dump(table, handle, indent=1)
            handle.write('\n')
        replace_file(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('raw_dir', nargs='?',
                        help='datacenter dump to read, default itemscraper/raw/<tag>')
    parser.add_argument('--game-version', default='beta', choices=sorted(DEFAULT_TAG))
    parser.add_argument('--tag', help='default the version\'s current tag')
    parser.add_argument('--output-folder')
    args = parser.parse_args()

    folder = args.raw_dir or os.path.join(
        CURRENT_DIRECTORY, 'raw', args.tag or DEFAULT_TAG[args.game_version])
    name = os.path.basename(os.path.normpath(folder))
    tag = args.tag or (name[4:] if name.startswith('raw_') else name)
    path = write(folder, tag, args.game_version, args.output_folder)
    if path is None:
        print('no dracorune in %s, nothing written' % folder)
    else:
        print('wrote %s' % path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
