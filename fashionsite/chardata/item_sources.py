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


_source_ids_cache = {}


def get_source_ankama_ids(game_version=None):
    """{'craftable': set, 'droppable': set} for the whole version. Cheaper than
    an IN clause when the caller has to filter a full item type at once, or has
    to answer for many builds in a row. Cached per version: the item DB does not
    change while the process runs."""
    if game_version is None:
        game_version = get_current_game_version()
    cached = _source_ids_cache.get(game_version)
    if cached is not None:
        return cached
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
    _source_ids_cache[game_version] = sources
    return sources


def acquisition_text(craftable, best_drop_rate):
    """"Craftable", "Drop rate: 2.50%", or both. Empty when we know of no source:
    we never claim an item is unobtainable, a quest may still give it."""
    from django.template.defaultfilters import floatformat
    from django.utils.translation import gettext as _
    parts = []
    if craftable:
        parts.append(_('Craftable'))
    if best_drop_rate:
        rate = ('< 0.01%' if best_drop_rate < 0.01
                else '%s%%' % floatformat(best_drop_rate, 2))
        parts.append(_('Drop rate: %(rate)s') % {'rate': rate})
    return ' · '.join(parts)


def format_acquisition_counts(craftable, drop_only, unknown, rarest_rate=None):
    """The set-level sentence. rarest_rate is optional: the gallery cards only
    have the counts (working out the rarest rate would mean a query per build),
    the solution page has it and says it."""
    from django.template.defaultfilters import floatformat
    from django.utils.translation import ngettext
    parts = []
    if craftable:
        parts.append(ngettext('%(count)s craftable piece',
                              '%(count)s craftable pieces',
                              craftable) % {'count': craftable})
    if drop_only:
        if rarest_rate:
            rate = ('< 0.01%' if rarest_rate < 0.01
                    else '%s%%' % floatformat(rarest_rate, 2))
            parts.append(
                ngettext('%(count)s piece by drop only, the rarest at %(rate)s',
                         '%(count)s pieces by drop only, the rarest at %(rate)s',
                         drop_only) % {'count': drop_only, 'rate': rate})
        else:
            parts.append(ngettext('%(count)s piece by drop only',
                                  '%(count)s pieces by drop only',
                                  drop_only) % {'count': drop_only})
    if unknown:
        parts.append(ngettext('%(count)s piece with no known source',
                              '%(count)s pieces with no known source',
                              unknown) % {'count': unknown})
    return ' · '.join(parts)


def summarize_by_ankama_id(entries, game_version=None):
    """Counts for a build we only know by (ankama_id, type name) pairs, which is
    all a gallery card has. Two set lookups, no per-build query."""
    sources = get_source_ankama_ids(game_version)
    craftable = drop_only = unknown = 0
    for ankama_id, type_name in entries:
        if ankama_id in sources['craftable']:
            craftable += 1
        elif ankama_id in sources['droppable']:
            drop_only += 1
        elif type_name in ('Dofus', 'Pet'):
            continue
        else:
            unknown += 1
    return {'craftable': craftable, 'drop_only': drop_only, 'unknown': unknown}


def acquisition_summary(result_items):
    """One line for the whole set: how many pieces you can craft, how many you
    can only farm, and the rarest of those rates, which is what really sets the
    farming time. Deliberately no score and no time estimate: we have no data
    for either. Items we know no source for are counted as unknown, never as
    unobtainable."""
    craftable = 0
    drop_only_rates = []
    unknown = 0
    for item in result_items:
        if not getattr(item, 'item_added', False):
            continue
        if getattr(item, 'craftable', False):
            craftable += 1
        elif getattr(item, 'best_drop_rate', None):
            drop_only_rates.append(item.best_drop_rate)
        elif getattr(item, 'type', None) in ('Dofus', 'Pet'):
            # A dofus comes from a quest or a dungeon boss and a mount from
            # breeding, so having neither recipe nor drop is normal for them,
            # not a gap. Trophies and prysmaradites sit in the same section but
            # do have recipes, and those still count above.
            continue
        else:
            unknown += 1

    return format_acquisition_counts(
        craftable, len(drop_only_rates), unknown,
        min(drop_only_rates) if drop_only_rates else None)


def attach_acquisition(result_items, game_version=None):
    """Set craftable / best_drop_rate / acquisition_text on result items, in one
    pass over the database."""
    acquisition = get_acquisition_by_ankama_id(
        [getattr(item, 'ankama_id', None) for item in result_items], game_version)
    for item in result_items:
        sources = acquisition.get(getattr(item, 'ankama_id', None)) or {}
        item.craftable = sources.get('craftable', False)
        item.best_drop_rate = sources.get('best_drop_rate')
        item.acquisition_text = acquisition_text(item.craftable, item.best_drop_rate)
