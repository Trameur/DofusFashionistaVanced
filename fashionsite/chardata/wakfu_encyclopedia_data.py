# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu encyclopedia's data: items, sets, recipes and conditions, read from sqlite only."""

import collections
import contextlib
import os
import re
import sqlite3
import threading
from pathlib import Path

from chardata import wakfu_game_text
from fashionistapulp import wakfu_criteria, wakfu_db
from fashionistapulp.fashion_util import strip_accents
from fashionistapulp.fashionista_config import get_items_db_path

GAME_VERSION = 'wakfu'
EFFECT_CACHE_SIZE = 4096
_LABEL_EDGES = re.compile(r'^[\s%+\-]+|[\s%+\-]+$')

Item = collections.namedtuple(
    'Item', 'id ankama_type level type rarity gfx set_id name search stats')
SetEntry = collections.namedtuple('SetEntry', 'id name size live_count min_level max_level')
Index = collections.namedtuple(
    'Index', 'language items by_id types rarities stats stat_keys sets sets_by_id')
Ingredient = collections.namedtuple('Ingredient', 'ankama_id subtype quantity name item_id')
Recipe = collections.namedtuple('Recipe', 'job level ingredients')
ItemDetail = collections.namedtuple(
    'ItemDetail', 'item type_name rarity_name lines conditions description recipe set_id '
                  'set_name display_level use_lines critical_use_lines')
SetDetail = collections.namedtuple(
    'SetDetail', 'id name size pieces other_count bonuses')

_lock = threading.Lock()
_indexes = {}
_effect_lines = collections.OrderedDict()
_held_stamp = [None]


def database_path():
    return get_items_db_path(GAME_VERSION)


def _stamp():
    path = database_path()
    return (str(path), os.stat(path).st_mtime_ns)


def connect():
    """A read-only connection; a missing database raises sqlite3.OperationalError."""
    uri = Path(database_path()).resolve().as_uri() + '?mode=ro'
    return sqlite3.connect(uri, uri=True)


def _normalized(text):
    return strip_accents(text or '').lower().strip()


def _build_index(conn, language):
    source = wakfu_game_text.TextSource(conn, language)
    names = {}
    for fallback in (wakfu_game_text.FALLBACK_LANGUAGE, language):
        names.update(conn.execute(
            'SELECT item, name FROM item_names WHERE language = ?', (fallback,)).fetchall())
    stat_keys = dict(conn.execute('SELECT id, key FROM stats').fetchall())
    stats = collections.defaultdict(dict)
    for item, stat, value in conn.execute('SELECT item, stat, value FROM stats_of_item'):
        key = stat_keys[stat]
        stats[item][key] = stats[item].get(key, 0) + value
    rarity = dict(conn.execute('SELECT item, rarity FROM item_rarity').fetchall())
    gfx = dict(conn.execute('SELECT item, gfx FROM item_picture').fetchall())
    in_set = dict(conn.execute(
        'SELECT item, item_set FROM client_set_members').fetchall())
    items = []
    for row in conn.execute('SELECT id, ankama_type, level, type FROM items WHERE removed = 0'):
        item_id, ankama_type, level, item_type = row
        name = names.get(item_id) or ''
        items.append(Item(item_id, ankama_type, level or 0, item_type, rarity.get(item_id),
                          gfx.get(item_id), in_set.get(item_id), name, _normalized(name),
                          stats.get(item_id, {})))
    items.sort(key=lambda one: (-one.level, one.name.lower(), one.id))
    types = sorted(((item_type, source.type_name(item_type))
                    for item_type in {one.type for one in items}),
                   key=lambda one: (_normalized(one[1]), one[0]))
    rarities = sorted((one, source.rarity_name(one))
                      for one in {one.rarity for one in items if one.rarity is not None})
    labels = stat_labels(conn, language)
    used = {key for one in items for key in one.stats}
    shown = tuple(sorted(((key, labels[key]) for key in used if key in labels),
                         key=lambda one: _normalized(one[1])))
    by_id = {one.id: one for one in items}
    sets = _set_entries(conn, source, by_id)
    return Index(language, tuple(items), by_id, tuple(types), tuple(rarities), shown,
                 frozenset(stat_keys.values()), sets, {one.id: one for one in sets})


def _set_entries(conn, source, by_id):
    members = collections.defaultdict(list)
    for item_set, item in conn.execute(
            'SELECT item_set, item FROM client_set_members ORDER BY item_set, position'):
        members[item_set].append(item)
    entries = []
    for item_set, pieces in members.items():
        live = [by_id[one] for one in pieces if one in by_id]
        if not live:
            continue
        levels = [one.level for one in live]
        entries.append(SetEntry(item_set, source.set_name(item_set) or '', len(pieces),
                                len(live), min(levels), max(levels)))
    entries.sort(key=lambda one: (_normalized(one.name), one.id))
    return tuple(entries)


def _usable_label_text(text):
    return bool(text) and '\n' not in text and not re.search(r'\[#[23]\]|\[\$', text)


