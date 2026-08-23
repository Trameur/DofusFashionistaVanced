#!/usr/bin/env python
# coding=utf-8

import json
import importlib
import os
import sqlite3
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if CURRENT_DIRECTORY not in sys.path:
    sys.path.append(CURRENT_DIRECTORY)

from untranslated_tag import clean_description  # noqa: E402

try:
    fashionista_config = importlib.import_module('fashionistapulp.fashionista_config')
except ModuleNotFoundError:
    fashionista_config = importlib.import_module('fashionistapulp.fashionistapulp.fashionista_config')

# Resolved against the repo holding this script: the global config points at
# one fixed checkout, which breaks worktrees.

try:
    game_versions = importlib.import_module('fashionistapulp.game_versions')
except ModuleNotFoundError:
    game_versions = importlib.import_module(
        'fashionistapulp.fashionistapulp.game_versions')


def _data_file_name(game_version, attribute):
    """The file the registry names for this version.

    These two functions used to read `_DB_FILES` / `_DUMP_FILES` straight out of
    fashionista_config. Those dicts are gone -- the registry replaced them -- so
    every itemscraper step raised AttributeError the moment it resolved a path,
    and item data could no longer be refreshed for any version. Nothing failed
    loudly: the site kept serving the database it already had.

    The paths stay anchored on PROJECT_ROOT rather than delegating to
    fashionista_config, which points at one fixed checkout and would break
    worktrees. Only the file name comes from the registry.
    """
    return getattr(game_versions.get_game_version(game_version), attribute)


def get_items_db_path(game_version='dofus3'):
    return os.path.join(PROJECT_ROOT, 'fashionistapulp', 'fashionistapulp',
                        _data_file_name(game_version, 'db_file'))


def get_items_dump_path(game_version='dofus3'):
    return os.path.join(PROJECT_ROOT, 'fashionistapulp', 'fashionistapulp',
                        _data_file_name(game_version, 'dump_file'))

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']

# Where each game version keeps its scraped all_*.json files, relative to the
# itemscraper directory. dofus3 / touch use the top-level files.
VERSION_DATA_SUBDIR = {
    'beta': 'beta',
    'dofus2': 'dofus2',
}

# Categories that provide names used by recipe ingredients.
NAME_SOURCE_CATEGORIES = [
    'equipment',
    'resources',
    'consumables',
    'quest_items',
    'cosmetics',
    'mounts',
]


def _find_base_dir(base_dir=None, game_version='dofus3'):
    """Resolve the directory containing all_*_<lang>.json files."""
    subdir = VERSION_DATA_SUBDIR.get(game_version)
    candidates = []
    if base_dir:
        candidates.append(os.path.abspath(base_dir))
    roots = [
        CURRENT_DIRECTORY,
        os.getcwd(),
        os.path.join(os.getcwd(), 'itemscraper'),
        os.path.join(PROJECT_ROOT, 'itemscraper'),
    ]
    for root in roots:
        if subdir:
            candidates.append(os.path.join(root, subdir))
        else:
            candidates.append(root)

    expected_file = 'all_equipment_en.json'
    for candidate in candidates:
        if os.path.exists(os.path.join(candidate, expected_file)):
            return candidate

    return os.path.abspath(base_dir) if base_dir else candidates[-1]


def _get_items_dump_path(game_version='dofus3'):
    return get_items_dump_path(game_version)


def _sanitize_dump_sql(sql_script):
    sanitized_lines = []
    for line in sql_script.splitlines():
        if 'sqlite_sequence' in line.lower():
            continue
        sanitized_lines.append(line)
    return '\n'.join(sanitized_lines)


def _load_db_from_dump(items_db_path, game_version='dofus3'):
    dump_path = _get_items_dump_path(game_version)
    if not os.path.exists(dump_path):
        raise RuntimeError('Could not find item DB dump at %s' % dump_path)

    with open(dump_path, 'r', encoding='utf-8') as in_file:
        sql_script = _sanitize_dump_sql(in_file.read())

    if os.path.exists(items_db_path):
        os.remove(items_db_path)

    conn = sqlite3.connect(items_db_path)
    try:
        conn.executescript('PRAGMA foreign_keys = OFF;')
        conn.executescript(sql_script)
        conn.commit()
    finally:
        conn.close()


