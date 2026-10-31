#!/usr/bin/env python3
"""Turn the decoded Wakfu build into an items database the site can read.

    python build_wakfu_db.py [--dump itemscraper/transformed_wakfu.json]

Run `get_items_wakfu.py` first: this reads what that writes and never touches
Ankama's servers.

The schema is the one the five Dofus versions already share, copied table for
table from `items.db`, because the parts that differ between games are ROWS and
not columns: `stats` names the characteristics, `item_types` the slots,
`item_flags` the marks. Wakfu's 34 characteristics and 12 slots are therefore
rows in a database of its own, and no Dofus version is touched.

Two facts have nowhere to sit in that schema, so `wakfu_db.py` adds one small
table each, and both exist only here: the rarity tier, and how many elements a
mastery line spreads over. See that module for why neither fits `stats_of_item`.

Sets are filled from what `get_sets_wakfu.py` recovered, because the CDN
publishes no set file: only the NAME comes from the encyclopedia, never the
bonus total it prints, which is stale. A set whose page has gone (three of
them) keeps its items and simply has no name to show.

The client's tables (get_wakfu_client.py writes tables.json) fill the
effects, effect_groups, states, abilities, ability_categories, client_sets,
client_set_members and set_bonuses tables: the effects an item of the client, a set bonus,
a state, an ability or a spell (through its own effect list) reaches, with every effect
whose id is a group id expanded. They also fill client_spells,
client_spell_effects, pets, mounts, monsters, monster_drops, monster_harvests,
loot_lists and loot_list_rows. Nothing reads them yet. A client that is not
there leaves them empty, with a notice.

The client's texts (texts.json, from the same step) fill state_texts,
client_spell_texts, client_set_names, client_monster_names, monster_family_names,
ability_names, ability_category_names, effect_texts and action_texts, one row
per language for each text the client has, and, whether or not another table
has a row for the id or key, client_job_names, client_breed_names,
client_breed_texts, client_aptitude_texts, client_enchantment_texts and
client_item_type_names. de is the English text; a text the English file lacks gets no
de row.

client_pictures names the picture file the client draws for each item, spell, state,
ability, monster, monster family and class; get_wakfu_images.py extracts them from the
client's picture archive.

German is absent from Wakfu entirely; `get_items_wakfu.py` and
`get_sets_wakfu.py` both fall it back to English, and that is what lands here.
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'fashionistapulp'))
from fashionistapulp import wakfu_aptitudes, wakfu_criteria  # noqa: E402
from fashionistapulp.wakfu_db import (create_tables, level_value,  # noqa: E402
                                      singular)
from fashionistapulp.wakfu_slots import (COMPANION_SLOTS,  # noqa: E402
                                         EQUIPMENT_POSITION_IDS, RARITIES,
                                         SOLVED_SLOTS, TWO_HANDED_FLAG)
from fashionistapulp.wakfu_stats import WAKFU_STATS  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DOFUS_DB = HERE / 'fashionistapulp' / 'fashionistapulp' / 'items.db'
WAKFU_DB = HERE / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'

# The site reads names in these five; the data only carries four, and the
# decoder has already put English under 'de'.
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

# A slot a build fills. The rest (costumes) is kept out of the item table
# rather than carried and then filtered everywhere downstream.
GEAR = set(SOLVED_SLOTS)


def dofus_schema():
    """Every CREATE statement of the shared schema, read from items.db."""
    conn = sqlite3.connect('file:%s?mode=ro' % DOFUS_DB, uri=True)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master"
            " WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'").fetchall()
    finally:
        conn.close()
    return [sql for (sql,) in rows]


def stat_name(key):
    """A readable name for a characteristic the client only names in caps."""
    return key.replace('_PERCENT', '').replace('_', ' ').title()


def read_sets(out_dir, version):
    """{set id: {language: name}} from get_sets_wakfu.py, or nothing yet."""
    path = Path(out_dir) / version / 'sets.json'
    if not path.exists():
        return {}
    with io.open(path, encoding='utf-8') as handle:
        return {int(key): names for key, names in json.load(handle).items()}


PREVIOUS = {
    'items': 'SELECT id, name, level, type, item_set, ankama_id, ankama_type,'
             ' dofustouch, skin FROM items',
    'item_names': 'SELECT item, language, name FROM item_names',
    'item_flags': 'SELECT item, flag FROM item_flags',
    'item_rarity': 'SELECT item, rarity FROM item_rarity',
    'item_picture': 'SELECT item, gfx FROM item_picture',
    'stats_of_item': 'SELECT item, stat, value, min_value, max_value'
                     ' FROM stats_of_item',
    'stat_element_count': 'SELECT item, line, stat, value, elements'
                          ' FROM stat_element_count',
    'item_level_caps': 'SELECT item, slot, cap FROM item_level_caps',
    'item_level_lines': 'SELECT item, line, stat, base, per_level FROM item_level_lines',
    'item_shard_slots': 'SELECT item, minimum, maximum FROM item_shard_slots',
    'stats': 'SELECT id, key FROM stats',
    'item_types': 'SELECT id, name FROM item_types',
    'item_type_names': 'SELECT item_type, language, name FROM item_type_names',
    'item_type_position': 'SELECT item_type, position FROM item_type_position',
    'item_criteria': 'SELECT item, criteria FROM item_criteria',
    'item_other_criteria': 'SELECT item, kind, criteria FROM item_other_criteria',
    'item_properties': 'SELECT item, property FROM item_properties',
    'item_class_conditions': 'SELECT item, class FROM item_class_conditions',
    'items_not_worn_together': 'SELECT item, other FROM items_not_worn_together',
    'items_worn_with': 'SELECT item, other FROM items_worn_with',
    'unusable_items': 'SELECT item FROM unusable_items',
    'min_level_to_equip': 'SELECT item, value FROM min_level_to_equip',
    'max_level_to_equip': 'SELECT item, value FROM max_level_to_equip',
    'min_stat_to_equip': 'SELECT item, stat, value FROM min_stat_to_equip',
    'max_stat_to_equip': 'SELECT item, stat, value FROM max_stat_to_equip',
    'item_state_conditions': 'SELECT item, option, nation, operator, value'
                             ' FROM item_state_conditions',
}


def read_previous(db_path):
    """Every row the database held before this build, by table."""
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        rows = {}
        for table, query in PREVIOUS.items():
            try:
                rows[table] = conn.execute(query).fetchall()
            except sqlite3.OperationalError as error:
                # A database built before this table existed holds no row of it
                if 'no such table' not in str(error):
                    raise
                rows[table] = []
        return rows
    finally:
        conn.close()


def level_caps(tables):
    """{item id: (slot, level cap)} of the client's pets and mounts that name an item."""
    caps = {}
    if tables is None:
        return caps
    for slot, key in (('PET', 'pets'), ('MOUNT', 'mounts')):
        for row in tables.get(key, ()):
            if row['item'] is None:
                continue
            if row['item'] in caps:
                raise ValueError('item %d has two rows in the client pet and mount tables'
                                 % row['item'])
            caps[row['item']] = (slot, row['emm'])
    return caps


