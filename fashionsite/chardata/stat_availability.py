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

"""Stats a version cannot give, so the pages stop offering them.

A weight only steers the optimizer if something in that version's catalogue can
carry the stat. On Retro ten of them cannot: pushback damage and resistance,
critical damage and resistance, lock, dodge, and the four AP and MP reduction
and resistance lines. Not one item and not one set bonus grants any of them, so
a reader who weighted them was moving a control wired to nothing.

Measured per version, never hand-listed: a hand-list is wrong the day a version
gains an item.

The weird-item bonuses in model.py could give such a weight a second route, but
that whole block returns early for anything other than dofus3 and the beta, so
on the other versions there is no route at all.
"""
import sqlite3

from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

_CACHE = {}


def stats_with_no_source(game_version):
    """Stat keys no item and no set bonus of this version can grant."""
    if game_version in _CACHE:
        return _CACHE[game_version]

    structure = get_structure(game_version)
    by_id = {stat.id: stat.key for stat in structure.get_stats_list()}
    granted = set()
    connection = None
    try:
        connection = sqlite3.connect(
            'file:%s?mode=ro' % get_items_db_path(game_version), uri=True)
        for table in ('stats_of_item', 'set_bonus'):
            try:
                rows = connection.execute(
                    'SELECT DISTINCT stat FROM "%s" WHERE value <> 0' % table)
            except sqlite3.Error:
                continue
            for (stat_id,) in rows:
                granted.add(stat_id)
    except sqlite3.Error:
        # Unreadable database: offer everything rather than hide the page.
        _CACHE[game_version] = frozenset()
        return _CACHE[game_version]
    finally:
        if connection is not None:
            connection.close()

    missing = frozenset(key for stat_id, key in by_id.items()
                        if stat_id not in granted)
    _CACHE[game_version] = missing
    return missing

# model.py hands a handful of named Dofus 3 items extra objective weight from
# stats no item carries directly: weighting HP steers the Emerald Dofus,
# weighting Dodge steers the Ochre. That block returns early for every version
# other than these two, so only there can a stat with no item source still be
# inert.
_VERSIONS_WITH_WEIRD_ITEM_WEIGHTS = ('dofus3', 'beta')


def stats_not_worth_offering(game_version):
    """Stat keys a weight on which cannot change the answer, in this version.

    Empty for dofus3 and the beta: there a stat with no item behind it can
    still move the solver through the named-item weights, so offering it is
    honest.
    """
    if game_version in _VERSIONS_WITH_WEIRD_ITEM_WEIGHTS:
        return frozenset()
    return stats_with_no_source(game_version)