def _save_db_to_dump(items_db_path, game_version='dofus3'):
    dump_path = _get_items_dump_path(game_version)
    temp_dump_path = dump_path + '.tmp'
    conn = sqlite3.connect(items_db_path)
    try:
        with open(temp_dump_path, 'w', encoding='utf-8') as out_file:
            for statement in conn.iterdump():
                out_file.write(statement)
                out_file.write('\n')
    finally:
        conn.close()

    os.replace(temp_dump_path, dump_path)


def _open_items_db(game_version='dofus3'):
    items_db_path = get_items_db_path(game_version)
    os.makedirs(os.path.dirname(items_db_path), exist_ok=True)

    needs_bootstrap = not os.path.exists(items_db_path)
    if not needs_bootstrap:
        conn = sqlite3.connect(items_db_path)
        try:
            cursor = conn.cursor()
            needs_bootstrap = not _table_exists(cursor, 'items')
        finally:
            conn.close()

    if needs_bootstrap:
        _load_db_from_dump(items_db_path, game_version)

    return sqlite3.connect(items_db_path)


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _ensure_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS item_descriptions (
            item INTEGER,
            language TEXT,
            description TEXT,
            PRIMARY KEY (item, language),
            FOREIGN KEY (item) REFERENCES items(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS item_extra_info (
            item INTEGER PRIMARY KEY,
            pods INTEGER,
            FOREIGN KEY (item) REFERENCES items(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS item_recipes (
            item INTEGER,
            position INTEGER,
            ingredient_ankama_id INTEGER,
            ingredient_subtype TEXT,
            quantity INTEGER,
            PRIMARY KEY (item, position),
            FOREIGN KEY (item) REFERENCES items(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS item_recipe_ingredient_names (
            ingredient_ankama_id INTEGER,
            ingredient_subtype TEXT,
            language TEXT,
            name TEXT,
            PRIMARY KEY (ingredient_ankama_id, ingredient_subtype, language)
        )
        """
    )


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as in_file:
        return json.load(in_file)


def _extract_entries(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if 'items' in payload and isinstance(payload['items'], list):
            return payload['items']
        if 'mounts' in payload and isinstance(payload['mounts'], list):
            return payload['mounts']
        if 'sets' in payload and isinstance(payload['sets'], list):
            return payload['sets']
    return []


def _load_name_maps(base_dir):
    # maps[(subtype, ankama_id)][lang] = name
    maps = {}
    for lang in LANGUAGES:
        for category in NAME_SOURCE_CATEGORIES:
            file_path = os.path.join(base_dir, 'all_%s_%s.json' % (category, lang))
            entries = _extract_entries(_load_json(file_path))
            for entry in entries:
                ankama_id = entry.get('ankama_id')
                name = entry.get('name')
                if ankama_id is None or not name:
                    continue
                key = (category, int(ankama_id))
                maps.setdefault(key, {})[lang] = name
    return maps


def _resolve_item_ids(cursor, ankama_id, ankama_type):
    """Every row that is this item.

    An item gated behind alternative conditions is flattened into one row per
    condition, "(#1)" and "(#2)", sharing its ankama id: they are the same
    piece and read from the same entry.
    """
    cursor.execute(
        "SELECT id FROM items WHERE ankama_id = ? AND ankama_type = ? ORDER BY dofustouch ASC",
        (ankama_id, ankama_type),
    )
    rows = cursor.fetchall()
    if rows:
        return [row[0] for row in rows]

    # Backward compatibility for older rows that do not have ankama_type populated.
    cursor.execute(
        "SELECT id FROM items WHERE ankama_id = ? ORDER BY dofustouch ASC",
        (ankama_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def _resolve_item_id(cursor, ankama_id, ankama_type):
    """The first of those rows."""
    rows = _resolve_item_ids(cursor, ankama_id, ankama_type)
    return rows[0] if rows else None


def _subtype_to_name_source(subtype):
    normalized = (subtype or '').strip().lower()
    mapping = {
        'equipment': 'equipment',
        'resources': 'resources',
        'consumables': 'consumables',
        'quest': 'quest_items',
        'quest_items': 'quest_items',
        'cosmetics': 'cosmetics',
        'mounts': 'mounts',
        'mount': 'mounts',
    }
    return mapping.get(normalized, normalized)


def _store_item_data(cursor, item_id, language, entry, ingredient_name_map):
    description = entry.get('description')
    if description is not None:
        cursor.execute(
            "INSERT OR REPLACE INTO item_descriptions(item, language, description) VALUES (?, ?, ?)",
            (item_id, language, clean_description(description)),
        )

    if language == 'en':
        cursor.execute(
            "INSERT OR REPLACE INTO item_extra_info(item, pods) VALUES (?, ?)",
            (item_id, entry.get('pods')),
        )

    recipe = entry.get('recipe') or []
    if language == 'en':
        cursor.execute("DELETE FROM item_recipes WHERE item = ?", (item_id,))
        for index, ingredient in enumerate(recipe):
            ingredient_id = ingredient.get('item_ankama_id')
            if ingredient_id is None:
                continue
            ingredient_subtype = (ingredient.get('item_subtype') or '').strip().lower()
            quantity = ingredient.get('quantity') or 0
            cursor.execute(
                """
                INSERT OR REPLACE INTO item_recipes(
                    item, position, ingredient_ankama_id, ingredient_subtype, quantity
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (item_id, index, int(ingredient_id), ingredient_subtype, int(quantity)),
            )

    for ingredient in recipe:
        ingredient_id = ingredient.get('item_ankama_id')
        if ingredient_id is None:
            continue
        ingredient_subtype = _subtype_to_name_source(ingredient.get('item_subtype'))
        names = ingredient_name_map.get((ingredient_subtype, int(ingredient_id)))
        if not names:
            continue
        translated_name = names.get(language) or names.get('en')
        if not translated_name:
            continue
        cursor.execute(
            """
            INSERT OR REPLACE INTO item_recipe_ingredient_names(
                ingredient_ankama_id, ingredient_subtype, language, name
            ) VALUES (?, ?, ?, ?)
            """,
            (int(ingredient_id), ingredient_subtype, language, translated_name),
        )


def main(game_version='dofus3', base_dir=None):
    base_dir = _find_base_dir(base_dir, game_version)
    print('Using scraper data directory: %s (version: %s)' % (base_dir, game_version))

    expected_equipment_file = os.path.join(base_dir, 'all_equipment_en.json')
    if not os.path.exists(expected_equipment_file):
        raise RuntimeError(
            'Could not find all_equipment_en.json in %s. Run get_equipments.py first.' % base_dir
        )

    equipment_payloads = {}
    for lang in LANGUAGES:
        equipment_path = os.path.join(base_dir, 'all_equipment_%s.json' % lang)
        equipment_payloads[lang] = _extract_entries(_load_json(equipment_path))

    if not equipment_payloads.get('en'):
        raise RuntimeError('Loaded 0 english equipment entries from %s.' % expected_equipment_file)

    ingredient_name_map = _load_name_maps(base_dir)

    conn = _open_items_db(game_version)
    cursor = conn.cursor()
    _ensure_tables(cursor)

    if not _table_exists(cursor, 'items'):
        raise RuntimeError('items table does not exist in %s' % get_items_db_path(game_version))

    upserts = 0
    missing = 0
    for lang in LANGUAGES:
        for entry in equipment_payloads[lang]:
            ankama_id = entry.get('ankama_id')
            if ankama_id is None:
                continue
            item_ids = _resolve_item_ids(cursor, int(ankama_id), 'equipment')
            if not item_ids:
                missing += 1
                continue
            for item_id in item_ids:
                _store_item_data(cursor, item_id, lang, entry, ingredient_name_map)
            upserts += 1

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(game_version), game_version)
    print('[%s] Stored item extra info for %d localized item rows (%d missing item ids).'
          % (game_version, upserts, missing))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Populate recipe / description / pods tables in a version items DB.')
    parser.add_argument('--game-version', default='dofus3',
                        help='dofus3 (default), touch, beta, dofus2, retro')
    parser.add_argument('base_dir', nargs='?', default=None,
                        help='Override directory containing all_*.json (auto-detected by default).')
    args = parser.parse_args()
    main(args.game_version, args.base_dir)