def check_leveled_line(item_id, line):
    """Stop on a leveled line the structure has no reading for."""
    params = line['params']
    template = (line.get('template') or {}).get('en') or ''
    if line.get('elements'):
        raise ValueError('leveled line of item %d spreads over elements' % item_id)
    if len(params) < 2 or params[1] < 0:
        raise ValueError('leveled line of item %d has no non-negative slope' % item_id)
    if line['value'] != params[0]:
        raise ValueError('leveled line of item %d: value is not the base' % item_id)
    if template.strip().startswith('-') or '] -[#1]' in template:
        raise ValueError('leveled line of item %d is a malus' % item_id)


def keep_removed(conn, previous, written, stat_ids, set_ids, type_ids):
    """Add back, flagged removed, the items the new build no longer has."""
    gone = {row[0] for row in previous['items']} - written
    if not gone:
        return 0
    old_keys = dict(previous['stats'])
    new_ids = {key.lower(): number for key, number in stat_ids.items()}
    for item_id, name, level, type_id, item_set, ankama_id, ankama_type, \
            dofustouch, skin in previous['items']:
        if item_id not in gone:
            continue
        if type_id not in type_ids:
            type_ids.add(type_id)
            for row in previous['item_types']:
                if row[0] == type_id:
                    conn.execute('INSERT INTO item_types (id, name)'
                                 ' VALUES (?, ?)', row)
            for row in previous['item_type_names']:
                if row[0] == type_id:
                    conn.execute('INSERT INTO item_type_names (item_type,'
                                 ' language, name) VALUES (?, ?, ?)', row)
            for row in previous['item_type_position']:
                if row[0] == type_id:
                    conn.execute('INSERT INTO item_type_position'
                                 ' (item_type, position) VALUES (?, ?)', row)
        conn.execute(
            'INSERT INTO items (id, name, level, type, item_set, ankama_id,'
            ' ankama_type, removed, dofustouch, skin)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)',
            (item_id, name, level, type_id,
             item_set if item_set in set_ids else None, ankama_id,
             ankama_type, dofustouch, skin))
    for row in previous['item_names']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_names (item, language, name)'
                         ' VALUES (?, ?, ?)', row)
    for row in previous['item_flags']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_flags (item, flag) VALUES (?, ?)',
                         row)
    for row in previous['item_rarity']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_rarity (item, rarity)'
                         ' VALUES (?, ?)', row)
    for row in previous['item_picture']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_picture (item, gfx) VALUES (?, ?)',
                         row)
    for row in previous['item_criteria']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_criteria (item, criteria)'
                         ' VALUES (?, ?)', row)
    for row in previous['item_other_criteria']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_other_criteria (item, kind, criteria)'
                         ' VALUES (?, ?, ?)', row)
    for row in previous['item_properties']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_properties (item, property)'
                         ' VALUES (?, ?)', row)
    for row in previous['item_class_conditions']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_class_conditions (item, class)'
                         ' VALUES (?, ?)', row)
    for row in previous['items_not_worn_together']:
        if row[0] in gone:
            conn.execute('INSERT INTO items_not_worn_together (item, other)'
                         ' VALUES (?, ?)', row)
    for row in previous['items_worn_with']:
        if row[0] in gone:
            conn.execute('INSERT INTO items_worn_with (item, other)'
                         ' VALUES (?, ?)', row)
    for row in previous['unusable_items']:
        if row[0] in gone:
            conn.execute('INSERT INTO unusable_items (item) VALUES (?)', row)
    for row in previous['min_level_to_equip']:
        if row[0] in gone:
            conn.execute('INSERT INTO min_level_to_equip (item, value)'
                         ' VALUES (?, ?)', row)
    for row in previous['max_level_to_equip']:
        if row[0] in gone:
            conn.execute('INSERT INTO max_level_to_equip (item, value)'
                         ' VALUES (?, ?)', row)
    for row in previous['item_state_conditions']:
        if row[0] in gone:
            conn.execute('INSERT INTO item_state_conditions (item, option,'
                         ' nation, operator, value) VALUES (?, ?, ?, ?, ?)', row)
    for item, stat, value in previous['min_stat_to_equip']:
        number = new_ids.get(str(old_keys.get(stat)).lower())
        if item in gone and number:
            conn.execute('INSERT INTO min_stat_to_equip (item, stat, value)'
                         ' VALUES (?, ?, ?)', (item, number, value))
    for item, stat, value in previous['max_stat_to_equip']:
        number = new_ids.get(str(old_keys.get(stat)).lower())
        if item in gone and number:
            conn.execute('INSERT INTO max_stat_to_equip (item, stat, value)'
                         ' VALUES (?, ?, ?)', (item, number, value))
    for item, stat, value, low, high in previous['stats_of_item']:
        number = new_ids.get(str(old_keys.get(stat)).lower())
        if item in gone and number:
            conn.execute(
                'INSERT INTO stats_of_item (item, stat, value, min_value,'
                ' max_value) VALUES (?, ?, ?, ?, ?)',
                (item, number, value, low, high))
    for item, line, stat, value, elements in previous['stat_element_count']:
        number = new_ids.get(str(old_keys.get(stat)).lower())
        if item in gone and number:
            conn.execute(
                'INSERT INTO stat_element_count (item, line, stat, value,'
                ' elements) VALUES (?, ?, ?, ?, ?)',
                (item, line, number, value, elements))
    for item, slot, cap in previous['item_level_caps']:
        if item in gone:
            conn.execute('INSERT INTO item_level_caps (item, slot, cap)'
                         ' VALUES (?, ?, ?)', (item, slot, cap))
    for item, line, stat, base, per_level in previous['item_level_lines']:
        number = new_ids.get(str(old_keys.get(stat)).lower())
        if item in gone and number:
            conn.execute(
                'INSERT INTO item_level_lines (item, line, stat, base, per_level)'
                ' VALUES (?, ?, ?, ?, ?)', (item, line, number, base, per_level))
    for item, minimum, maximum in previous['item_shard_slots']:
        if item in gone:
            conn.execute('INSERT INTO item_shard_slots (item, minimum, maximum)'
                         ' VALUES (?, ?, ?)', (item, minimum, maximum))
    return len(gone)


