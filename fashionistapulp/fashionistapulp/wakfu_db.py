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

THE POSITIONS A TYPE FILLS answer the question this file used to leave open:
`items.type` is one column and a Wakfu ring declares two positions, LEFT_HAND
and RIGHT_HAND, on the same item type.

`item_types` holds ANKAMA'S OWN TYPES, the 25 a player recognises, and this
table says where each one goes. Filing items under the twelve positions
instead was the first attempt and it loses real information: a Needle
(one-handed) and an Axe (two-handed) are not the same kind of thing, and a
site that lets a reader filter by type would offer them one bucket called
FIRST_WEAPON.

The slot COUNT falls out of the rows rather than being stored: a Ring has two
rows, everything else has one. That is what Dofus keeps in the hand-written
`TYPE_NAME_TO_SLOT_NUMBER`, derived here instead, because Ankama publishes it
in `equipmentItemTypes.json` and a published fact should never be retyped.

THE TYPE NAMES come with the data in the four languages Wakfu is played in,
so they are stored the way item and set names are, rather than going through
gettext like the Dofus type names do. Asking a translator for "Anneau" would
invent a second word for something Ankama has already named, and the site
would then disagree with the game a player is reading it beside. German is the
one language Wakfu has never had; it falls back to English, like every other
Wakfu string.

THE PICTURE a piece of gear shows is Ankama's `gfxId`, and it is not the item
id: 7785 pieces of gear share 3928 drawings, so the artwork is stored once
under the gfx id and this table says which item points at which. The `skin`
column the shared schema already has is a different thing, a small animation
number Dofus uses, and putting a seven-digit gfx id in it would have been a
quiet lie.

THE SPELLS get four tables of their own because Ankama publishes no spell file
at all: the CDN answers 403 for spells.json and the encyclopedia is where they
live. Wakfu is the only version here whose spells are DATA rather than a
hand-written python constant, which is why they need a schema and the Dofus
versions do not.

The shape of those four is a measurement and not a guess. A spell page offers
245 levels for every field, so the obvious import writes 245 rows per spell.
Measured across all 715 spells: THE AP, MP AND WP COSTS AND THE RANGE DO NOT
VARY WITH THE LEVEL. Not rarely, never, on any spell. Only the damage moves,
and only for 280 of the 715. So the cost sits on the spell, once, and only the
figures are stored per level: 715 rows where the obvious import would write
175 175.

`spell_text` keeps the sentence once per spell and per language rather than
once per level, because 708 of the 715 carry a single template across their
whole range and only the numbers inside it move.

`spell_effects.is_percent` is there for two spells, Entaille and Sang Brulant,
which read "Dommage : 10 %" of the caster's health. Stored as a flat 10 they
would sit in the data looking like the feeblest hit in the game.

`spell_effects.conditional` says whether a row lands on a plain cast. A spell's
figures are NOT a sum: the Cra's Fleche d'immolation lists 60, 121 and 181, and
those are alternatives, while the Iop's Bastonnade says 250 "a la place" of 83.
Adding them up put one class at three times the damage per AP of its nearest
neighbour, which is what made the question worth asking. Ankama marks a
conditional row with ": -" before it, and punctuation is the same in every
language, which is why this is read from the markup and not from words.

Nothing about doubling lives here. Whether two copies of one ring may be worn
is a rule of the game and sits in `game_versions.rings_can_double`, which is
also why storing the real names was safe: the model used to read that rule off
a type being NAMED 'Ring', and 'Ring' is exactly what Wakfu calls one of the
types this table now holds.
"""

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
    """CREATE TABLE item_picture
             (item INTEGER PRIMARY KEY, gfx INTEGER,
              FOREIGN KEY(item) REFERENCES items(id))""",
    """CREATE TABLE spells
             (id INTEGER PRIMARY KEY, class INTEGER, element TEXT,
              ap INTEGER, mp INTEGER, wp INTEGER, range TEXT)""",
    """CREATE TABLE spell_names
             (spell INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (spell, language),
              FOREIGN KEY(spell) REFERENCES spells(id))""",
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

# Ankama writes a name once and lets the client pick the ending:
# "Anneau{[~1]?x:}" is Anneau or Anneaux, "An{[~1]?eis:el}" is anel or aneis.
# The general form is {[~N]?A:B}, meaning A when the quantity differs from N
# and B when it equals it. A page shows one item, so the quantity is 1.
PLURAL_TEMPLATE = re.compile(r'\{\[~(\d+)\]\?([^:{}]*):([^:{}]*)\}')


def singular(text):
    """Ankama's name for one of a thing, with the plural template resolved.

    Either the whole string resolves or nothing is touched. The stat line
    templates carry far richer forms, nested and testing the line's own
    parameters, and a partial pass over one of those turns
    "{[99>3]?:{[0<3]?:{[~3]?([#3]%):}" into a shorter piece of nonsense that
    still looks like a name. Names are simple, so a leftover brace means this
    was not a name and the caller gets its string back unchanged, able to tell
    the two apart by looking for that brace.
    """
    def pick(found):
        equal_count, differs, equals = found.groups()
        return equals if equal_count == '1' else differs
    resolved = PLURAL_TEMPLATE.sub(pick, text or '')
    return text if '{' in resolved else resolved


def create_tables(conn):
    """Add both tables to an items database that does not have them yet."""
    for statement in SCHEMA:
        conn.execute(statement)
