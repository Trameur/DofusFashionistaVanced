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
from chardata.encyclopedia_view import (_INGREDIENT_ICON_DIRS, _ingredient_icon_ids,
                                        _ingredient_icon_url, _resource_names_by_key)
from chardata.lock_forbid import get_inclusions_dict
from chardata.options import set_setup_choices
from chardata.recipe_util import _LOCAL_INGREDIENT_TYPES, MAX_SUBRECIPE_DEPTH
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import fits_the_level, get_current_game_version, get_structure
from static_s3.templatetags.static_s3 import static

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


def is_resource_key(key):
    """Whether the value is a well-formed 'ankama_id:subtype' key."""
    return isinstance(key, str) and _KEY_PATTERN.fullmatch(key) is not None


def known_keys(keys, game_version=None):
    """The keys, in order, that a recipe of the version uses."""
    known = _items_by_resource(game_version)
    return [key for key in keys if key in known]


def _stored_keys(char):
    """The well-formed keys the build stores, whether its version knows them or not."""
    options = read_char_blob(char.options, {}, 'options', char)
    if not isinstance(options, dict):
        return []
    stored = options.get(OPTION_KEY)
    if not isinstance(stored, (list, tuple)):
        return []
    return [key for key in stored if is_resource_key(key)]


def _known_to_the_build(char):
    return _items_by_resource(getattr(char, 'game_version', None) or None)


def banned_resource_keys(char):
    """The well-formed banned keys the build's version knows, sorted; an unreadable value is no ban."""
    known = _known_to_the_build(char)
    keys = {key for key in _stored_keys(char) if key in known}
    return sorted(keys)[:MAX_BANNED_RESOURCES]


def keys_the_version_does_not_know(char):
    """The well-formed stored keys no recipe of the build's version uses, which a page save keeps."""
    known = _known_to_the_build(char)
    return sorted({key for key in _stored_keys(char) if key not in known})


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


def _forbidden_per_resource(char, structure, locked_ids, keys):
    """{key: the item ids that resource forbids}, less the locked and owned pieces."""
    by_resource = _items_by_resource(structure.game_version)
    spared = set()
    for item_id in locked_ids:
        try:
            spared.add(structure.current_item_id(int(item_id)))
        except (TypeError, ValueError):
            continue
    spared |= _owned_item_ids(char, structure)
    spared = _spared_closure(structure, spared)
    return {
        key: {item_id for item_id in by_resource.get(key, ())
              if getattr(structure.get_item_by_id(item_id), 'id', None) == item_id}
        - spared
        for key in keys}


def items_the_ban_forbids(char, structure, locked_ids=()):
    """The item ids to forbid for the build's banned resources, less the locked and owned pieces."""
    keys = banned_resource_keys(char)
    if not keys:
        return set()
    forbidden = set()
    for item_ids in _forbidden_per_resource(char, structure, locked_ids, keys).values():
        forbidden.update(item_ids)
    return forbidden


def set_banned_resource_keys(char, keys, kept=()):
    """Stores the banned keys up to the cap, plus the kept ones, sorted and without repeats; nothing left removes the ban."""
    capped = sorted(set(keys or ()))[:MAX_BANNED_RESOURCES]
    stored = sorted(set(capped) | set(kept))
    return set_setup_choices(char, {OPTION_KEY: stored or None})


def _piece_of(structure, item):
    """What the forbid box counts as one piece: an OR family, or the rows of one item."""
    family = structure.get_available_or_items().get(item.or_name)
    if family is not None and len(family) > 1:
        return ('or', item.or_name)
    rows = structure.get_rows_of_the_same_item(item.id)
    return min(rows) if rows else item.id


def _pieces_at_the_level(structure, item_ids, level):
    pieces = set()
    for item_id in item_ids:
        item = structure.get_item_by_id(item_id)
        if item is not None and fits_the_level(item, level):
            pieces.add(_piece_of(structure, item))
    return pieces


def _label_of(names, language):
    return names.get(language) or names.get('en') or next(iter(names.values()))


_labels_cache = {}


def _resource_labels(game_version, language):
    """{key: name in the language, English when missing, ' (#ankama_id)' added when two share a name}."""
    cached = _labels_cache.get((game_version, language))
    if cached is not None:
        return cached
    known = _items_by_resource(game_version)
    labels = {}
    for (ankama_id, subtype), names in _resource_names_by_key(game_version).items():
        key = '%d:%s' % (ankama_id, subtype)
        if key in known and names:
            labels[key] = _label_of(names, language)
    taken = {}
    for label in labels.values():
        taken[label] = taken.get(label, 0) + 1
    labels = {key: ('%s (#%s)' % (label, key.split(':')[0]) if taken[label] > 1 else label)
              for key, label in labels.items()}
    _labels_cache[(game_version, language)] = labels
    return labels


def _has_icon(game_version, key):
    return (_INGREDIENT_ICON_DIRS.get(game_version) is not None
            and int(key.split(':')[0]) in _ingredient_icon_ids(game_version))


def icon_url_base(game_version):
    """The static folder of the version's resource icons, each named '<ankama id>-60-60.png', None when it has none."""
    subdir = _INGREDIENT_ICON_DIRS.get(game_version)
    return None if subdir is None else static('chardata/resources/%s60x60/' % subdir)


def picker_index(game_version, language):
    """{label: [key, items it forbids at any level, has an icon]} for every resource a recipe uses."""
    known = _items_by_resource(game_version)
    return {label: [key, len(known[key]), _has_icon(game_version, key)]
            for key, label in _resource_labels(game_version, language).items()}


def ban_state(char, structure, language, locked_ids=None):
    """(rows {key, name, count, image_url} of the banned resources by name, distinct pieces they forbid at the build's level)."""
    keys = banned_resource_keys(char)
    if not keys:
        return [], 0
    if locked_ids is None:
        locked_ids = get_inclusions_dict(char).values()
    game_version = structure.game_version
    labels = _resource_labels(game_version, language)
    per_resource = _forbidden_per_resource(char, structure, locked_ids, keys)
    rows, everything = [], set()
    for key in keys:
        pieces = _pieces_at_the_level(structure, per_resource[key], char.level)
        everything |= pieces
        rows.append({
            'key': key,
            'name': labels.get(key, key),
            'count': len(pieces),
            'image_url': (_ingredient_icon_url(game_version, int(key.split(':')[0]))
                          if _has_icon(game_version, key) else None)})
    rows.sort(key=lambda row: (row['name'].casefold(), row['key']))
    return rows, len(everything)