def socketed_positions(dump):
    """The positions at least one item with sockets is worn in."""
    return {position for item in dump['equipment']
            if (item.get('shard_slots') or [0, 0])[1]
            for position in item['positions'] if position in GEAR}


def write_shards(conn, item, effects, stat_ids, socketed, counts):
    """Fill the rune tables from a rune of the dump and the client's effect ranges."""
    rune_id = item['id']
    shard = item['shard']
    curve, requirement = shard['curve'] or [], shard['requirement'] or []
    if not curve or len(curve) != len(requirement):
        raise ValueError('rune %d: %d costs for %d item levels'
                         % (rune_id, len(curve), len(requirement)))
    positions = []
    for number in shard['double_positions'] or ():
        position = EQUIPMENT_POSITION_IDS.get(number)
        if position is None:
            raise ValueError('rune %d doubles on position %r, which the client enum'
                             ' map lacks' % (rune_id, number))
        if position not in socketed:
            raise ValueError('rune %d doubles on %s, which no item with sockets fills'
                             % (rune_id, position))
        positions.append(position)
    actions = {line['action'] for line in item['lines']}
    if len(actions) != 1:
        raise ValueError('rune %d mixes actions %s' % (rune_id, sorted(actions)))
    keys = {line.get('stat') for line in item['lines']}
    if len(keys) != 1:
        raise ValueError('rune %d has lines of different characteristics' % rune_id)
    key = keys.pop()
    covered = collections.Counter()
    lines = []
    for line in item['lines']:
        effect = (effects or {}).get(line['effect'])
        if effect is None:
            raise ValueError('rune %d: effect %r is not in the client effect table'
                             % (rune_id, line['effect']))
        low, high = effect.get('min_level'), effect.get('max_level')
        if low is None or high is None:
            raise ValueError('rune %d: effect %d has no level range'
                             % (rune_id, line['effect']))
        params = line['params']
        if len(params) < 2:
            raise ValueError('rune %d: effect %d has no slope' % (rune_id, line['effect']))
        for tier in range(low, high + 1):
            covered[tier] += 1
        lines.append((line['effect'], low, high, params[0], params[1]))
    for tier in range(1, len(curve) + 1):
        if covered[tier] != 1:
            raise ValueError('rune %d: tier %d is covered by %d lines'
                             % (rune_id, tier, covered[tier]))
    conn.execute('INSERT INTO shards (id, colour, action, stat) VALUES (?, ?, ?, ?)',
                 (rune_id, shard['color'], actions.pop(),
                  stat_ids[key] if key else None))
    counts['shards'] += 1
    if not key:
        counts['shards with no stat'] += 1
    for language in LANGUAGES:
        name = item['name'].get(language)
        if name:
            conn.execute('INSERT INTO shard_names (shard, language, name)'
                         ' VALUES (?, ?, ?)', (rune_id, language, name))
    for position in positions:
        conn.execute('INSERT INTO shard_double_positions (shard, position)'
                     ' VALUES (?, ?)', (rune_id, position))
        counts['shard double positions'] += 1
    for level, (cost, needed) in enumerate(zip(curve, requirement), start=1):
        conn.execute('INSERT INTO shard_levels (shard, level, cost, item_level)'
                     ' VALUES (?, ?, ?, ?)', (rune_id, level, cost, needed))
        counts['shard levels'] += 1
    for row in lines:
        conn.execute('INSERT INTO shard_lines (shard, effect, min_level, max_level,'
                     ' base, per_level) VALUES (?, ?, ?, ?, ?, ?)', (rune_id,) + row)
        counts['shard lines'] += 1


def write_breeds(conn, dump, stat_ids, counts, defaults=None):
    """Fill breeds and their base values; the set of breed names.

    A stat the breed record does not carry starts at the client's default for that
    characteristic, when it is not 0.
    """
    by_key = {key.lower(): number for key, number in stat_ids.items()}
    start = {}
    for name, value in sorted((defaults or {}).items()):
        key = wakfu_aptitudes.TEMPLATE_ALIASES.get(name, name).lower()
        if value and key in by_key:
            start[key] = value
    names = set()
    skipped = set()
    for breed in dump.get('breeds') or ():
        conn.execute('INSERT INTO breeds (id, name) VALUES (?, ?)',
                     (breed['id'], breed['name']))
        names.add(breed['name'])
        counts['breeds'] += 1
        base = {field.lower(): value for field, value in breed['base'].items()}
        for key, value in start.items():
            base.setdefault(key, value)
        for field, value in sorted(base.items()):
            number = by_key.get(field)
            if number is None:
                skipped.add(field.upper())
                continue
            conn.execute('INSERT INTO breed_base_values (breed, stat, value)'
                         ' VALUES (?, ?, ?)', (breed['id'], number, value))
            counts['breed base values'] += 1
    if skipped:
        print('breed fields with no stat row, not stored: %s'
              % ', '.join(sorted(skipped)))
    return names


