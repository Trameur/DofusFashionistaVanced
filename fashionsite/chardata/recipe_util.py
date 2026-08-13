# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Recipe ingredient aggregation.

The recipe tables (`item_recipes`, `item_recipe_ingredient_names`) are written
into the per-version items DB by `itemscraper/store_item_obtainment.py`.
"""

import logging
import sqlite3

from chardata.official_site import get_item_link
from fashionistapulp.fashionista_config import get_items_db_path

logger = logging.getLogger(__name__)

# Ingredient subtypes we host a detail page for, so the ingredient can link back.
_LOCAL_INGREDIENT_TYPES = {
    'equipment': 'equipment',
    'mounts': 'mount',
    'mount': 'mount',
    'pets': 'pet',
    'pet': 'pet',
}


def _table_exists(cursor, name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
    return cursor.fetchone() is not None


def _ingredient_name(cursor, has_names_table, ankama_id, subtype, language):
    if not has_names_table:
        return None
    cursor.execute(
        "SELECT name FROM item_recipe_ingredient_names "
        "WHERE ingredient_ankama_id = ? AND ingredient_subtype = ? AND language = ?",
        (ankama_id, subtype, language))
    row = cursor.fetchone()
    if row is None and language != 'en':
        cursor.execute(
            "SELECT name FROM item_recipe_ingredient_names "
            "WHERE ingredient_ankama_id = ? AND ingredient_subtype = ? AND language = 'en'",
            (ankama_id, subtype))
        row = cursor.fetchone()
    return row[0] if row is not None else None


def _local_item_url(cursor, ankama_id, subtype, game_version):
    local_type = _LOCAL_INGREDIENT_TYPES.get((subtype or '').lower())
    if not local_type:
        return None
    cursor.execute(
        "SELECT ankama_id, ankama_type, name FROM items "
        "WHERE ankama_id = ? AND ankama_type = ? ORDER BY dofustouch ASC LIMIT 1",
        (ankama_id, local_type))
    row = cursor.fetchone()
    if row is None:
        return None
    return get_item_link(row[1], row[0], row[2], game_version)


def aggregate_ingredients(item_quantities, language, game_version='dofus3',
                          unknown_label='Unknown ingredient'):
    """Sum recipe ingredients across several items.

    `item_quantities` is an iterable of `(item_id, count)` pairs, where `item_id`
    is a structure item id and `count` is how many of that item are wanted. The
    returned dict has:

      ingredients        sorted list of {name, quantity, subtype, ankama_id,
                         local_item_url}, quantity summed across all items
      items_with_recipe  how many distinct input items had a known recipe
      recipes_available  False when the recipe tables are missing from the DB
    """
    empty = {'ingredients': [], 'items_with_recipe': 0, 'recipes_available': False}

    totals = {}
    order = []
    items_with_recipe = 0
    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        if not _table_exists(cursor, 'item_recipes'):
            return empty
        has_names = _table_exists(cursor, 'item_recipe_ingredient_names')

        for item_id, count in item_quantities:
            if not count:
                continue
            cursor.execute(
                "SELECT ingredient_ankama_id, ingredient_subtype, quantity "
                "FROM item_recipes WHERE item = ? ORDER BY position ASC", (item_id,))
            rows = cursor.fetchall()
            if rows:
                items_with_recipe += 1
            for ankama_id, subtype, quantity in rows:
                key = (ankama_id, subtype)
                entry = totals.get(key)
                if entry is None:
                    name = (_ingredient_name(cursor, has_names, ankama_id, subtype, language)
                            or '%s #%s' % (unknown_label, ankama_id))
                    entry = totals[key] = {
                        'name': name,
                        'quantity': 0,
                        'subtype': subtype,
                        'ankama_id': ankama_id,
                        'local_item_url': _local_item_url(cursor, ankama_id, subtype, game_version),
                    }
                    order.append(key)
                entry['quantity'] += (quantity or 0) * count
    except Exception:
        logger.exception('Failed to aggregate recipe ingredients')
        return empty
    finally:
        if conn is not None:
            conn.close()

    ingredients = sorted((totals[key] for key in order),
                         key=lambda entry: (entry['name'] or '').lower())
    return {
        'ingredients': ingredients,
        'items_with_recipe': items_with_recipe,
        'recipes_available': True,
    }
