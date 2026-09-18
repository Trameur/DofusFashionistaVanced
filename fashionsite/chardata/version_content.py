# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Tell whether a version's item page repeats the Dofus 3 one, by its data."""

import hashlib
import sqlite3
import time

from fashionistapulp.fashionista_config import get_items_db_path

_TTL = 6 * 3600

_CACHE = {}


def _table_exists(cursor, name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,))
    return cursor.fetchone() is not None


def _signatures(version):
    """(ankama_type, ankama_id) -> digest of everything the page shows."""
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        cursor = conn.cursor()

        stats = {}
        if _table_exists(cursor, 'stats_of_item'):
            for item_id, stat, value, low, high in cursor.execute(
                    'SELECT item, stat, value, min_value, max_value '
                    'FROM stats_of_item ORDER BY item, stat'):
                stats.setdefault(item_id, []).append((stat, value, low, high))

        recipes = {}
        if _table_exists(cursor, 'item_recipes'):
            for item_id, position, ingredient, subtype, quantity in cursor.execute(
                    'SELECT item, position, ingredient_ankama_id, '
                    'ingredient_subtype, quantity FROM item_recipes '
                    'ORDER BY item, position'):
                recipes.setdefault(item_id, []).append(
                    (position, ingredient, subtype, quantity))

        bonuses = {}
        if _table_exists(cursor, 'set_bonus'):
            for set_id, pieces, stat, value in cursor.execute(
                    'SELECT item_set, num_pieces_used, stat, value '
                    'FROM set_bonus ORDER BY item_set, num_pieces_used, stat'):
                bonuses.setdefault(set_id, []).append((pieces, stat, value))

        type_names = {}
        if _table_exists(cursor, 'item_types'):
            type_names = dict(cursor.execute('SELECT id, name FROM item_types'))

        signatures = {}
        # Pets and mounts share one ankama id across stat variants
        ambiguous = set()
        for item_id, ankama_type, ankama_id, level, kind, item_set, name in cursor.execute(
                'SELECT id, ankama_type, ankama_id, level, type, item_set, name '
                'FROM items WHERE ankama_id IS NOT NULL '
                'AND COALESCE(removed, 0) = 0'):
            payload = repr((level, kind, item_set,
                            stats.get(item_id, []),
                            recipes.get(item_id, []),
                            bonuses.get(item_set, [])))
            key = (ankama_type, ankama_id)
            if key in signatures:
                ambiguous.add(key)
            signatures[key] = (
                hashlib.sha1(payload.encode('utf-8')).hexdigest(),
                name,
                type_names.get(kind, ''),
            )
        for key in ambiguous:
            del signatures[key]
        return signatures
    finally:
        conn.close()


def _cached_signatures(version):
    entry = _CACHE.get(version)
    now = time.time()
    if entry is not None and now - entry[0] < _TTL:
        return entry[1]
    try:
        signatures = _signatures(version)
    except Exception:
        # Unreadable catalogue: the page stays canonical
        signatures = {}
    _CACHE[version] = (now, signatures)
    return signatures


def repeats_the_live_version(game_version, ankama_type, ankama_id):
    """True when the page repeats the Dofus 3 one, picture included. False if unsure."""
    if not game_version or game_version == 'dofus3':
        return False

    key = (ankama_type, ankama_id)
    live = _cached_signatures('dofus3').get(key)
    mine = _cached_signatures(game_version).get(key)
    if live is None or mine is None:
        return False

    live_digest, live_name, live_type = live
    digest, name, type_name = mine
    if digest != live_digest or name != live_name:
        return False

    from chardata.image_store import get_image_url
    return (get_image_url(type_name, name, game_version)
            == get_image_url(live_type, live_name, 'dofus3'))