def with_fallback_languages(by_language):
    """A copy of {language: table} with each CLIENT_TEXT_FALLBACK language it lacks."""
    out = dict(by_language)
    for language, source in CLIENT_TEXT_FALLBACK.items():
        if language not in out and source in out:
            out[language] = out[source]
    return out


def write_labels(conn, dump, counts):
    """Fill criteria_labels and nations, every language the client carries, de from en."""
    labels = with_fallback_languages(dump.get('labels') or {})
    nations = with_fallback_languages(dump.get('nations') or {})
    for language, table in sorted(labels.items()):
        for key, text in sorted(table.items()):
            conn.execute('INSERT INTO criteria_labels (key, language, text)'
                         ' VALUES (?, ?, ?)', (key, language, text))
            counts['criteria labels'] += 1
    for language, table in sorted(nations.items()):
        for ident, name in sorted(table.items(), key=lambda one: int(one[0])):
            conn.execute('INSERT INTO nations (id, language, name)'
                         ' VALUES (?, ?, ?)', (int(ident), language, name))
            counts['nations'] += 1


def screen(item, stat_keys, breed_names, gear_ids, counts):
    """The derivation of one item's EQUIP text, or None when it has none.

    Raises CriteriaError, naming the item, on anything the screen does not
    know: an unreviewed kind or property, a text that does not parse, a
    function outside the four classes or a shape the derivation refuses.
    """
    try:
        for kind in item.get('other_criteria') or {}:
            if kind not in wakfu_criteria.REVIEWED_KINDS:
                raise wakfu_criteria.CriteriaError(
                    'criteria kind %r is not reviewed' % kind)
        for number in item.get('properties') or ():
            if number not in wakfu_criteria.REVIEWED_PROPERTIES:
                raise wakfu_criteria.CriteriaError(
                    'property %r is not reviewed' % number)
        text = item.get('criteria')
        if not text:
            return None
        tree = wakfu_criteria.parse(text)
        for kind in {wakfu_criteria.classify(name)
                     for name in wakfu_criteria.functions(tree)}:
            counts['items with %s atoms' % kind] += 1
        return wakfu_criteria.derive(tree, stat_keys=stat_keys,
                                     breed_names=breed_names, item_ids=gear_ids)
    except wakfu_criteria.CriteriaError as error:
        raise wakfu_criteria.CriteriaError(
            'item %s: %s' % (item['id'], error)) from error


def write_conditions(conn, item, stat_ids, breed_names, gear_ids, counts):
    """Write what the client says about wearing one item."""
    item_id = item['id']
    by_key = {key.lower(): number for key, number in stat_ids.items()}
    derived = screen(item, set(by_key), breed_names, gear_ids, counts)
    for number in item.get('properties') or ():
        conn.execute('INSERT INTO item_properties (item, property) VALUES (?, ?)',
                     (item_id, number))
    for kind, other in sorted((item.get('other_criteria') or {}).items()):
        conn.execute('INSERT INTO item_other_criteria (item, kind, criteria)'
                     ' VALUES (?, ?, ?)', (item_id, kind, other))
    if derived is None:
        return
    conn.execute('INSERT INTO item_criteria (item, criteria) VALUES (?, ?)',
                 (item_id, item['criteria']))
    if derived.unusable:
        conn.execute('INSERT INTO unusable_items (item) VALUES (?)', (item_id,))
    for name in derived.classes:
        conn.execute('INSERT INTO item_class_conditions (item, class)'
                     ' VALUES (?, ?)', (item_id, name))
    for key, value in sorted(derived.min_stats.items()):
        conn.execute('INSERT INTO min_stat_to_equip (item, stat, value)'
                     ' VALUES (?, ?, ?)', (item_id, by_key[key], value))
    for key, value in sorted(derived.max_stats.items()):
        conn.execute('INSERT INTO max_stat_to_equip (item, stat, value)'
                     ' VALUES (?, ?, ?)', (item_id, by_key[key], value))
    for other in derived.worn_with:
        conn.execute('INSERT INTO items_worn_with (item, other) VALUES (?, ?)',
                     (item_id, other))
    for other in derived.not_worn_with:
        conn.execute('INSERT INTO items_not_worn_together (item, other)'
                     ' VALUES (?, ?)', (item_id, other))
    if derived.min_level is not None:
        conn.execute('INSERT INTO min_level_to_equip (item, value) VALUES (?, ?)',
                     (item_id, derived.min_level))
    if derived.max_level is not None:
        conn.execute('INSERT INTO max_level_to_equip (item, value) VALUES (?, ?)',
                     (item_id, derived.max_level))
    for condition in derived.state:
        conn.execute('INSERT INTO item_state_conditions (item, option, nation,'
                     ' operator, value) VALUES (?, ?, ?, ?, ?)',
                     (item_id, condition.option, condition.nation,
                      condition.operator, condition.value))
    counts['equip texts screened'] += 1


def find_client_tables(client_dir, version, name='tables.json'):
    """The `name` file of the client whose game version is that of `version`, or None."""
    wanted = '.'.join(version.split('.')[:3])
    found = []
    for path in sorted(Path(client_dir).glob('*/' + name)):
        with io.open(path, encoding='utf-8') as handle:
            payload = json.load(handle)
        if payload.get('game_version') == wanted:
            found.append(payload)
    if len(found) > 1:
        raise ValueError('%d decoded clients for game version %s under %s'
                         % (len(found), wanted, client_dir))
    return found[0] if found else None


ITEM_CONTAINERS = ('ITEM_EQUIP', 'ITEM_USE')


