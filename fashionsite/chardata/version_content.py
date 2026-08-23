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

"""Telling a version's page apart from the live one, by its data.

Every item exists once per game version, and each gets its own url. Measured
across the catalogues, most of those really are different pages -- recipes and
set bonuses diverge far more than the stats do:

    beta     3796 of 3826 items identical to Dofus 3   (99.2%)
    dofus2    531 of 3314                              (16.0%)
    touch      48 of 2303                              ( 2.1%)
    retro      51 of 1774                              ( 2.9%)

So Dofus 2, Touch and Retro are genuinely different games and deserve their own
pages. Beta is not: it mirrors the live version until a patch lands, and 3796
of its item pages say exactly what the Dofus 3 page says.

A page that repeats another should say so, rather than claim to be its own. The
comparison is on the data rather than on the version name, so the day beta
diverges its pages become canonical in their own right without anyone changing
a setting.

Counting stats alone would have called 81.8% of Dofus 2 a duplicate and merged
away some three thousand pages that differ by their recipe.
"""

import hashlib
import sqlite3
import time

from fashionistapulp.fashionista_config import get_items_db_path

#: Rebuilt at most this often. The catalogues only change when the update
#: pipeline runs, so anything shorter is wasted work.
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
        for item_id, ankama_type, ankama_id, level, kind, item_set, name in cursor.execute(
                'SELECT id, ankama_type, ankama_id, level, type, item_set, name '
                'FROM items WHERE ankama_id IS NOT NULL '
                'AND COALESCE(removed, 0) = 0'):
            payload = repr((level, kind, item_set,
                            stats.get(item_id, []),
                            recipes.get(item_id, []),
                            bonuses.get(item_set, [])))
            signatures[(ankama_type, ankama_id)] = (
                hashlib.sha1(payload.encode('utf-8')).hexdigest(),
                name,
                type_names.get(kind, ''),
            )
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
        # A catalogue that will not open is not a reason to break a page: the
        # variant simply stays canonical in its own right, as it was before.
        signatures = {}
    _CACHE[version] = (now, signatures)
    return signatures


def repeats_the_live_version(game_version, ankama_type, ankama_id):
    """True when this version's item page says what the Dofus 3 page says.

    The picture counts, and counts most. This is a gear *appearance*
    optimizer: two pages carrying the same numbers but a different render are
    two different pages to the people who come here, whatever a text
    comparison would conclude. Measured on the catalogues, the picture is what
    separates them nearly everywhere --

        beta    3358 of the 3796 that match on data carry another picture
        touch     48 of 48                          -- every one of them
        retro     51 of 51                          -- every one of them
        dofus2     1 of 531

    -- so a comparison that skipped it would have merged 3458 pages that show
    a different item. It is checked with the same function that renders the
    page, so the two cannot drift apart.

    False whenever the answer is not certain: an unknown item, an unreadable
    catalogue. Claiming a page is a copy when it is not costs its indexing,
    while missing a duplicate costs only some crawl budget, so doubt is
    resolved in the page's favour.
    """
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
