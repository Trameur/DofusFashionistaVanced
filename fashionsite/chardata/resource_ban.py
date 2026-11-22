# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Forbids every item whose recipe, directly or through crafted equipment, uses a banned resource."""

import re
import sqlite3

from chardata.char_blobs import read_char_blob
from chardata.recipe_util import _LOCAL_INGREDIENT_TYPES, MAX_SUBRECIPE_DEPTH
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_current_game_version, get_structure

OPTION_KEY = 'banned_resources'
MAX_BANNED_RESOURCES = 50

_KEY_PATTERN = re.compile(r'^\d{1,9}:[a-z]+$')

_resource_map_cache = {}


def _table_exists(cursor, name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
    return cursor.fetchone() is not None


def _read_recipes(game_version):
    """(rows of each item id, item ids by (ankama_id, ankama_type))."""
    rows_by_item = {}
    owners = {}
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        cursor = conn.cursor()
        if not _table_exists(cursor, 'item_recipes'):
            return rows_by_item, owners
        for item_id, ankama_id, ankama_type in cursor.execute(
                "SELECT id, ankama_id, ankama_type FROM items "
                "WHERE ankama_id IS NOT NULL"):
            owners.setdefault((ankama_id, ankama_type), []).append(item_id)
        for item_id, ankama_id, subtype in cursor.execute(
                "SELECT item, ingredient_ankama_id, ingredient_subtype "
                "FROM item_recipes ORDER BY item, position"):
            rows_by_item.setdefault(item_id, []).append((ankama_id, subtype))
    finally:
        conn.close()
    return rows_by_item, owners


def _sub_owners(owners, ankama_id, subtype):
    local_type = _LOCAL_INGREDIENT_TYPES.get(subtype.lower())
    found = []
    for ankama_type in {subtype.lower(), local_type}:
        found.extend(owners.get((ankama_id, ankama_type), ()))
    return found


def _resources_of(item_id, rows_by_item, owners):
    resources = set()
    visited = {item_id}
    frontier = [item_id]
    for _depth in range(MAX_SUBRECIPE_DEPTH + 1):
        following = []
        for current in frontier:
            for ankama_id, subtype in rows_by_item.get(current, ()):
                if subtype is None:
                    continue
                if subtype.lower() not in _LOCAL_INGREDIENT_TYPES:
                    resources.add('%d:%s' % (ankama_id, subtype))
                    continue
                for owner in _sub_owners(owners, ankama_id, subtype):
                    if owner not in visited:
                        visited.add(owner)
                        following.append(owner)
        if not following:
            break
        frontier = following
    return resources


def _items_by_resource(game_version=None):
    """{'ankama_id:subtype': frozenset of item ids}, built once per process and version."""
    if game_version is None:
        game_version = get_current_game_version()
    cached = _resource_map_cache.get(game_version)
    if cached is not None:
        return cached
    rows_by_item, owners = _read_recipes(game_version)
    items = {}
    for item_id in rows_by_item:
        for key in _resources_of(item_id, rows_by_item, owners):
            items.setdefault(key, set()).add(item_id)
    result = {key: frozenset(item_ids) for key, item_ids in items.items()}
    _resource_map_cache[game_version] = result
    return result


def banned_resource_keys(char):
    """The well-formed banned keys the build's version knows, sorted; an unreadable value is no ban."""
    options = read_char_blob(char.options, {}, 'options', char)
    if not isinstance(options, dict):
        return []
    stored = options.get(OPTION_KEY)
    if not isinstance(stored, (list, tuple)):
        return []
    known = _items_by_resource(getattr(char, 'game_version', None) or None)
    keys = {key for key in stored
            if isinstance(key, str) and _KEY_PATTERN.match(key) and key in known}
    return sorted(keys)[:MAX_BANNED_RESOURCES]


def _spared_closure(structure, item_ids):
    """The ids with their OR family and their same-item rows, until nothing more joins."""
    families = [{item.id for item in group}
                for group in structure.get_available_or_items().values()]
    rows = set(item_ids)
    while True:
        grown = set(rows)
        for family in families:
            if not family.isdisjoint(grown):
                grown.update(family)
        for item_id in tuple(grown):
            grown.update(structure.get_rows_of_the_same_item(item_id))
        if grown == rows:
            return rows
        rows = grown


def _owned_item_ids(char, structure):
    from chardata.inventory_solver import get_inventory_solver_settings
    mode, folder = get_inventory_solver_settings(char)
    if mode not in ('mixed', 'only') or folder is None:
        return set()
    from chardata.models import InventoryItem
    return {structure.current_item_id(item_id) for item_id
            in InventoryItem.objects.filter(folder=folder)
            .values_list('item_id', flat=True)}


def items_the_ban_forbids(char, structure, locked_ids=()):
    """The item ids to forbid for the build's banned resources, less the locked and owned pieces."""
    keys = banned_resource_keys(char)
    if not keys:
        return set()
    by_resource = _items_by_resource(structure.game_version)
    forbidden = set()
    for key in keys:
        forbidden.update(by_resource.get(key, ()))
    forbidden = {item_id for item_id in forbidden
                 if getattr(structure.get_item_by_id(item_id), 'id', None) == item_id}
    spared = set()
    for item_id in locked_ids:
        try:
            spared.add(structure.current_item_id(int(item_id)))
        except (TypeError, ValueError):
            continue
    spared |= _owned_item_ids(char, structure)
    return forbidden - _spared_closure(structure, spared)
