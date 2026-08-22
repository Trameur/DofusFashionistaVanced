#!/usr/bin/env python
# coding=utf-8

"""Populate recipe data for Dofus Touch.

The Touch data backend ships recipes in its own Recipes table, downloaded by
download_touch_data.py to touch_raw/Recipes_fr.json:

    {<recipe_id>: {"resultId": <crafted ankama id>,
                   "ingredientIds": [...], "quantities": [...], ...}}

Ingredient names come from the Items tables (touch_raw/Items_<lang>.json, keyed
by ankama id, field "nameId"), pulled per language. This fills the item_recipes /
item_recipe_ingredient_names tables in items_touch.db and re-dumps it, the same
way store_item_obtainment.py does for the other versions, so the encyclopedia and
recipe_util work for Touch unchanged.
"""

import argparse
import json
import os
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

from untranslated_tag import clean_description  # noqa: E402  (sys.path set above)
from store_item_obtainment import (  # noqa: E402  (sys.path set above)
    get_items_db_path, _ensure_tables, _open_items_db, _save_db_to_dump,
    _resolve_item_id, _table_exists)

GAME_VERSION = 'touch'
LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']
RAW_DIR = os.path.join(CURRENT_DIRECTORY, 'touch_raw')


def _load_table(name, lang):
    path = os.path.join(RAW_DIR, '%s_%s.json' % (name, lang))
    with open(path, encoding='utf-8') as in_file:
        return json.load(in_file)


def _load_recipes():
    """crafted ankama id -> [(quantity, ingredient ankama id), ...]."""
    recipes = {}
    for record in _load_table('Recipes', 'fr').values():
        if not isinstance(record, dict):
            continue
        result_id = record.get('resultId')
        ingredient_ids = record.get('ingredientIds') or []
        quantities = record.get('quantities') or []
        if not result_id or not ingredient_ids:
            continue
        pairs = [(int(q), int(i)) for i, q in zip(ingredient_ids, quantities)]
        if pairs:
            recipes[int(result_id)] = pairs
    return recipes


def _load_ingredient_names():
    """ankama id -> {lang: name}, from every language's Items table."""
    names = {}
    for lang in LANGUAGES:
        path = os.path.join(RAW_DIR, 'Items_%s.json' % lang)
        if not os.path.exists(path):
            continue
        for ankama_id, record in _load_table('Items', lang).items():
            if not isinstance(record, dict):
                continue
            name = record.get('nameId')
            if name:
                names.setdefault(int(ankama_id), {})[lang] = name
    return names


def _equipment_ankama_ids(cursor):
    cursor.execute("SELECT ankama_id FROM items WHERE ankama_type = 'equipment'")
    return set(row[0] for row in cursor.fetchall())


def _load_descriptions():
    """ankama id -> {lang: description}, from each language's Items table."""
    descs = {}
    for lang in LANGUAGES:
        path = os.path.join(RAW_DIR, 'Items_%s.json' % lang)
        if not os.path.exists(path):
            continue
        for ankama_id, record in _load_table('Items', lang).items():
            if isinstance(record, dict) and record.get('descriptionId'):
                descs.setdefault(int(ankama_id), {})[lang] = record['descriptionId']
    return descs


def _store_descriptions(cursor):
    """Fill item_descriptions (localized) and item_extra_info.pods (item weight)
    from the items' descriptionId / realWeight."""
    descriptions = _load_descriptions()
    weights = {int(k): v.get('realWeight')
               for k, v in _load_table('Items', 'fr').items()
               if isinstance(v, dict) and v.get('realWeight') is not None}
    cursor.execute("SELECT id, ankama_id FROM items WHERE ankama_type = 'equipment'")
    rows = cursor.fetchall()
    stored = 0
    for item_id, ankama_id in rows:
        for lang, desc in (descriptions.get(ankama_id) or {}).items():
            cursor.execute(
                "INSERT OR REPLACE INTO item_descriptions(item, language, description) "
                "VALUES (?, ?, ?)", (item_id, lang, clean_description(desc)))
            stored += 1
        if ankama_id in weights:
            cursor.execute("INSERT OR REPLACE INTO item_extra_info(item, pods) VALUES (?, ?)",
                           (item_id, weights[ankama_id]))
    return stored


def main():
    recipes = _load_recipes()
    print('Loaded %d touch recipes.' % len(recipes))
    ingredient_names = _load_ingredient_names()

    conn = _open_items_db(GAME_VERSION)
    cursor = conn.cursor()
    _ensure_tables(cursor)
    if not _table_exists(cursor, 'items'):
        raise RuntimeError('items table does not exist in %s' % get_items_db_path(GAME_VERSION))

    equipment_ids = _equipment_ankama_ids(cursor)

    stored = 0
    missing_item = 0
    for crafted_ankama_id, pairs in recipes.items():
        item_id = _resolve_item_id(cursor, crafted_ankama_id, 'equipment')
        if item_id is None:
            missing_item += 1
            continue

        cursor.execute("DELETE FROM item_recipes WHERE item = ?", (item_id,))
        for position, (quantity, ingredient_ankama_id) in enumerate(pairs):
            # Equipment ingredients get a detail page; everything else is a resource.
            subtype = 'equipment' if ingredient_ankama_id in equipment_ids else 'resources'
            cursor.execute(
                """
                INSERT OR REPLACE INTO item_recipes(
                    item, position, ingredient_ankama_id, ingredient_subtype, quantity
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (item_id, position, ingredient_ankama_id, subtype, quantity),
            )
            localized = ingredient_names.get(ingredient_ankama_id, {})
            for lang in LANGUAGES:
                name = localized.get(lang) or localized.get('fr') or localized.get('en')
                if not name:
                    continue
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO item_recipe_ingredient_names(
                        ingredient_ankama_id, ingredient_subtype, language, name
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (ingredient_ankama_id, subtype, lang, name),
                )
        stored += 1

    desc_stored = _store_descriptions(cursor)

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    print('[touch] Stored recipes for %d items (%d recipes had no hosted item); '
          '%d item descriptions.' % (stored, missing_item, desc_stored))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
