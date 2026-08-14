#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""store_spell_states.py - the game's own name for every state that gates a
damage row, into fashionsite/chardata/spell_states/<version>.json.

    python itemscraper/store_spell_states.py --game-version dofus3

A spell whose damage depends on a state writes one row per case, and the two
cases print the same table with nothing telling them apart. The target mask
names the state by id; this reads spell_states.json for the id and the lang
files for the name Ankama gives it in each language.

Only the states a damage row actually names are kept, so the file holds a few
hundred entries instead of the six thousand the datacenter ships.

dofus3 and beta only. The 2.73 archive ships no spell_states.json, and Retro
and Touch build no state-gated rows.
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
from store_spell_reference import LANGUAGES, clean_text  # noqa: E402

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'fashionsite', 'chardata',
                          'spell_states')

SOURCE = {
    'dofus3': ('transformed_spells.json',
               fashionista_version.FASHIONISTA_VERSION),
    'beta': ('transformed_spells_beta.json',
             fashionista_version.FASHIONISTA_BETA_VERSION),
}

_STATE_TOKEN = re.compile(r'\*?([eE])(\d+)')


def state_ids_in_use(spells_path):
    """Every state id a damage row of the archive is gated on."""
    with open(spells_path, encoding='utf-8') as handle:
        spells = json.load(handle)
    found = set()
    for spell in spells:
        templates = spell.get('damage_templates') or {}
        for key in ('normal', 'critical'):
            for row in templates.get(key) or []:
                group = row.get('state_group')
                if not group:
                    continue
                for _sign, state_id in _STATE_TOKEN.findall(group):
                    found.add(int(state_id))
    return found


def read_states(tag, wanted):
    """id -> {lang: name}, from the datacenter dump and the lang files."""
    root = os.path.join(CURRENT_DIRECTORY, 'raw', tag)

    def load(name):
        with open(os.path.join(root, name), encoding='utf-8') as handle:
            return json.load(handle)

    name_ids = {}
    for reference in load('spell_states.json')['references']['RefIds']:
        data = reference.get('data') or {}
        try:
            state_id = int(data.get('id'))
        except (TypeError, ValueError):
            continue
        if state_id in wanted and data.get('nameId'):
            name_ids[state_id] = str(data['nameId'])

    texts = {}
    for lang in LANGUAGES:
        texts[lang] = load('%s.json' % lang)['entries']

    states = {}
    for state_id, name_id in name_ids.items():
        names = {}
        for lang in LANGUAGES:
            name = clean_text(texts[lang].get(name_id) or '')
            if name:
                names[lang] = name
        if names.get('en') or names.get('fr'):
            states[str(state_id)] = names
    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=sorted(SOURCE))
    parser.add_argument('--tag', default=None)
    args = parser.parse_args()

    spells_name, default_tag = SOURCE[args.game_version]
    wanted = state_ids_in_use(os.path.join(CURRENT_DIRECTORY, spells_name))
    states = read_states(args.tag or default_tag, wanted)
    if not states:
        raise SystemExit('%s: no state name found' % args.game_version)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, '%s.json' % args.game_version)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        json.dump(states, handle, ensure_ascii=False, indent=1, sort_keys=True)
    missing = len(wanted) - len(states)
    print('%s: %d states named out of %d in use%s'
          % (args.game_version, len(states), len(wanted),
             ', %d unnamed' % missing if missing else ''))


if __name__ == '__main__':
    main()
