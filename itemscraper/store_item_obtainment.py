#!/usr/bin/env python
# coding=utf-8

import json
import os
import sqlite3
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from fashionistapulp.fashionista_config import (
    get_items_db_path,
    load_items_db_from_dump,
    save_items_db_to_dump,
)

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']

# Categories that provide names used by recipe ingredients.
NAME_SOURCE_CATEGORIES = [
    'equipment',
    'resources',
    'consumables',
    'quest_items',
    'cosmetics',
    'mounts',
]


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


def _resolve_item_id(cursor, ankama_id, ankama_type):
    cursor.execute(
        "SELECT id FROM items WHERE ankama_id = ? AND ankama_type = ? ORDER BY dofustouch ASC LIMIT 1",
        (ankama_id, ankama_type),
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0]

    # Backward compatibility for older rows that do not have ankama_type populated.
    cursor.execute(
        "SELECT id FROM items WHERE ankama_id = ? ORDER BY dofustouch ASC LIMIT 1",
        (ankama_id,),
    )
    row = cursor.fetchone()
    return row[0] if row is not None else None


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
            (item_id, language, description),
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


def main(base_dir='itemscraper'):
    base_dir = os.path.abspath(base_dir)
    equipment_payloads = {}
    for lang in LANGUAGES:
        equipment_path = os.path.join(base_dir, 'all_equipment_%s.json' % lang)
        equipment_payloads[lang] = _extract_entries(_load_json(equipment_path))

    ingredient_name_map = _load_name_maps(base_dir)

    load_items_db_from_dump()
    conn = sqlite3.connect(get_items_db_path())
    cursor = conn.cursor()
    _ensure_tables(cursor)

    if not _table_exists(cursor, 'items'):
        raise RuntimeError('items table does not exist in items.db')

    upserts = 0
    missing = 0
    for lang in LANGUAGES:
        for entry in equipment_payloads[lang]:
            ankama_id = entry.get('ankama_id')
            if ankama_id is None:
                continue
            item_id = _resolve_item_id(cursor, int(ankama_id), 'equipment')
            if item_id is None:
                missing += 1
                continue
            _store_item_data(cursor, item_id, lang, entry, ingredient_name_map)
            upserts += 1

    conn.commit()
    conn.close()
    save_items_db_to_dump()
    print('Stored item extra info for %d localized item rows (%d missing item ids).' % (upserts, missing))


if __name__ == '__main__':
    main()