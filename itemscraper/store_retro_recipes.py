#!/usr/bin/env python
# coding=utf-8

"""store_retro_recipes.py: populate recipe data for Dofus Retro.

Unlike the other versions (whose recipes come from the dofusdu.de all_*.json
files), Dofus Retro ships its data as Ankama "lang" SWF files. Recipes live in
the `crafts` lang file as global `CR`:

    CR[<crafted_item_ankama_id>] = [[quantity, ingredient_ankama_id], ...]

Ingredient names come from the `items` lang file (global `I['u']`, keyed by
ankama id, field `n` = name), which we pull per language.

This script downloads (or reuses cached) crafts + items lang data, then fills
the item_recipes / item_recipe_ingredient_names tables in items_retro.db and
re-dumps it, mirroring what store_item_obtainment.py does for the other
versions, so chardata.recipe_util / the encyclopedia work unchanged for retro.
"""

import argparse
import ast
import json
import os
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

from store_item_obtainment import (  # noqa: E402  (sys.path set above)
    get_items_db_path, _ensure_tables, _open_items_db, _save_db_to_dump,
    _resolve_item_id, _table_exists)
from download_retro_langs import fetch_manifest, download_swf  # noqa: E402

GAME_VERSION = 'retro'
LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']
RAW_DIR = os.path.join(CURRENT_DIRECTORY, 'retro_raw')
# crafts (the recipe structure) is language-independent; we only need it once.
CRAFTS_LANG = 'fr'


def _raw_json_path(category, lang):
    return os.path.join(RAW_DIR, '%s_%s.json' % (category, lang))


def _ensure_raw(category, lang):
    """Return parsed lang globals for (category, lang), downloading if absent."""
    path = _raw_json_path(category, lang)
    if not os.path.exists(path):
        versions = fetch_manifest(lang)
        version = versions.get(category)
        if version is None:
            raise RuntimeError('Retro manifest has no "%s" category for %s' % (category, lang))
        print('  downloading %s_%s_%s.swf ...' % (category, lang, version))
        download_swf(category, lang, version, __import__('pathlib').Path(RAW_DIR))
    with open(path, encoding='utf-8') as in_file:
        return json.load(in_file)


def _load_recipes():
    crafts = _ensure_raw('crafts', CRAFTS_LANG)
    cr = crafts.get('CR') or {}
    recipes = {}
    for crafted_id, ingredients in cr.items():
        try:
            parsed = ast.literal_eval(ingredients) if isinstance(ingredients, str) else ingredients
        except (ValueError, SyntaxError):
            continue
        # Normalise to [(quantity, ingredient_ankama_id), ...].
        pairs = []
        for entry in parsed or []:
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                qty, ing = entry
                pairs.append((int(qty), int(ing)))
        if pairs:
            recipes[int(crafted_id)] = pairs
    return recipes


def _load_ingredient_names():
    """ankama_id -> {lang: name}, from each language's items lang file."""
    names = {}
    for lang in LANGUAGES:
        items = _ensure_raw('items', lang)
        records = ((items.get('I') or {}).get('u')) or {}
        for ankama_id, record in records.items():
            if not isinstance(record, dict):
                continue
            name = record.get('n')
            if not name:
                continue
            names.setdefault(int(ankama_id), {})[lang] = name
    return names


def _equipment_ankama_ids(cursor):
    cursor.execute("SELECT ankama_id FROM items WHERE ankama_type = 'equipment'")
    return set(row[0] for row in cursor.fetchall())


def main():
    recipes = _load_recipes()
    print('Loaded %d retro recipes from crafts lang data.' % len(recipes))
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

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    print('[retro] Stored recipes for %d equipment items (%d recipes had no hosted item).'
          % (stored, missing_item))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