def stat_labels(conn, language):
    """{stat key: the game's label}: the text of an action that gives the stat, without its
    number. A text that needs more than one parameter is passed over, and when no action text
    is left the effect text that links itself to the stat through [#charac KEY] is used."""
    source = wakfu_game_text.TextSource(conn, language)
    keys = dict(conn.execute('SELECT id, key FROM stats').fetchall())
    candidates = collections.defaultdict(list)
    for stat, action in conn.execute(
            'SELECT stat, action FROM stat_actions WHERE positive_lines > 0'
            ' ORDER BY stat, primary_action DESC, positive_lines DESC, action'):
        candidates[stat].append(action)
    labels = {}
    for stat, actions in candidates.items():
        texts = [source.action_text(action) for action in actions]
        for action in actions:
            texts.extend(row[0] for row in conn.execute(
                'SELECT DISTINCT t.text FROM effect_texts t JOIN effects e ON e.id = t.effect'
                ' WHERE e.action = ? AND t.language = ? AND t.text LIKE ?',
                (action, language, '%[#charac ' + keys[stat].upper() + ']%')))
        chosen = next((one for one in texts if _usable_label_text(one)), None)
        if chosen is None:
            continue
        label = wakfu_game_text.format_text(chosen, [''])
        label = _LABEL_EDGES.sub('', wakfu_game_text.tidy(label))
        if label:
            labels[keys[stat]] = label
    return labels


def index(language):
    """The list index of one language, rebuilt when the database file changes."""
    stamp = _stamp()
    with _lock:
        for held in [one for one in _indexes if one[0] != stamp]:
            del _indexes[held]
        if stamp != _held_stamp[0]:
            _effect_lines.clear()
            _held_stamp[0] = stamp
        key = (stamp, language)
        if key not in _indexes:
            with contextlib.closing(connect()) as conn:
                _indexes[key] = _build_index(conn, language)
        return _indexes[key]


def filter_items(idx, criteria):
    """The items of an index that meet a dict of criteria, ordered.

    Keys: q (text), type, rarity, min_level, max_level, stats [(stat key, minimum)],
    orders [(key, 'asc' or 'desc')] where key is a stat key, 'level' or 'name'.
    """
    needle = _normalized(criteria.get('q') or '')
    item_type = criteria.get('type')
    rarity = criteria.get('rarity')
    minimum = criteria.get('min_level')
    maximum = criteria.get('max_level')
    wanted = list(criteria.get('stats') or ())
    found = []
    for one in idx.items:
        if item_type is not None and one.type != item_type:
            continue
        if rarity is not None and one.rarity != rarity:
            continue
        if minimum is not None and one.level < minimum:
            continue
        if maximum is not None and one.level > maximum:
            continue
        if needle and needle not in one.search:
            continue
        if any(one.stats.get(key, 0) < least for key, least in wanted):
            continue
        found.append(one)
    for key, direction in reversed(list(criteria.get('orders') or ())):
        reverse = direction != 'asc'
        if key == 'level':
            found.sort(key=lambda one: one.level, reverse=reverse)
        elif key == 'name':
            found.sort(key=lambda one: one.search, reverse=reverse)
        else:
            found.sort(key=lambda one: one.stats.get(key, 0), reverse=reverse)
    return found


def is_stat_key(idx, key):
    return key in idx.stat_keys


def _cached_lines(stamp, item_id, language, build, kind='worn'):
    key = (stamp, kind, item_id, language)
    with _lock:
        if key in _effect_lines:
            _effect_lines.move_to_end(key)
            return _effect_lines[key]
    value = build()
    with _lock:
        _effect_lines[key] = value
        while len(_effect_lines) > EFFECT_CACHE_SIZE:
            _effect_lines.popitem(last=False)
    return value


def _recipe(conn, source, item_id, by_id):
    job = conn.execute('SELECT job_ankama_id, level FROM item_craft_jobs WHERE item = ?',
                       (item_id,)).fetchone()
    rows = conn.execute(
        'SELECT ingredient_ankama_id, ingredient_subtype, quantity FROM item_recipes'
        ' WHERE item = ? ORDER BY position', (item_id,)).fetchall()
    if not rows:
        return None
    ingredients = tuple(
        Ingredient(ankama_id, subtype, quantity,
                   source.ingredient_name(ankama_id, subtype),
                   ankama_id if subtype == 'equipment' and ankama_id in by_id else None)
        for ankama_id, subtype, quantity in rows)
    return Recipe(source.job_name(job[0]) if job else None, job[1] if job else None,
                  ingredients)


def display_levels(conn):
    """{item id: the level its numbers are shown at}: the stored cap of a pet or a mount when
    it is above the item's level, the item's level otherwise."""
    caps = {}
    for item, cap in conn.execute('SELECT item, cap FROM item_level_caps'):
        caps[item] = max(caps.get(item, 0), cap or 0)
    return {item: max(level or 0, caps.get(item, 0)) for item, level in conn.execute(
        'SELECT id, level FROM items')}


def display_level(conn, item_id, level):
    row = conn.execute('SELECT MAX(cap) FROM item_level_caps WHERE item = ?',
                       (item_id,)).fetchone()
    return max(level or 0, (row[0] or 0) if row else 0)