def write_client_tables(conn, tables, counts):
    """Fill the effect, state, ability and set tables from a decoded client."""
    item_ids = set(tables['item_ids'])
    effects = {effect['id']: effect for effect in tables['effects']}
    if any('criterion' not in effect for effect in effects.values()):
        raise ValueError('the decoded effects carry no criterion: decode the client again'
                         ' with get_wakfu_client.py')
    groups = {group['id']: group['effect_ids'] for group in tables['groups']}
    ability_categories = {one['id'] for one in tables['ability_categories']}
    roots = {effect['id'] for effect in effects.values()
             if effect['container_type'] in ITEM_CONTAINERS
             and effect['container_id'] in item_ids}
    for state in tables['states']:
        roots.update(state['effect_ids'])
    for ability in tables['abilities']:
        if ability['category'] not in ability_categories:
            raise ValueError('ability %d is in no category' % ability['id'])
        roots.update(ability['effect_ids'])
    for client_set in tables['sets']:
        for _pieces, effect_ids in client_set['bonuses']:
            roots.update(effect_ids)
    for spell in tables.get('spells', ()):
        roots.update(spell['effect_ids'])
    wanted, pending = set(), sorted(roots)
    while pending:
        ident = pending.pop()
        if ident in wanted:
            continue
        if ident not in effects:
            raise ValueError('effect %d is listed but not in the effect table' % ident)
        wanted.add(ident)
        pending.extend(groups.get(ident, ()))
    for ident in sorted(wanted):
        effect = effects[ident]
        conn.execute(
            'INSERT INTO effects (id, action, container_type, container,'
            ' root_container_type, normal_or_critical, area_shape, area_size,'
            ' params, criterion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (ident, effect['action_id'], effect['container_type'],
             effect['container_id'], effect['root_container_type'],
             effect['normal_or_critical'], effect['area_shape'],
             json.dumps(effect['area_size']), json.dumps(effect['params']),
             effect['criterion']))
        counts['effects'] += 1
        for position, member in enumerate(groups.get(ident, ())):
            conn.execute('INSERT INTO effect_groups (group_id, position, effect)'
                         ' VALUES (?, ?, ?)', (ident, position, member))
            counts['effects in groups'] += 1
        if ident in groups:
            counts['effect groups'] += 1
    for state in tables['states']:
        conn.execute('INSERT INTO states (id, key) VALUES (?, ?)',
                     (state['id'], state['bcw']))
        counts['states'] += 1
    for category in tables['ability_categories']:
        conn.execute('INSERT INTO ability_categories (id, unlock_levels,'
                     ' ability_ids) VALUES (?, ?, ?)',
                     (category['id'], json.dumps(category['unlock_levels']),
                      json.dumps(category['ability_ids'])))
        counts['ability categories'] += 1
    for ability in tables['abilities']:
        conn.execute('INSERT INTO abilities (id, category, ddl, cgi)'
                     ' VALUES (?, ?, ?, ?)',
                     (ability['id'], ability['category'], ability['ddL'],
                      ability['cgI']))
        counts['abilities'] += 1
    for client_set in tables['sets']:
        conn.execute('INSERT INTO client_sets (id, item_count) VALUES (?, ?)',
                     (client_set['id'], len(client_set['item_ids'])))
        counts['client sets'] += 1
        for position, ident in enumerate(client_set['item_ids']):
            conn.execute('INSERT INTO client_set_members (item_set, position, item)'
                         ' VALUES (?, ?, ?)', (client_set['id'], position, ident))
            counts['client set members'] += 1
            if ident not in item_ids:
                counts['client set members with no client item'] += 1
        for pieces, effect_ids in client_set['bonuses']:
            for ident in effect_ids:
                conn.execute('INSERT INTO set_bonuses (item_set, pieces, effect)'
                             ' VALUES (?, ?, ?)', (client_set['id'], pieces, ident))
                counts['set bonus effects'] += 1
        if client_set['bonuses']:
            counts['sets with a bonus entry'] += 1
    write_spells_pets_and_monsters(conn, tables, item_ids, counts)


# (insert statement, the text family of each text column, SQL of the ids that may have a text)
CLIENT_TEXT_TABLES = (
    ('INSERT INTO state_texts (state, language, name, description) VALUES (?, ?, ?, ?)',
     ('state_names', 'state_descriptions'), 'SELECT id FROM states'),
    ('INSERT INTO client_spell_texts (spell, language, name, description)'
     ' VALUES (?, ?, ?, ?)',
     ('spell_names', 'spell_descriptions'), 'SELECT id FROM client_spells'),
    ('INSERT INTO client_set_names (item_set, language, name) VALUES (?, ?, ?)',
     ('set_names',), 'SELECT id FROM client_sets'),
    ('INSERT INTO client_monster_names (monster, language, name) VALUES (?, ?, ?)',
     ('monster_names',), 'SELECT id FROM monsters'),
    ('INSERT INTO monster_family_names (family, language, name) VALUES (?, ?, ?)',
     ('monster_family_names',), 'SELECT DISTINCT family FROM monsters'),
    ('INSERT INTO ability_names (ability, language, name) VALUES (?, ?, ?)',
     ('ability_names',), 'SELECT id FROM abilities'),
    ('INSERT INTO ability_category_names (category, language, name) VALUES (?, ?, ?)',
     ('ability_category_names',), 'SELECT id FROM ability_categories'),
    ('INSERT INTO effect_texts (effect, language, text) VALUES (?, ?, ?)',
     ('effect_texts',), 'SELECT id FROM effects'),
    ('INSERT INTO action_texts (action, language, text) VALUES (?, ?, ?)',
     ('action_texts',), 'SELECT DISTINCT action FROM effects'),
)
# (insert statement, the text family, whether its ids are numbers): every id or key of the
# family is written, whatever the parent tables hold: job_names holds 14 of the 15 jobs
# and breeds 18 of the 19 classes
CLIENT_FREE_TEXT_TABLES = (
    ('INSERT INTO client_job_names (job, language, name) VALUES (?, ?, ?)',
     'job_names', True),
    ('INSERT INTO client_breed_names (breed, language, name) VALUES (?, ?, ?)',
     'breed_names', True),
    ('INSERT INTO client_breed_texts (key, language, text) VALUES (?, ?, ?)',
     'breed_texts', False),
    ('INSERT INTO client_aptitude_texts (key, language, text) VALUES (?, ?, ?)',
     'aptitude_texts', False),
    ('INSERT INTO client_enchantment_texts (key, language, text) VALUES (?, ?, ?)',
     'enchantment_texts', False),
    ('INSERT INTO client_item_type_names (item_type, language, name) VALUES (?, ?, ?)',
     'item_type_names', True),
)
# Wakfu has no German
CLIENT_TEXT_FALLBACK = {'de': 'en'}


