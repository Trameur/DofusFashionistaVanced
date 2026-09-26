#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""store_starting_stats.py - the AP, MP and prospecting a character starts
with, as each version's client states them, into
fashionsite/chardata/starting_stats/<version>.json.

    dofus3, beta, dofus2  itemscraper/raw/<build>/fr.json
    touch                 itemscraper/touch_raw/Documents_fr.json
    retro                 itemscraper/retro_raw/kb_fr.json

    python itemscraper/store_starting_stats.py --game-version retro

What no text states stays out of the file and the site uses its own value.
"""
from __future__ import annotations

import argparse
import html
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
from store_spell_reference import CLASS_ID_TO_NAME  # noqa: E402

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'fashionsite', 'chardata',
                          'starting_stats')

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

DEFAULT_TAG = {
    'dofus3': fashionista_version.FASHIONISTA_VERSION,
    'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
    'dofus2': fashionista_version.FASHIONISTA_DOFUS2_VERSION,
}

# The beginner's book is the Dofus 1 text: these servers give Enutrofs 100, not 120
STALE_TEXTS = {'dofus3': {'1080288'}, 'beta': {'1080288'},
               'dofus2': {'1080288'}}

PROSPECTING = re.compile(
    r'(\d+)\s+points\s+de\s+Prospection\s+quand\s+tu\s+débutes'
    r'(?:\s*\((\d+)\s+pour\s+les\s+([^)]+?)\s*\))?')
FIXED = re.compile(r'Fixés\s+à\s+(\d+)\s+(PA|PM)\s+pour\s+tous\s+les\s+combattants')
LEVEL_AP = re.compile(
    r'Au\s+niveau\s+(\d+),\s+votre\s+personnage\s+obtient\s+(\d+)\s+PA\s+'
    r'supplémentaire')

STAT_BY_WORD = {'PA': 'AP', 'PM': 'MP'}

# {{featureDescription,49::PA}} in 3.x, {featureDescription,49::PA} in 2.x
_REFERENCE = re.compile(r'\{\{?[^{}]*?::([^{}]*)\}\}?')
_TAG = re.compile(r'<[^>]*>')


def plain(text):
    return html.unescape(_TAG.sub('', _REFERENCE.sub(r'\1', text or '')))


def _load(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def _modern_dir(version, tag):
    return os.path.join(CURRENT_DIRECTORY, 'raw', tag or DEFAULT_TAG[version])


def source_path(version, tag=None):
    if version == 'touch':
        return os.path.join(CURRENT_DIRECTORY, 'touch_raw', 'Documents_fr.json')
    if version == 'retro':
        return os.path.join(CURRENT_DIRECTORY, 'retro_raw', 'kb_fr.json')
    return os.path.join(_modern_dir(version, tag), 'fr.json')


def texts(version, tag=None):
    """[(source, text)] of every text the version's file holds, bar the stale ones."""
    path = source_path(version, tag)
    data = _load(path)
    name = os.path.basename(path)
    if version == 'touch':
        return [('%s %s' % (name, key), record.get('contentId'))
                for key, record in data.items() if isinstance(record, dict)]
    if version == 'retro':
        return [('%s KBA %s' % (name, key), record.get('a'))
                for key, record in (data.get('KBA') or {}).items()]
    stale = STALE_TEXTS.get(version, set())
    entries = data.get('entries') or data.get('texts') or {}
    return [('%s %s' % (name, key), text) for key, text in entries.items()
            if key not in stale]