def _conditions(source, criteria):
    try:
        return tuple(wakfu_game_text.condition_lines(source, criteria))
    except wakfu_criteria.CriteriaError:
        return (wakfu_game_text.Condition('', ('shape:criteria',)),)


def item_detail(item_id, language):
    """Everything the item page shows, or None for an unknown or removed item."""
    idx = index(language)
    item = idx.by_id.get(item_id)
    if item is None:
        return None
    stamp = _stamp()
    with contextlib.closing(connect()) as conn:
        source = wakfu_game_text.TextSource(conn, language)
        shown_level = display_level(conn, item.id, item.level)

        def build():
            return tuple(wakfu_game_text.item_lines(source, item.id, shown_level))
        lines = _cached_lines(stamp, item.id, language, build)

        def build_use():
            return tuple(wakfu_game_text.use_lines(source, item.id, shown_level))
        use_lines = _cached_lines(stamp, item.id, language, build_use, 'use')

        def build_critical_use():
            return tuple(wakfu_game_text.use_lines(source, item.id, shown_level, 'CRITICAL'))
        critical_use_lines = _cached_lines(stamp, item.id, language, build_critical_use,
                                           'use_critical')
        criteria = conn.execute('SELECT criteria FROM item_criteria WHERE item = ?',
                                (item.id,)).fetchone()
        conditions = _conditions(source, criteria[0]) if criteria else ()
        set_entry = idx.sets_by_id.get(item.set_id)
        return ItemDetail(item, source.type_name(item.type), source.rarity_name(item.rarity),
                          lines, conditions, source.description(item.id),
                          _recipe(conn, source, item.id, idx.by_id),
                          item.set_id if set_entry else None,
                          set_entry.name if set_entry else None, shown_level, use_lines,
                          critical_use_lines)


def set_detail(set_id, language):
    """The set page's data, or None when no live item belongs to the set."""
    idx = index(language)
    entry = idx.sets_by_id.get(set_id)
    if entry is None:
        return None
    with contextlib.closing(connect()) as conn:
        source = wakfu_game_text.TextSource(conn, language)
        members = [row[0] for row in conn.execute(
            'SELECT item FROM client_set_members WHERE item_set = ? ORDER BY position',
            (set_id,))]
        pieces = tuple(idx.by_id[one] for one in members if one in idx.by_id)
        level = max(one.level for one in pieces)
        bonuses = collections.OrderedDict()
        for count, effect in conn.execute(
                'SELECT pieces, effect FROM set_bonuses WHERE item_set = ?'
                ' ORDER BY pieces, effect', (set_id,)):
            lines = wakfu_game_text.bonus_lines(source, effect, level)
            if lines:
                bonuses.setdefault(count, []).extend(lines)
        return SetDetail(set_id, entry.name, entry.size, pieces,
                         len(members) - len(pieces),
                         tuple((count, tuple(lines)) for count, lines in bonuses.items()))


def reached_effects(conn):
    """The effects a live item wears or a set grants, groups expanded: (roots, reached ids)."""
    roots = [row[0] for row in conn.execute(
        "SELECT e.id FROM effects e JOIN items i ON i.id = e.container"
        " WHERE e.container_type = 'ITEM_EQUIP' AND i.removed = 0")]
    roots.extend(row[0] for row in conn.execute('SELECT effect FROM set_bonuses'))
    groups = {row[0] for row in conn.execute('SELECT DISTINCT group_id FROM effect_groups')}
    reached = set(roots)
    for root in roots:
        if root in groups:
            reached.update(one.id for one in wakfu_db.expand_effect(conn, root))
    return roots, reached


def census(conn):
    """The texts the live items and sets reach: {'actions': {action: effect count},
    'effects': reached ids, 'shapes': {(kind, id): [token shapes]}} where kind is 'action' or
    'effect' and a shape of None is a token the parser lacks."""
    _roots, reached = reached_effects(conn)
    actions = collections.Counter()
    for effect_id, action in conn.execute('SELECT id, action FROM effects'):
        if effect_id in reached:
            actions[action] += 1
    shapes = collections.defaultdict(list)
    for action in actions:
        for (text,) in conn.execute('SELECT text FROM action_texts WHERE action = ?',
                                    (action,)):
            shapes[('action', action)].extend(
                shape for shape, _token in wakfu_game_text.token_shapes(text))
    for effect_id, text in conn.execute('SELECT effect, text FROM effect_texts'):
        if effect_id in reached:
            shapes[('effect', effect_id)].extend(
                shape for shape, _token in wakfu_game_text.token_shapes(text))
    return {'actions': dict(actions), 'effects': reached, 'shapes': dict(shapes)}


def unsettled_tokens(conn):
    """[(kind, id, token shape)] for each token of a reached text the parser does not know."""
    found = []
    for (kind, ident), shapes in sorted(census(conn)['shapes'].items()):
        found.extend((kind, ident, shape) for shape in sorted(
            {one for one in shapes if one not in wakfu_game_text.KNOWN_SHAPES},
            key=str))
    return found