def write_client_texts(conn, texts, counts):
    """Fill the client's name and text tables, pairing each text with its row by id."""
    families = texts['texts']
    for sql, family, numeric in CLIENT_FREE_TEXT_TABLES:
        table = sql.split()[2]
        by_language = families.get(family)
        if by_language is None:
            counts['texts family missing: ' + family] += 1
            continue
        for language in LANGUAGES:
            source = by_language.get(CLIENT_TEXT_FALLBACK.get(language, language), {})
            for ident, text in sorted(source.items()):
                conn.execute(sql, (int(ident) if numeric else ident, language, text))
                counts[table.replace('_', ' ')] += 1
    for sql, columns, parents_sql in CLIENT_TEXT_TABLES:
        table = sql.split()[2]
        parents = sorted(row[0] for row in conn.execute(parents_sql))
        known = {str(ident) for ident in parents}
        for language in LANGUAGES:
            source = CLIENT_TEXT_FALLBACK.get(language, language)
            for ident in parents:
                values = [families[family].get(source, {}).get(str(ident))
                          for family in columns]
                if any(value is not None for value in values):
                    conn.execute(sql, (ident, language, *values))
                    counts[table.replace('_', ' ')] += 1
        for family in columns:
            unmatched = set()
            for by_id in families[family].values():
                unmatched.update(set(by_id) - known)
            if unmatched:
                counts['texts naming no row: ' + family] += len(unmatched)


def write_spells_pets_and_monsters(conn, tables, item_ids, counts):
    """Fill the spell, pet, mount, monster and loot list tables of a decoded client."""
    for spell in tables.get('spells', ()):
        conn.execute(
            'INSERT INTO client_spells (id, breed, ap, mp, wp, range_min, range_max,'
            ' element, unlock_level, max_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (spell['id'], spell['breed'], spell['ap'], spell['mp'], spell['wp'],
             spell['range_min'], spell['range_max'], spell['element'],
             spell['unlock_level'], spell['max_level']))
        counts['client spells'] += 1
        for position, effect in enumerate(spell['effect_ids']):
            conn.execute('INSERT INTO client_spell_effects (spell, position, effect)'
                         ' VALUES (?, ?, ?)', (spell['id'], position, effect))
            counts['client spell effects'] += 1
    for pet in tables.get('pets', ()):
        item = pet['item'] if pet['item'] in item_ids else None
        conn.execute('INSERT INTO pets (id, item, eoq, eop, emm) VALUES (?, ?, ?, ?, ?)',
                     (pet['id'], item, pet['eoq'], pet['eop'], pet['emm']))
        counts['pets'] += 1
    for mount in tables.get('mounts', ()):
        item = mount['item'] if mount['item'] in item_ids else None
        conn.execute('INSERT INTO mounts (id, item, eop, emm, eoq) VALUES (?, ?, ?, ?, ?)',
                     (mount['id'], item, mount['eop'], mount['emm'], mount['eoq']))
        counts['mounts'] += 1
        if item is None:
            counts['mounts without an item'] += 1
    list_ids = {one['id'] for one in tables.get('loot_lists', ())}
    for loot_list in tables.get('loot_lists', ()):
        conn.execute('INSERT INTO loot_lists (id) VALUES (?)', (loot_list['id'],))
        counts['loot lists'] += 1
        for position, row in enumerate(loot_list['rows']):
            if row['is_list'] and row['target'] not in list_ids:
                raise ValueError('loot list %d names the list %d, which is not there'
                                 % (loot_list['id'], row['target']))
            item, sub_list = (None, row['target']) if row['is_list'] \
                else (row['target'], None)
            conn.execute(
                'INSERT INTO loot_list_rows (loot_list, position, id, item, sub_list,'
                ' rate, quantity_min, quantity_max) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (loot_list['id'], position, row['id'], item, sub_list, row['rate'],
                 row['quantity_min'], row['quantity_max']))
            counts['loot list rows'] += 1
    for monster in tables.get('monsters', ()):
        conn.execute('INSERT INTO monsters (id, family) VALUES (?, ?)',
                     (monster['id'], monster['family']))
        counts['monsters'] += 1
        for position, drop in enumerate(monster['drops']):
            conn.execute(
                'INSERT INTO monster_drops (monster, position, item, rate, quantity_min,'
                ' quantity_max) VALUES (?, ?, ?, ?, ?, ?)',
                (monster['id'], position, drop['item'], drop['rate'],
                 drop['quantity_min'], drop['quantity_max']))
            counts['monster drops'] += 1
        for position, harvest in enumerate(monster['harvests']):
            if harvest['loot_list'] not in list_ids:
                raise ValueError('monster %d harvests the list %d, which is not there'
                                 % (monster['id'], harvest['loot_list']))
            conn.execute(
                'INSERT INTO monster_harvests (monster, position, loot_list, condition)'
                ' VALUES (?, ?, ?, ?)',
                (monster['id'], position, harvest['loot_list'], harvest['condition']))
            counts['monster harvests'] += 1


