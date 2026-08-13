#!/usr/bin/env python
# coding=utf-8

"""store_retro_descriptions.py: fill item_descriptions for Dofus Retro.

Retro ships its text in Ankama "lang" files, on each item record:

    I['u'][<ankama_id>]['d'] = "Cette amulette augmente l'intelligence ..."

The other versions get theirs from the dofusdu.de all_*.json files, through
store_item_obtainment.py.
"""

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

from store_item_obtainment import (  # noqa: E402  (sys.path set above)
    get_items_db_path, _ensure_tables, _open_items_db, _save_db_to_dump,
    _resolve_item_ids)

GAME_VERSION = 'retro'
LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']
RAW_DIR = os.path.join(CURRENT_DIRECTORY, 'retro_raw')

# Most weapons carry "#1" instead of a description: the client builds their text
# from the effects. "---" and "..." are the same thing written by hand.
PLACEHOLDER = re.compile(r'^[\s#\d.\-]*$')


def _items_for(lang):
    path = os.path.join(RAW_DIR, 'items_%s.json' % lang)
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as in_file:
        return json.load(in_file)['I']['u']


def main():
    conn = _open_items_db(GAME_VERSION)
    cursor = conn.cursor()
    _ensure_tables(cursor)

    # Resolve once: the same ankama id is written in up to five languages.
    known = {}
    for ankama_id, in conn.execute(
            'SELECT ankama_id FROM items WHERE ankama_id IS NOT NULL'):
        known[str(ankama_id)] = _resolve_item_ids(cursor, ankama_id, 'equipment')

    cursor.execute('DELETE FROM item_descriptions')

    stored = 0
    per_lang = {}
    for lang in LANGUAGES:
        count = 0
        for raw_id, entry in _items_for(lang).items():
            if not isinstance(entry, dict):
                continue
            description = (entry.get('d') or '').strip()
            item_ids = known.get(raw_id)
            if not description or not item_ids or PLACEHOLDER.match(description):
                continue
            # A fed pet is a row of its own, "Bow Meow (+80 Vitality)": same
            # creature, same description.
            for item_id in item_ids:
                cursor.execute(
                    'INSERT OR REPLACE INTO item_descriptions(item, language, description)'
                    ' VALUES (?, ?, ?)', (item_id, lang, description))
                count += 1
        per_lang[lang] = count
        stored += count

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    print('[retro] item_descriptions: %d rows (%s)'
          % (stored, ', '.join('%s %d' % (l, per_lang[l]) for l in LANGUAGES)))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
