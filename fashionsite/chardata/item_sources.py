# Copyright (C) 2020 The Dofus Fashionista
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

"""How an item is obtained, straight from the scraped data: does it have a
recipe, and what is its best drop rate. The item picker shows it so a player
can tell a craftable piece from a 0.05% drop before building around it.

Keyed by ankama_id rather than internal id: an item with OR equip conditions is
split into one row per branch and only the first branch carries the recipe and
the drops, so both branches have to answer the same thing.
"""

import sqlite3

from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_current_game_version

__all__ = ['get_acquisition_by_ankama_id', 'get_source_ankama_ids',
           'attach_acquisition']


def _table_exists(cursor, name):
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                   (name,))
    return cursor.fetchone() is not None


def get_acquisition_by_ankama_id(ankama_ids, game_version=None):
    """{ankama_id: {'craftable': bool, 'best_drop_rate': float or None}} for the
    ids that have a known source. Ids with no source at all are left out."""
    ankama_ids = [i for i in set(ankama_ids or []) if i is not None]
    if not ankama_ids:
        return {}
    if game_version is None:
        game_version = get_current_game_version()

    placeholders = ','.join('?' * len(ankama_ids))
    result = {}
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        cursor = conn.cursor()
        if _table_exists(cursor, 'item_recipes'):
            cursor.execute(
                'SELECT DISTINCT i.ankama_id FROM item_recipes r '
                'JOIN items i ON i.id = r.item '
                'WHERE i.ankama_id IN (%s)' % placeholders, ankama_ids)
            for (ankama_id,) in cursor.fetchall():
                result.setdefault(ankama_id, {})['craftable'] = True
        if _table_exists(cursor, 'item_drops'):
            cursor.execute(
                'SELECT i.ankama_id, MAX(d.rate) FROM item_drops d '
                'JOIN items i ON i.id = d.item '
                'WHERE i.ankama_id IN (%s) GROUP BY i.ankama_id' % placeholders,
                ankama_ids)
            for ankama_id, rate in cursor.fetchall():
                if rate:
                    result.setdefault(ankama_id, {})['best_drop_rate'] = rate
    finally:
        conn.close()

    for sources in result.values():
        sources.setdefault('craftable', False)
        sources.setdefault('best_drop_rate', None)
    return result


def get_source_ankama_ids(game_version=None):
    """{'craftable': set, 'droppable': set} for the whole version. Cheaper than
    an IN clause when the caller has to filter a full item type at once."""
    if game_version is None:
        game_version = get_current_game_version()
    sources = {'craftable': set(), 'droppable': set()}
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        cursor = conn.cursor()
        for key, table in (('craftable', 'item_recipes'), ('droppable', 'item_drops')):
            if not _table_exists(cursor, table):
                continue
            cursor.execute(
                'SELECT DISTINCT i.ankama_id FROM %s t '
                'JOIN items i ON i.id = t.item '
                'WHERE i.ankama_id IS NOT NULL' % table)
            sources[key] = {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()
    return sources


def attach_acquisition(result_items, game_version=None):
    """Set craftable / best_drop_rate on picker result items, in one pass."""
    acquisition = get_acquisition_by_ankama_id(
        [getattr(item, 'ankama_id', None) for item in result_items], game_version)
    for item in result_items:
        sources = acquisition.get(getattr(item, 'ankama_id', None)) or {}
        item.craftable = sources.get('craftable', False)
        item.best_drop_rate = sources.get('best_drop_rate')
