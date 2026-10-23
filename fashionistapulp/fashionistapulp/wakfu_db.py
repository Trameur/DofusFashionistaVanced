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

"""Wakfu-only tables: rarity, spread lines, types, pictures, spells, effects, pets, monsters."""

import collections
import json
import math
import re
import struct

ITEM_RARITY_TABLE = 'item_rarity'
STAT_ELEMENT_COUNT_TABLE = 'stat_element_count'
ITEM_TYPE_POSITION_TABLE = 'item_type_position'
ITEM_TYPE_NAME_TABLE = 'item_type_names'
ITEM_PICTURE_TABLE = 'item_picture'
ITEM_LEVEL_CAP_TABLE = 'item_level_caps'
ITEM_LEVEL_LINE_TABLE = 'item_level_lines'
EFFECT_TABLE = 'effects'
EFFECT_GROUP_TABLE = 'effect_groups'
STATE_TABLE = 'states'
ABILITY_TABLE = 'abilities'
ABILITY_CATEGORY_TABLE = 'ability_categories'
CLIENT_SET_TABLE = 'client_sets'
CLIENT_SET_MEMBER_TABLE = 'client_set_members'
SET_BONUS_TABLE = 'set_bonuses'
CLIENT_SPELL_TABLE = 'client_spells'
CLIENT_SPELL_EFFECT_TABLE = 'client_spell_effects'
PET_TABLE = 'pets'
MOUNT_TABLE = 'mounts'
MONSTER_TABLE = 'monsters'
MONSTER_DROP_TABLE = 'monster_drops'
MONSTER_HARVEST_TABLE = 'monster_harvests'
LOOT_LIST_TABLE = 'loot_lists'
LOOT_LIST_ROW_TABLE = 'loot_list_rows'
STATE_TEXT_TABLE = 'state_texts'
CLIENT_SPELL_TEXT_TABLE = 'client_spell_texts'
CLIENT_SET_NAME_TABLE = 'client_set_names'
CLIENT_MONSTER_NAME_TABLE = 'client_monster_names'
MONSTER_FAMILY_NAME_TABLE = 'monster_family_names'
ABILITY_NAME_TABLE = 'ability_names'
ABILITY_CATEGORY_NAME_TABLE = 'ability_category_names'
EFFECT_TEXT_TABLE = 'effect_texts'
ACTION_TEXT_TABLE = 'action_texts'
CLIENT_JOB_NAME_TABLE = 'client_job_names'
CLIENT_BREED_NAME_TABLE = 'client_breed_names'
CLIENT_BREED_TEXT_TABLE = 'client_breed_texts'
CLIENT_APTITUDE_TEXT_TABLE = 'client_aptitude_texts'
CLIENT_ENCHANTMENT_TEXT_TABLE = 'client_enchantment_texts'
CLIENT_ITEM_TYPE_NAME_TABLE = 'client_item_type_names'
CLIENT_PICTURE_TABLE = 'client_pictures'

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
    # The highest level of a pet or mount (emm of the client tables)
    """CREATE TABLE item_level_caps
             (item INTEGER PRIMARY KEY, slot TEXT, cap INTEGER,
              FOREIGN KEY(item) REFERENCES items(id))""",
    # line is the index in the dump's lines; the value at level L is
    # base + per_level * L, see level_value
    """CREATE TABLE item_level_lines
             (item INTEGER, line INTEGER, stat INTEGER, base REAL, per_level REAL,
              PRIMARY KEY (item, line),
              FOREIGN KEY(item) REFERENCES items(id),
              FOREIGN KEY(stat) REFERENCES stats(id))""",
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
    # criterion is the client's condition on the effect, empty when none.
    # container_type is the client's name (ITEM_EQUIP, ITEM_USE, SET, STATE,
    # ABILITY, GROUP), normal_or_critical splits a use effect's two outcomes
    """CREATE TABLE effects
             (id INTEGER PRIMARY KEY, action INTEGER, container_type TEXT,
              container INTEGER, root_container_type TEXT,
              normal_or_critical TEXT, area_shape INTEGER, area_size TEXT,
              params TEXT, criterion TEXT)""",
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
    # The pieces of a client set in the client's own order. item is the id in
    # the client's item table, as the client lists it, and is never NULL; a few
    # pieces of admin and test sets are in no item table, so there is no foreign
    # key (items holds gear only) and "not in the client item table" is a query
    """CREATE TABLE client_set_members
             (item_set INTEGER, position INTEGER, item INTEGER,
              PRIMARY KEY (item_set, position),
              FOREIGN KEY(item_set) REFERENCES client_sets(id))""",
    # A bonus applies from `pieces` worn pieces on, and the bonuses of the
    # lower tiers still apply (cumulative)
    """CREATE TABLE set_bonuses
             (item_set INTEGER, pieces INTEGER, effect INTEGER,
              PRIMARY KEY (item_set, pieces, effect),
              FOREIGN KEY(item_set) REFERENCES client_sets(id),
              FOREIGN KEY(effect) REFERENCES effects(id))""",
    # There is no table of spell levels. A client spell holds unlock_level and
    # max_level, client_spell_effects lists its effects, and the value of an
    # effect at a level L is effect_value(params, i, L) below
    # The client's spells, class and monster ones alike, apart from the spells
    # table above, which holds the encyclopedia's class spells and is owned
    # by another writer. breed is 0, -1 or -2 on the spells no class owns.
    # ap, mp and wp are the client's costs, range_min and range_max in cells,
    # element the client's code (FIRE 1, WATER 2, EARTH 3, AIR 4, none 9),
    # unlock_level the character level that gives the spell
    """CREATE TABLE client_spells
             (id INTEGER PRIMARY KEY, breed INTEGER, ap REAL, mp REAL, wp REAL,
              range_min REAL, range_max REAL, element INTEGER,
              unlock_level INTEGER, max_level INTEGER)""",
    # A spell's effects are the ones its own list names, in order: never every
    # SPELL effect whose container is the spell, some belong to spells that are gone
    """CREATE TABLE client_spell_effects
             (spell INTEGER, position INTEGER, effect INTEGER,
              PRIMARY KEY (spell, position),
              FOREIGN KEY(spell) REFERENCES client_spells(id),
              FOREIGN KEY(effect) REFERENCES effects(id))""",
    # item: the pet's item in the client's item table, NULL when the client's
    # item table lacks it, as for a mount. Its effects are the
    # effects rows with container_type ITEM_EQUIP and container = item.
    # emm is the level cap, eop the experience per level, eoq a byte of the
    # feeding record
    """CREATE TABLE pets
             (id INTEGER PRIMARY KEY, item INTEGER, eoq INTEGER, eop INTEGER,
              emm INTEGER)""",
    # item is NULL for the mounts whose item the client no longer has. The
    # mount's effects are the item's, as for a pet. emm is the level cap, eop
    # the experience per level, eoq a byte of the feeding record
    """CREATE TABLE mounts
             (id INTEGER PRIMARY KEY, item INTEGER, eop INTEGER, emm INTEGER,
              eoq INTEGER)""",
    """CREATE TABLE monsters
             (id INTEGER PRIMARY KEY, family INTEGER)""",
    # What a monster drops outright: rate is a probability
    """CREATE TABLE monster_drops
             (monster INTEGER, position INTEGER, item INTEGER, rate REAL,
              quantity_min INTEGER, quantity_max INTEGER,
              PRIMARY KEY (monster, position),
              FOREIGN KEY(monster) REFERENCES monsters(id))""",
    # What a monster yields when harvested: a loot list, kept or not by the
    # condition text (for example IsDead("target"))
    """CREATE TABLE monster_harvests
             (monster INTEGER, position INTEGER, loot_list INTEGER,
              condition TEXT,
              PRIMARY KEY (monster, position),
              FOREIGN KEY(monster) REFERENCES monsters(id),
              FOREIGN KEY(loot_list) REFERENCES loot_lists(id))""",
    """CREATE TABLE loot_lists
             (id INTEGER PRIMARY KEY)""",
    # A row is an item (item set, sub_list NULL) or another list (sub_list
    # set, item NULL), kept as a reference and never flattened. rate is a
    # probability below 1, a weight above 1, or -1 for always given. item is
    # kept as the client gives it: 0 means none, and some rows name an item the
    # client's item table lacks
    """CREATE TABLE loot_list_rows
             (loot_list INTEGER, position INTEGER, id INTEGER, item INTEGER,
              sub_list INTEGER, rate REAL, quantity_min INTEGER,
              quantity_max INTEGER,
              PRIMARY KEY (loot_list, position),
              FOREIGN KEY(loot_list) REFERENCES loot_lists(id),
              FOREIGN KEY(sub_list) REFERENCES loot_lists(id))""",
    # The client's own texts, as the client shows them. de is the English text
    # because Wakfu has no German. A text the client lacks has no row, and a
    # template ({...} or %s) is kept raw
    """CREATE TABLE state_texts
             (state INTEGER, language TEXT, name TEXT, description TEXT,
              PRIMARY KEY (state, language),
              FOREIGN KEY(state) REFERENCES states(id))""",
    """CREATE TABLE client_spell_texts
             (spell INTEGER, language TEXT, name TEXT, description TEXT,
              PRIMARY KEY (spell, language),
              FOREIGN KEY(spell) REFERENCES client_spells(id))""",
    """CREATE TABLE client_set_names
             (item_set INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (item_set, language),
              FOREIGN KEY(item_set) REFERENCES client_sets(id))""",
    """CREATE TABLE client_monster_names
             (monster INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (monster, language),
              FOREIGN KEY(monster) REFERENCES monsters(id))""",
    """CREATE TABLE monster_family_names
             (family INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (family, language))""",
    """CREATE TABLE ability_names
             (ability INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (ability, language),
              FOREIGN KEY(ability) REFERENCES abilities(id))""",
    """CREATE TABLE ability_category_names
             (category INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (category, language),
              FOREIGN KEY(category) REFERENCES ability_categories(id))""",
    """CREATE TABLE effect_texts
             (effect INTEGER, language TEXT, text TEXT,
              PRIMARY KEY (effect, language),
              FOREIGN KEY(effect) REFERENCES effects(id))""",
    """CREATE TABLE action_texts
             (action INTEGER, language TEXT, text TEXT,
              PRIMARY KEY (action, language))""",
    # Only the pictures a row of this table names are extracted from the client's
    # picture archive; the rest of the archive is left alone
    # The picture file the client draws for a row, as the client names it: family is
    # item, spell, state, ability, monster, monster_family or class, and the
    # picture is the number or key of the file, not a path
    """CREATE TABLE client_pictures
             (family TEXT NOT NULL, id INTEGER NOT NULL, picture TEXT NOT NULL,
              PRIMARY KEY (family, id))""",
    # The language file's keyed texts, same rule as above: a key or an id the
    # client has in no table gets a row too. breed is the class number of
    # breed.<number>, the other breed.* keys (roles, descriptions) and the
    # breedLongName.<number> and breedLongDesc.<number> keys are in
    # client_breed_texts under their whole key. item_type is the id of
    # content.14; the open data's itemTypes.json is where the item_types
    # table gets its ids and names, so these rows are the client's own wording
    """CREATE TABLE client_job_names
             (job INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (job, language))""",
    """CREATE TABLE client_breed_names
             (breed INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (breed, language))""",
    """CREATE TABLE client_breed_texts
             (key TEXT, language TEXT, text TEXT,
              PRIMARY KEY (key, language))""",
    """CREATE TABLE client_aptitude_texts
             (key TEXT, language TEXT, text TEXT,
              PRIMARY KEY (key, language))""",
    """CREATE TABLE client_enchantment_texts
             (key TEXT, language TEXT, text TEXT,
              PRIMARY KEY (key, language))""",
    """CREATE TABLE client_item_type_names
             (item_type INTEGER, language TEXT, name TEXT,
              PRIMARY KEY (item_type, language))""",
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


def level_value(base, per_level, level):
    """The client's value of a pet or mount line at its displayed level.

    Floored for a slope >= 0 and ceiled below (eVG.a).
    """
    value = effect_value((base, per_level), 0, level)
    return int(math.floor(value) if per_level >= 0 else math.ceil(value))


EffectRow = collections.namedtuple(
    'EffectRow',
    'id action container_type container normal_or_critical params criterion')

EFFECT_COLUMNS = ('id, action, container_type, container, normal_or_critical, params,'
                  ' criterion')


def _effect_row(row):
    return EffectRow(*row[:5], json.loads(row[5]), row[6])


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
