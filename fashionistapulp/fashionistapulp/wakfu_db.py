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

"""Wakfu-only tables: rarity, spread lines, types, pictures, spells."""

import re

ITEM_RARITY_TABLE = 'item_rarity'
STAT_ELEMENT_COUNT_TABLE = 'stat_element_count'
ITEM_TYPE_POSITION_TABLE = 'item_type_position'
ITEM_TYPE_NAME_TABLE = 'item_type_names'
ITEM_PICTURE_TABLE = 'item_picture'

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
    """CREATE TABLE item_type_position
             (item_type INTEGER, position TEXT,
              PRIMARY KEY (item_type, position),
              FOREIGN KEY(item_type) REFERENCES item_types(id))""",
    """CREATE TABLE item_type_names
             (item_type INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (item_type, language),
              FOREIGN KEY(item_type) REFERENCES item_types(id))""",
    # gfx is Ankama's gfxId, shared by many items, not the skin column
    """CREATE TABLE item_picture
             (item INTEGER PRIMARY KEY, gfx INTEGER,
              FOREIGN KEY(item) REFERENCES items(id))""",
    # Costs and range never vary with the spell level
    """CREATE TABLE spells
             (id INTEGER PRIMARY KEY, class INTEGER, element TEXT,
              ap INTEGER, mp INTEGER, wp INTEGER, range TEXT)""",
    """CREATE TABLE spell_names
             (spell INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (spell, language),
              FOREIGN KEY(spell) REFERENCES spells(id))""",
    # conditional: row marked ": -" by Ankama, an alternative, never added up
    """CREATE TABLE spell_effects
             (spell INTEGER, level INTEGER, position INTEGER, kind TEXT,
              element TEXT, value INTEGER, is_percent INTEGER,
              conditional INTEGER,
              PRIMARY KEY (spell, level, position),
              FOREIGN KEY(spell) REFERENCES spells(id))""",
    """CREATE TABLE spell_text
             (spell INTEGER, language TEXT, normal TEXT, critical TEXT,
              PRIMARY KEY (spell, language),
              FOREIGN KEY(spell) REFERENCES spells(id))""",
)

# "Anneau{[~1]?x:}": {[~N]?A:B} is A when the quantity differs from N, else B
PLURAL_TEMPLATE = re.compile(r'\{\[~(\d+)\]\?([^:{}]*):([^:{}]*)\}')


def singular(text):
    """Name with the plural template resolved for 1; unchanged if a brace is left."""
    def pick(found):
        equal_count, differs, equals = found.groups()
        return equals if equal_count == '1' else differs
    resolved = PLURAL_TEMPLATE.sub(pick, text or '')
    return text if '{' in resolved else resolved


def create_tables(conn):
    """Add the Wakfu-only tables to an items database."""
    for statement in SCHEMA:
        conn.execute(statement)
