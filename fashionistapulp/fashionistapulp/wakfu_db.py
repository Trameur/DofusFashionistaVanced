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

"""Wakfu-only tables: rarity, spread lines, types, pictures, spells, effects."""

import collections
import json
import re
import struct

ITEM_RARITY_TABLE = 'item_rarity'
STAT_ELEMENT_COUNT_TABLE = 'stat_element_count'
ITEM_TYPE_POSITION_TABLE = 'item_type_position'
ITEM_TYPE_NAME_TABLE = 'item_type_names'
ITEM_PICTURE_TABLE = 'item_picture'
EFFECT_TABLE = 'effects'
EFFECT_GROUP_TABLE = 'effect_groups'
STATE_TABLE = 'states'
ABILITY_TABLE = 'abilities'
ABILITY_CATEGORY_TABLE = 'ability_categories'
CLIENT_SET_TABLE = 'client_sets'
SET_BONUS_TABLE = 'set_bonuses'

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
    # The client's effects: only those an item (worn or used), a set bonus, a
    # state or an ability reaches, groups expanded. params is the client's
    # float list as JSON; effect_value() turns it into a number at a level.
    # container_type is the client's name (ITEM_EQUIP, ITEM_USE, SET, STATE,
    # ABILITY, GROUP), normal_or_critical splits a use effect's two outcomes
    """CREATE TABLE effects
             (id INTEGER PRIMARY KEY, action INTEGER, container_type TEXT,
              container INTEGER, root_container_type TEXT,
              normal_or_critical TEXT, area_shape INTEGER, area_size TEXT,
              params TEXT)""",
    # An effect whose id is a group id runs the group's effects, in order
    """CREATE TABLE effect_groups
             (group_id INTEGER, position INTEGER, effect INTEGER,
              PRIMARY KEY (group_id, position),
              FOREIGN KEY(effect) REFERENCES effects(id))""",
    # key is the client's text key (for example malus_portee); the state's
    # effects are the effects rows with container_type STATE and container = id
    """CREATE TABLE states
             (id INTEGER PRIMARY KEY, key TEXT)""",
    # category: the fixed ability category that lists the ability. ddl and cgi
    # are the client's ddL and cgI, not understood yet. Its effects are the
    # effects rows with container_type ABILITY
    """CREATE TABLE abilities
             (id INTEGER PRIMARY KEY, category INTEGER, ddl INTEGER,
              cgi INTEGER,
              FOREIGN KEY(category) REFERENCES ability_categories(id))""",
    # Both lists are JSON arrays of integers. The two have different lengths
    # and are not paired: unlock_levels are character levels, ability_ids the
    # abilities of the category
    """CREATE TABLE ability_categories
             (id INTEGER PRIMARY KEY, unlock_levels TEXT, ability_ids TEXT)""",
    # Every set of the client, whether or not it has a bonus or a name: the
    # sets table above only holds the sets the encyclopedia names
    """CREATE TABLE client_sets
             (id INTEGER PRIMARY KEY, item_count INTEGER)""",
    # A bonus applies from `pieces` worn pieces on, and the bonuses of the
    # lower tiers still apply (cumulative)
    """CREATE TABLE set_bonuses
             (item_set INTEGER, pieces INTEGER, effect INTEGER,
              PRIMARY KEY (item_set, pieces, effect),
              FOREIGN KEY(item_set) REFERENCES client_sets(id),
              FOREIGN KEY(effect) REFERENCES effects(id))""",
    # Equip conditions. IF NOT EXISTS: a Dofus items.db may carry a table of
    # the same name and the same shape
    "CREATE TABLE IF NOT EXISTS item_criteria"
    " (item INTEGER PRIMARY KEY, criteria TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS item_other_criteria"
    " (item INTEGER, kind TEXT, criteria TEXT)",
    "CREATE TABLE IF NOT EXISTS item_properties (item INTEGER, property INTEGER)",
    "CREATE TABLE IF NOT EXISTS breeds (id INTEGER PRIMARY KEY, name TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS breed_base_values"
    " (breed INTEGER, stat INTEGER, value INTEGER)",
    "CREATE TABLE IF NOT EXISTS item_class_conditions (item INTEGER, class TEXT)",
    "CREATE TABLE IF NOT EXISTS items_not_worn_together"
    " (item INTEGER, other INTEGER)",
    "CREATE TABLE IF NOT EXISTS items_worn_with (item INTEGER, other INTEGER)",
    "CREATE TABLE IF NOT EXISTS unusable_items (item INTEGER)",
    "CREATE TABLE IF NOT EXISTS min_level_to_equip (item INTEGER, value INTEGER)",
    "CREATE TABLE IF NOT EXISTS max_level_to_equip (item INTEGER, value INTEGER)",
    "CREATE TABLE IF NOT EXISTS item_state_conditions"
    " (item INTEGER, option TEXT, nation INTEGER, operator TEXT, value INTEGER)",
    "CREATE TABLE IF NOT EXISTS criteria_labels"
    " (key TEXT, language TEXT, text TEXT)",
    "CREATE TABLE IF NOT EXISTS nations (id INTEGER, language TEXT, name TEXT)",
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


def float32(number):
    return struct.unpack('<f', struct.pack('<f', number))[0]


def effect_value(params, index, level):
    """The client's value of parameter pair `index` at `level`, in float32.

    params[2i] + params[2i+1] * L, the product replaced by its rounding when
    it is within 1e-5 of an integer. The client counts a state's level from 1
    where the tooltip counts from 0, so a Ruine of level 1 gives 5.
    """
    product = float32(params[2 * index + 1] * level)
    if abs(product - round(product)) < 1e-5:
        product = float(round(product))
    return float32(params[2 * index] + product)


EffectRow = collections.namedtuple(
    'EffectRow', 'id action container_type container normal_or_critical params')

EFFECT_COLUMNS = 'id, action, container_type, container, normal_or_critical, params'


def _effect_row(row):
    return EffectRow(*row[:5], json.loads(row[5]))


def effects_of(conn, container_type, container):
    """The effects a container (an item, state, set or ability) holds, by id."""
    return [_effect_row(row) for row in conn.execute(
        'SELECT %s FROM effects WHERE container_type = ? AND container = ?'
        ' ORDER BY id' % EFFECT_COLUMNS, (container_type, container))]


def expand_effect(conn, effect_id, _seen=()):
    """The effect, then every effect its group runs, groups inside groups included."""
    if effect_id in _seen:
        raise ValueError('effect group %d contains itself' % effect_id)
    row = conn.execute('SELECT %s FROM effects WHERE id = ?' % EFFECT_COLUMNS,
                       (effect_id,)).fetchone()
    if row is None:
        raise KeyError(effect_id)
    out = [_effect_row(row)]
    for (member,) in conn.execute(
            'SELECT effect FROM effect_groups WHERE group_id = ? ORDER BY position',
            (effect_id,)).fetchall():
        out.extend(expand_effect(conn, member, _seen + (effect_id,)))
    return out