def class_names(version, tag=None):
    """{lowercase French class name: site class name}."""
    if version == 'retro':
        path = os.path.join(CURRENT_DIRECTORY, 'retro_raw', 'classes_fr.json')
        named = {int(key): entry.get('sn')
                 for key, entry in _load(path)['G'].items()}
    elif version == 'touch':
        path = os.path.join(CURRENT_DIRECTORY, 'touch_raw', 'Breeds_fr.json')
        named = {int(entry['id']): entry.get('shortNameId')
                 for entry in _load(path).values()}
    else:
        folder = _modern_dir(version, tag)
        data = _load(os.path.join(folder, 'breeds.json'))
        if isinstance(data, dict) and 'references' in data:
            breeds = [ref['data'] for ref in data['references']['RefIds']]
        else:
            breeds = list(data.values()) if isinstance(data, dict) else data
        language = _load(os.path.join(folder, 'fr.json'))
        words = language.get('entries') or language.get('texts') or {}
        named = {int(breed['id']): words.get(str(breed.get('shortNameId')))
                 for breed in breeds}
    return {name.lower(): CLASS_ID_TO_NAME[breed_id]
            for breed_id, name in named.items()
            if name and breed_id in CLASS_ID_TO_NAME}


def _class_of(phrase, names):
    phrase = phrase.strip().lower()
    return names.get(phrase) or (names.get(phrase[:-1])
                                 if phrase.endswith('s') else None)


def extract(version, tag=None):
    """(table, notes): what the version's texts state, and what could not be kept."""
    found = {}
    notes = []
    names = None

    def note(key, value, source):
        found.setdefault(key, {}).setdefault(value, []).append(source)

    for source, raw in texts(version, tag):
        if not raw:
            continue
        text = plain(raw)
        for match in PROSPECTING.finditer(text):
            note(('all', 'Prospecting'), int(match.group(1)), source)
            if match.group(2):
                if names is None:
                    names = class_names(version, tag)
                char_class = _class_of(match.group(3), names)
                if char_class is None:
                    notes.append('%s names "%s", no class of that name'
                                 % (source, match.group(3)))
                    continue
                note(('classes', char_class, 'Prospecting'),
                     int(match.group(2)), source)
        for match in FIXED.finditer(text):
            note(('all', STAT_BY_WORD[match.group(2)]), int(match.group(1)),
                 source)
        for match in LEVEL_AP.finditer(text):
            note(('level_ap',), (int(match.group(1)), int(match.group(2))),
                 source)

    table = {}
    sources = {}
    for key, values in sorted(found.items()):
        if len(values) > 1:
            notes.append('texts disagree on %s: %s' % (
                '/'.join(key), '; '.join('%s in %s' % (value, ', '.join(where))
                                         for value, where in values.items())))
            continue
        (value, where), = values.items()
        if key == ('level_ap',):
            table['level_ap'] = {'level': value[0], 'AP': value[1]}
            sources['level_ap'] = sorted(where)
            continue
        target, origin = table, sources
        for part in key[:-1]:
            target = target.setdefault(part, {})
            origin = origin.setdefault(part, {})
        target[key[-1]] = value
        origin[key[-1]] = sorted(where)
    if sources:
        table['sources'] = sources
    return table, notes


def _values(table, prefix=''):
    out = {}
    for key, value in (table or {}).items():
        if key == 'sources':
            continue
        if isinstance(value, dict) and key != 'level_ap':
            out.update(_values(value, prefix + key + '/'))
        else:
            out[prefix + key] = value
    return out


def output_path(version):
    return os.path.join(OUTPUT_DIR, '%s.json' % version)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', required=True, choices=VERSIONS)
    parser.add_argument('--tag', default=None)
    args = parser.parse_args(argv)
    version = args.game_version

    source = source_path(version, args.tag)
    if not os.path.exists(source):
        print('%s: no %s on this machine, starting stats kept as they were'
              % (version, os.path.relpath(source, PROJECT_ROOT)))
        return 0

    table, notes = extract(version, args.tag)
    path = output_path(version)
    previous = _load(path) if os.path.exists(path) else None
    for line in notes:
        print('warning: %s: %s' % (version, line))
    if previous is not None:
        before, after = _values(previous), _values(table)
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                print('warning: %s %s changed: %s -> %s'
                      % (version, key, before.get(key), after.get(key)))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        json.dump(table, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write('\n')
    read = _values(table)
    print('%s: %s' % (version, ', '.join(
        '%s %s' % (key, value) for key, value in sorted(read.items()))
        or 'no starting stat stated'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