def write_client_pictures(conn, tables, decoded, counts):
    """Fill client_pictures: the file number or key the client draws for each row.

    An item gfx or a monster picture of 0 or less names no file, and neither does an
    empty state key.
    """
    def add(family, ident, picture):
        conn.execute('INSERT INTO client_pictures (family, id, picture) VALUES (?, ?, ?)',
                     (family, ident, str(picture)))
        counts['pictures: ' + family] += 1

    client_items = {int(ident) for ident in decoded['items']}
    for ident, item in sorted(decoded['items'].items(), key=lambda one: int(one[0])):
        if item['gfx'] > 0:
            add('item', int(ident), item['gfx'])
    for item, gfx in conn.execute('SELECT item, gfx FROM item_picture ORDER BY item').fetchall():
        if item not in client_items:
            add('item', item, gfx)
    for spell in tables['spells']:
        add('spell', spell['id'], spell['icon'])
    for state in tables['states']:
        if state['bcw']:
            add('state', state['id'], state['bcw'])
    for ability in tables['abilities']:
        add('ability', ability['id'], ability['cgI'])
    for monster in tables['monsters']:
        if monster['picture'] > 0:
            add('monster', monster['id'], monster['picture'])
    for family in sorted({monster['family'] for monster in tables['monsters']}):
        add('monster_family', family, family)
    for (breed,) in conn.execute('SELECT id FROM breeds ORDER BY id').fetchall():
        add('class', breed, breed)


def build(dump_path, db_path, out_dir='itemscraper/wakfu_raw', client_dir=None):
    # Built beside the database and swapped in last, so a failure keeps the old one.
    # The name is the one load_item_db.py uses, which .gitignore covers
    temp_path = db_path.with_name('%s.tmp.%d' % (db_path.name, os.getpid()))
    for stale in db_path.parent.glob(db_path.name + '.tmp.*'):
        try:
            if stale == temp_path or time.time() - stale.stat().st_mtime > 3600:
                stale.unlink()
        except OSError:
            pass
    conn = sqlite3.connect(str(temp_path))
    try:
        counts = build_into(dump_path, db_path, conn, out_dir, client_dir)
        conn.commit()
    except BaseException:
        conn.close()
        temp_path.unlink()
        raise
    conn.close()
    os.replace(str(temp_path), str(db_path))
    return counts


