#!/usr/bin/env python
# coding=utf-8

"""store_retro_set_names.py: localize Dofus Retro set names.

The retro builder only ingested French set names, so `sets.name` and the
`set_names` table in items_retro.db are French-only. Because structure.py sets
`localized_names['en'] = sets.name`, English (and ES/PT/DE) all fall back to the
French name (e.g. "Panoplie Ventouse" instead of "Sucker Set").

Set names live in the Ankama `itemsets` lang file (global `IS`, keyed by set
ankama id, field `n` = name), per language. This script pulls itemsets for every
language, sets the canonical `sets.name` to the English name and fills
`set_names` with all languages, then re-dumps items_retro.db, mirroring how the
other versions localize set names.
"""

import json
import os
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

from store_item_obtainment import (  # noqa: E402  (sys.path set above)
    get_items_db_path, _open_items_db, _save_db_to_dump, _table_exists)
from download_retro_langs import fetch_manifest, download_swf  # noqa: E402

GAME_VERSION = 'retro'
LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']
RAW_DIR = os.path.join(CURRENT_DIRECTORY, 'retro_raw')


def _ensure_itemsets(lang):
    """Return {set_ankama_id(str): name} for a language, downloading if absent."""
    path = os.path.join(RAW_DIR, 'itemsets_%s.json' % lang)
    if not os.path.exists(path):
        versions = fetch_manifest(lang)
        version = versions.get('itemsets')
        if version is None:
            raise RuntimeError('Retro manifest has no "itemsets" for %s' % lang)
        print('  downloading itemsets_%s_%s.swf ...' % (lang, version))
        download_swf('itemsets', lang, version, __import__('pathlib').Path(RAW_DIR))
    with open(path, encoding='utf-8') as in_file:
        item_sets = (json.load(in_file).get('IS')) or {}
    names = {}
    for sid, data in item_sets.items():
        if isinstance(data, dict) and data.get('n'):
            names[str(sid)] = data['n']
    return names


def main():
    names_by_lang = {lang: _ensure_itemsets(lang) for lang in LANGUAGES}

    conn = _open_items_db(GAME_VERSION)
    cursor = conn.cursor()
    if not _table_exists(cursor, 'sets') or not _table_exists(cursor, 'set_names'):
        raise RuntimeError('sets / set_names tables missing in %s' % get_items_db_path(GAME_VERSION))

    cursor.execute("SELECT id, ankama_id, name FROM sets")
    rows = cursor.fetchall()

    renamed = 0
    localized = 0
    for set_id, ankama_id, current_name in rows:
        sid = str(ankama_id)
        english = names_by_lang['en'].get(sid)
        if english and english != current_name:
            cursor.execute("UPDATE sets SET name = ? WHERE id = ?", (english, set_id))
            renamed += 1

        cursor.execute("DELETE FROM set_names WHERE item_set = ?", (set_id,))
        for lang in LANGUAGES:
            name = names_by_lang[lang].get(sid)
            if name:
                cursor.execute(
                    "INSERT INTO set_names(item_set, language, name) VALUES (?, ?, ?)",
                    (set_id, lang, name))
                localized += 1

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    print('[retro] Renamed %d sets to English, wrote %d localized set-name rows for %d sets.'
          % (renamed, localized, len(rows)))


if __name__ == '__main__':
    main()
