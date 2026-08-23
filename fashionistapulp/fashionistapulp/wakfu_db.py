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

"""The two things Wakfu gear carries that the items schema has nowhere to put.

The rest of Wakfu fits the schema the five Dofus versions already share, and it
fits because the parts that differ between games are rows rather than columns:
`stats` names the characteristics, `item_types` the slots, `item_flags` the
two-handed / relic / epic marks. None of that needs a new column.

Two facts have nowhere to go, so they get one small table each, and both tables
live only in items_wakfu.db:

RARITY is a tier from 0 to 7 on the item itself. It is not a statistic, so
`stats_of_item` would be a lie, and it is not a yes-or-no mark, so `item_flags`
would lose the ordering. One row per item.

THE NUMBER OF ELEMENTS a mastery line spreads over is a property of the LINE,
not of the item and not of the stat: a line reads "232 Mastery with 2 elements"
and `stats_of_item` has room for the 232 and nowhere for the 2. See
wakfu_stats.py for what the planner assumes about where those elements land.

The element table names the line it qualifies in full, by the item's own line
number and by the stat and value that line carries, rather than leaning on the
order sqlite happens to return `stats_of_item` in. That costs two columns and
buys a reader that can check the two tables still agree, which structure.py
does: a line that names a stat and value no `stats_of_item` row carries is a
build where the two halves have drifted apart, and it fails loudly there.

ONE QUESTION THE IMPORTER STILL HAS TO ANSWER, written down rather than
guessed: `items.type` is one column and a Wakfu ring declares two positions,
LEFT_HAND and RIGHT_HAND, on the same item type. Whether `item_types` holds the
twelve positions or Ankama's own item types, and where the second hand then
goes, is not settled here. wakfu_slots.BOTH_HANDS states the fact; nothing in
this file depends on which way it is stored.
"""

ITEM_RARITY_TABLE = 'item_rarity'
STAT_ELEMENT_COUNT_TABLE = 'stat_element_count'

SCHEMA = (
    """CREATE TABLE item_rarity
             (item INTEGER PRIMARY KEY, rarity INTEGER,
              FOREIGN KEY(item) REFERENCES items(id))""",
    """CREATE TABLE stat_element_count
             (item INTEGER, line INTEGER, stat INTEGER, value INTEGER,
              elements INTEGER,
              PRIMARY KEY (item, line),
              FOREIGN KEY(item) REFERENCES items(id),
              FOREIGN KEY(stat) REFERENCES stats(id))""",
)


def create_tables(conn):
    """Add both tables to an items database that does not have them yet."""
    for statement in SCHEMA:
        conn.execute(statement)