def build_into(dump_path, db_path, conn, out_dir, client_dir):
    with io.open(dump_path, encoding='utf-8') as handle:
        dump = json.load(handle)
    sets = read_sets(out_dir, dump['version'])

    previous = read_previous(db_path)
    for statement in dofus_schema():
        conn.execute(statement)
    create_tables(conn)
    counts = collections.Counter()

    # The item types, under Ankama's own ids and names, with the positions each
    # one fills beside them. A Ring has two rows there and everything else has
    # one, which is the slot count Dofus keeps by hand in
    # TYPE_NAME_TO_SLOT_NUMBER.
    types = {}
    for item in dump['equipment']:
        positions = sorted(p for p in item['positions'] if p in GEAR)
        if not positions:
            continue
        names = {language: singular(text)
                 for language, text in (item.get('type_name') or {}).items()}
        types.setdefault(item['type_id'], (names, positions))
    for type_id, (names, positions) in sorted(types.items()):
        # A brace here means Ankama used a plural form this build has never
        # seen. Better to stop than to print "Anneau{[~1]?x:}" at a reader.
        for language, name in sorted(names.items()):
            if '{' in name or not name.strip():
                raise ValueError('type %d has no usable %s name: %r'
                                 % (type_id, language, name))
        if not names.get('en'):
            raise ValueError('type %d is not named in english' % type_id)
        conn.execute('INSERT INTO item_types (id, name) VALUES (?, ?)',
                     (type_id, names['en']))
        for language, name in sorted(names.items()):
            conn.execute('INSERT INTO item_type_names (item_type, language,'
                         ' name) VALUES (?, ?, ?)', (type_id, language, name))
        for position in positions:
            conn.execute('INSERT INTO item_type_position (item_type, position)'
                         ' VALUES (?, ?)', (type_id, position))
    counts['item types'] = len(types)

    stat_ids = {}
    for number, key in enumerate(sorted(WAKFU_STATS), start=1):
        stat_ids[key] = number
        conn.execute('INSERT INTO stats (id, name, key) VALUES (?, ?, ?)',
                     (number, stat_name(key), key.lower()))

    for set_id, names in sorted(sets.items()):
        conn.execute('INSERT INTO sets (id, name, ankama_id, dofustouch)'
                     ' VALUES (?, ?, ?, 0)',
                     (set_id, names.get('en'), set_id))
        for language, name in sorted(names.items()):
            conn.execute('INSERT INTO set_names (item_set, language, name)'
                         ' VALUES (?, ?, ?)', (set_id, language, name))

    code = find_client_tables(client_dir, dump['version'], 'client_code.json') \
        if client_dir else None
    if client_dir and code is None:
        print('no client_code.json for game version %s: decode the client again with'
              ' get_wakfu_client.py, the breeds start without control' % dump['version'])
    elif code is not None and 'characteristic_defaults' not in code:
        print('client_code.json holds no characteristic defaults: decode the client again'
              ' with get_wakfu_client.py')
    breed_names = write_breeds(conn, dump, stat_ids, counts,
                               (code or {}).get('characteristic_defaults'))
    write_labels(conn, dump, counts)
    gear_ids = {item['id'] for item in dump['equipment']
                if any(p in GEAR for p in item['positions'])}

    tables = find_client_tables(client_dir, dump['version']) if client_dir else None
    caps = level_caps(tables)
    effect_table = {effect['id']: effect for effect in tables['effects']} if tables else None
    socketed = socketed_positions(dump)

    written = set()
    for item in dump['equipment']:
        positions = [p for p in item['positions'] if p in GEAR]
        if item.get('shard') and tables is not None:
            write_shards(conn, item, effect_table, stat_ids, socketed, counts)
        if not positions:
            counts['not gear'] += 1
            continue
        leveled = item['id'] in caps
        if not leveled and any(p in COMPANION_SLOTS for p in positions) and any(
                line.get('stat') and len(line['params']) > 1 and line['params'][1]
                for line in item['lines']):
            print('leveled item %d %s has no cap in the client tables, left out'
                  % (item['id'], item['name'].get('en')))
            counts['leveled item without a cap'] += 1
            continue
        # The item points at its type; where that type is worn is one join
        # away in item_type_position, so nothing about the slot is copied onto
        # the item and the two can never disagree.
        item_id = item['id']
        # A set the encyclopedia no longer has a page for keeps its items
        # and simply goes unnamed, rather than the items losing their set.
        set_id = item.get('set_id')
        if set_id and set_id not in sets:
            counts['set with no page'] += 1
            set_id = None
        conn.execute(
            'INSERT INTO items (id, name, level, type, item_set, ankama_id,'
            ' ankama_type, removed, dofustouch, skin)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, NULL)',
            (item_id, item['name'].get('en'), item['level'],
             item['type_id'], set_id, item_id, 'equipment'))
        written.add(item_id)
        counts['items'] += 1
        if set_id:
            counts['items in a set'] += 1
        minimum, maximum = item.get('shard_slots') or [0, 0]
        conn.execute('INSERT INTO item_shard_slots (item, minimum, maximum)'
                     ' VALUES (?, ?, ?)', (item_id, minimum or 0, maximum or 0))
        if maximum:
            counts['items with sockets'] += 1
        if item.get('gfx_id'):
            conn.execute('INSERT INTO item_picture (item, gfx) VALUES (?, ?)',
                         (item_id, item['gfx_id']))
        else:
            counts['no picture'] += 1

        for language in LANGUAGES:
            name = item['name'].get(language)
            if name:
                conn.execute('INSERT INTO item_names (item, language, name)'
                             ' VALUES (?, ?, ?)', (item_id, language, name))

        for flag in (TWO_HANDED_FLAG, 'relic', 'epic'):
            if flag == TWO_HANDED_FLAG and item['two_handed']:
                conn.execute('INSERT INTO item_flags (item, flag)'
                             ' VALUES (?, ?)', (item_id, flag))
            elif item['exclusive'] == flag:
                conn.execute('INSERT INTO item_flags (item, flag)'
                             ' VALUES (?, ?)', (item_id, flag))
        if len(positions) > 1:
            conn.execute('INSERT INTO item_flags (item, flag) VALUES (?, ?)',
                         (item_id, 'both_hands'))

        if item['rarity'] is not None:
            conn.execute('INSERT INTO item_rarity (item, rarity)'
                         ' VALUES (?, ?)', (item_id, item['rarity']))
            counts['rarity %s' % RARITIES.get(item['rarity'], '?')] += 1

        write_conditions(conn, item, stat_ids, breed_names, gear_ids, counts)

        if leveled:
            slot, cap = caps[item_id]
            if slot not in positions:
                raise ValueError('item %d is a %s row of the client but is worn in %s'
                                 % (item_id, slot, positions))
            conn.execute('INSERT INTO item_level_caps (item, slot, cap) VALUES (?, ?, ?)',
                         (item_id, slot, cap))
            counts['leveled items'] += 1

        for line_number, line in enumerate(item['lines']):
            key = line.get('stat')
            if not key:
                counts['line: %s' % line.get('not_a_stat')] += 1
                continue
            if leveled:
                check_leveled_line(item_id, line)
                base, per_level = line['params'][0], line['params'][1]
                conn.execute(
                    'INSERT INTO item_level_lines (item, line, stat, base, per_level)'
                    ' VALUES (?, ?, ?, ?, ?)',
                    (item_id, line_number, stat_ids[key], base, per_level))
                counts['leveled lines'] += 1
                value = level_value(base, per_level, cap)
            else:
                value = int(line['value'])
            if not value:
                counts['line worth nothing'] += 1
                continue
            conn.execute(
                'INSERT INTO stats_of_item (item, stat, value, min_value,'
                ' max_value) VALUES (?, ?, ?, ?, ?)',
                (item_id, stat_ids[key], value, value, value))
            counts['stat lines'] += 1
            if line.get('elements'):
                # Named in full so structure.py can check the two tables
                # against each other instead of trusting a row order.
                conn.execute(
                    'INSERT INTO stat_element_count (item, line, stat, value,'
                    ' elements) VALUES (?, ?, ?, ?, ?)',
                    (item_id, line_number, stat_ids[key], value,
                     line['elements']))
                counts['spread over elements'] += 1

    decoded = find_client_tables(client_dir, dump['version'], 'decoded.json') \
        if tables is not None else None
    if tables is None:
        print('client tables not found for game version %s, the effect and rune tables'
              ' stay empty' % dump['version'])
    else:
        write_client_tables(conn, tables, counts)
        texts = find_client_tables(client_dir, dump['version'], 'texts.json')
        if texts is None:
            print('client texts not found for %s under %s: the name tables stay empty'
                  % (dump['version'], client_dir))
        else:
            write_client_texts(conn, texts, counts)

    counts['removed upstream, kept'] = keep_removed(
        conn, previous, written, stat_ids, set(sets),
        set(types)) if previous else 0
    if tables is not None and decoded is None:
        print('client pictures not found for %s under %s: the picture table stays empty'
              % (dump['version'], client_dir))
    if tables is not None and decoded is not None:
        write_client_pictures(conn, tables, decoded, counts)
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', default='itemscraper/transformed_wakfu.json')
    parser.add_argument('--db', default=str(WAKFU_DB))
    parser.add_argument('--out', default='itemscraper/wakfu_raw',
                        help='where get_sets_wakfu.py wrote the set names')
    parser.add_argument('--client', default='itemscraper/wakfu_client',
                        help='where get_wakfu_client.py wrote the decoded client')
    args = parser.parse_args(argv)

    dump_path = Path(args.dump)
    if not dump_path.exists():
        parser.error('%s is missing; run itemscraper/get_items_wakfu.py first'
                     % dump_path)
    counts = build(dump_path, Path(args.db), args.out, args.client)
    print('wrote %s' % args.db)
    print('kept %d items this build no longer has, flagged removed'
          % counts['removed upstream, kept'])
    for name, count in sorted(counts.items()):
        print('   %-28s %6d' % (name, count))
    return 0


if __name__ == '__main__':
    sys.exit(main())
