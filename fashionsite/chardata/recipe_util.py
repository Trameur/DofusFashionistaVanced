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

from chardata.encyclopedia_view import _ingredient_icon_url, _recipe_lookups
from chardata.item_sources import get_source_ankama_ids
from chardata.official_site import get_item_link, get_resource_link
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

logger = logging.getLogger(__name__)

# Ingredient subtypes we host a detail page for, so the ingredient can link back.
_LOCAL_INGREDIENT_TYPES = {
    'equipment': 'equipment',
    'mounts': 'mount',
    'mount': 'mount',
    'pets': 'pet',
    'pet': 'pet',
}

# How many levels deep a "Craftable" tag can keep opening its own sub-recipe.
MAX_SUBRECIPE_DEPTH = 8
MAX_SUBRECIPE_KEYS_PER_REQUEST = 40


def _stock_key(ankama_id, subtype):
    return '%d:%s' % (ankama_id, subtype)


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


def workshop_breakdown(item_quantities, language, game_version='dofus3',
                       unknown_label='Unknown ingredient'):
    """Per-item recipe rows plus per-resource totals, for the workshop cards.

    `item_quantities` is an iterable of `(item_id, count)` pairs, where `item_id`
    is a `WorkshopItem.item_id` (a structure item id, possibly a retired one:
    every id is resolved through `Structure.current_item_id` before it is
    looked up). The returned dict has:

      items               {item_id: [row, ...]}, one entry per input item_id
                          (its own, unresolved key), 'row' quantities are per
                          one unit of the item; callers multiply by their own
                          count client-side
      resources           sorted list of {name, quantity, subtype, ankama_id,
                          local_item_url, resource_url, image_url, used_by},
                          quantity and used_by summed across every item_id
      items_with_recipe   how many distinct input items had a known recipe
      recipes_available   False when the recipe tables are missing from the DB

    Each ingredient row is {name, quantity, subtype, ankama_id, local_item_url,
    resource_url, image_url}. This runs a constant number of SQL statements,
    regardless of how many items are asked for.
    """
    empty = {'items': {}, 'resources': [], 'items_with_recipe': 0,
             'recipes_available': False}

    entries = [(item_id, count) for item_id, count in item_quantities if count]
    if not entries:
        return {'items': {}, 'resources': [], 'items_with_recipe': 0,
                'recipes_available': True}

    structure = get_structure(game_version)
    resolved_by_item_id = {
        item_id: structure.current_item_id(item_id) for item_id, _count in entries
    }
    resolved_ids = sorted(set(resolved_by_item_id.values()))

    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        existing = {row[0] for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('item_recipes', 'item_recipe_ingredient_names')")}
        if 'item_recipes' not in existing:
            return empty
        has_names = 'item_recipe_ingredient_names' in existing

        holes = ','.join('?' * len(resolved_ids))
        raw_rows = cursor.execute(
            "SELECT item, position, ingredient_ankama_id, ingredient_subtype, "
            "quantity FROM item_recipes WHERE item IN (%s) ORDER BY item, position"
            % holes, resolved_ids).fetchall()

        lookup_rows = [(position, ankama_id, subtype, quantity)
                       for _item, position, ankama_id, subtype, quantity in raw_rows]
        names, local_items = _recipe_lookups(cursor, lookup_rows, language, has_names)
    except Exception:
        logger.exception('Failed to build the workshop breakdown')
        return empty
    finally:
        if conn is not None:
            conn.close()

    rows_by_resolved_id = {}
    for item_id, _position, ankama_id, subtype, quantity in raw_rows:
        rows_by_resolved_id.setdefault(item_id, []).append(
            (ankama_id, subtype, quantity))

    craftable_ids = get_source_ankama_ids(game_version)['craftable']

    def build_row(ankama_id, subtype, quantity):
        name = names.get((ankama_id, subtype)) or '%s #%s' % (unknown_label, ankama_id)
        local_type = _LOCAL_INGREDIENT_TYPES.get((subtype or '').lower())
        local_item = local_items.get((ankama_id, local_type)) if local_type else None
        local_item_url = None
        if local_item is not None:
            local_item_url = get_item_link(
                local_item[1], local_item[0], local_item[3], game_version)
        resource_url = None
        if local_item_url is None and (ankama_id, subtype) in names:
            resource_url = get_resource_link(subtype, ankama_id, name, game_version)
        craftable = ankama_id in craftable_ids
        return {
            'name': name,
            'quantity': quantity,
            'subtype': subtype,
            'ankama_id': ankama_id,
            'local_item_url': local_item_url,
            'resource_url': resource_url,
            'image_url': _ingredient_icon_url(game_version, ankama_id),
            'craftable': craftable,
            'craftable_item_id': (local_item[2]
                                  if craftable and local_item is not None else None),
        }

    items = {}
    totals = {}
    order = []
    items_with_recipe = 0
    for item_id, count in entries:
        resolved_rows = rows_by_resolved_id.get(resolved_by_item_id[item_id], [])
        if resolved_rows:
            items_with_recipe += 1
        seen_keys = set()
        item_rows = []
        for ankama_id, subtype, quantity in resolved_rows:
            row = build_row(ankama_id, subtype, quantity)
            item_rows.append(row)
            key = (ankama_id, subtype)
            entry = totals.get(key)
            if entry is None:
                entry = totals[key] = {
                    'name': row['name'],
                    'quantity': 0,
                    'subtype': subtype,
                    'ankama_id': ankama_id,
                    'local_item_url': row['local_item_url'],
                    'resource_url': row['resource_url'],
                    'image_url': row['image_url'],
                    'craftable': row['craftable'],
                    'craftable_item_id': row['craftable_item_id'],
                    'used_by': 0,
                }
                order.append(key)
            entry['quantity'] += (quantity or 0) * count
            if key not in seen_keys:
                seen_keys.add(key)
                entry['used_by'] += 1
        items[item_id] = item_rows

    resources = sorted((totals[key] for key in order),
                       key=lambda entry: (entry['name'] or '').lower())
    return {
        'items': items,
        'resources': resources,
        'items_with_recipe': items_with_recipe,
        'recipes_available': True,
    }


def expand_subrecipes(keys, game_version, language, unknown_label='Unknown ingredient'):
    """One level of the recipe for each requested craftable ingredient.

    `keys` is an iterable of (ankama_id, subtype) pairs, at most
    MAX_SUBRECIPE_KEYS_PER_REQUEST honoured (duplicates dropped). Returns
    {'<ankama_id>:<subtype>': {'found': bool, 'children': [row, ...]}}, where
    'found' is False when this ankama_id carries no item_recipes row of its
    own (the recipe changed since the tag was drawn, or the key was never
    craftable). Each child row is {name, quantity, subtype, ankama_id,
    local_item_url, resource_url, image_url, craftable, craftable_item_id}.

    Runs a small constant number of SQL statements, independent of how many
    keys are asked for.
    """
    keys = list(dict.fromkeys(
        (int(a), str(s)) for a, s in keys))[:MAX_SUBRECIPE_KEYS_PER_REQUEST]
    result = {_stock_key(a, s): {'found': False, 'children': []} for a, s in keys}
    if not keys:
        return result

    ankama_ids = sorted({a for a, _s in keys})
    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        if not _table_exists(cursor, 'item_recipes'):
            return result
        has_names = _table_exists(cursor, 'item_recipe_ingredient_names')

        placeholders = ','.join('?' * len(ankama_ids))
        # One internal item id per ankama_id: duplicate item rows sharing an
        # ankama_id carry identical recipes (retro, touch), so any one will do.
        owner_rows = cursor.execute(
            "SELECT i.ankama_id, MIN(i.id) FROM items i "
            "JOIN item_recipes r ON r.item = i.id "
            "WHERE i.ankama_id IN (%s) GROUP BY i.ankama_id"
            % placeholders, ankama_ids).fetchall()
        if not owner_rows:
            return result
        ankama_by_item = {item_id: ankama_id for ankama_id, item_id in owner_rows}

        item_placeholders = ','.join('?' * len(ankama_by_item))
        own_rows = cursor.execute(
            "SELECT item, position, ingredient_ankama_id, ingredient_subtype, "
            "quantity FROM item_recipes WHERE item IN (%s) ORDER BY item, position"
            % item_placeholders, list(ankama_by_item)).fetchall()

        lookup_rows = [(position, a, s, q) for _item, position, a, s, q in own_rows]
        names, local_items = _recipe_lookups(cursor, lookup_rows, language, has_names)
    except Exception:
        logger.exception('Failed to expand a sub-recipe')
        return result
    finally:
        if conn is not None:
            conn.close()

    craftable_ids = get_source_ankama_ids(game_version)['craftable']
    rows_by_ankama = {}
    for item_id, _position, a, s, q in own_rows:
        rows_by_ankama.setdefault(ankama_by_item[item_id], []).append((a, s, q))

    for ankama_id, subtype in keys:
        rows = rows_by_ankama.get(ankama_id)
        if not rows:
            continue
        children = []
        for a, s, q in rows:
            name = names.get((a, s)) or '%s #%s' % (unknown_label, a)
            local_type = _LOCAL_INGREDIENT_TYPES.get((s or '').lower())
            local_item = local_items.get((a, local_type)) if local_type else None
            local_item_url = None
            if local_item is not None:
                local_item_url = get_item_link(
                    local_item[1], local_item[0], local_item[3], game_version)
            resource_url = None
            if local_item_url is None and (a, s) in names:
                resource_url = get_resource_link(s, a, name, game_version)
            craftable = a in craftable_ids
            children.append({
                'name': name,
                'quantity': q,
                'subtype': s,
                'ankama_id': a,
                'local_item_url': local_item_url,
                'resource_url': resource_url,
                'image_url': _ingredient_icon_url(game_version, a),
                'craftable': craftable,
                'craftable_item_id': (local_item[2]
                                      if craftable and local_item is not None else None),
            })
        result[_stock_key(ankama_id, subtype)] = {'found': True, 'children': children}

    return result
