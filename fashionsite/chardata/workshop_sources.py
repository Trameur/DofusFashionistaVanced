# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Where a workshop resource can be farmed, and the craft job it needs.

Reuses `item_sources.get_source_ankama_ids` (cached per version) for the
"crafted" flag, and the same drop-lookup SQL shape as `encyclopedia_view`'s
resource and item pages, batched for many keys or items at once.
"""

import sqlite3

from chardata.encyclopedia_view import (
    _drop_conditions_text, _drop_level_text, _monster_level_spans, _monster_ui_text)
from chardata.item_sources import get_source_ankama_ids
from chardata.official_site import get_monster_link
from fashionistapulp.fashionista_config import get_items_db_path

MAX_SOURCE_KEYS_PER_REQUEST = 60
MAX_MONSTERS_PER_RESOURCE = 3
RESOURCE_SUBTYPE = 'resources'
BASE_JOB_ANKAMA_ID = 1
# Retro's item_craft_jobs.level is 0 on every row: the data has no level to show.
NO_LEVEL_VERSIONS = ('retro',)


def _table_exists(cursor, name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
    return cursor.fetchone() is not None


def stock_key(ankama_id, subtype):
    return '%d:%s' % (ankama_id, subtype)


def get_resource_sources(keys, game_version, language):
    """{'<ankama_id>:<subtype>': {'monsters': [...], 'crafted': bool}}.

    `keys` is an iterable of (ankama_id, subtype) pairs, at most
    MAX_SOURCE_KEYS_PER_REQUEST long (the caller enforces the limit).
    'monsters' holds up to MAX_MONSTERS_PER_RESOURCE entries, best drop rate
    first: {name, rate, url, level, has_conditions, conditions_text}.
    Runs a small constant number of SQL statements against the version's
    item DB, regardless of how many keys are asked for.
    """
    keys = list(dict.fromkeys(
        (int(ankama_id), str(subtype)) for ankama_id, subtype in keys))
    keys = keys[:MAX_SOURCE_KEYS_PER_REQUEST]
    result = {stock_key(a, s): {'monsters': [], 'crafted': False} for a, s in keys}
    if not keys:
        return result

    craftable_ids = get_source_ankama_ids(game_version)['craftable']
    for ankama_id, subtype in keys:
        if ankama_id in craftable_ids:
            result[stock_key(ankama_id, subtype)]['crafted'] = True

    resource_ids = sorted({a for a, s in keys if s == RESOURCE_SUBTYPE})
    if not resource_ids:
        return result

    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        if not _table_exists(cursor, 'resource_drops'):
            return result

        placeholders = ','.join('?' * len(resource_ids))
        drop_rows = cursor.execute(
            "SELECT resource_ankama_id, monster_ankama_id, rate, conditions "
            "FROM resource_drops WHERE resource_ankama_id IN (%s) "
            "ORDER BY resource_ankama_id, rate DESC" % placeholders,
            resource_ids).fetchall()
        if not drop_rows:
            return result

        monster_ids = sorted({row[1] for row in drop_rows})
        name_placeholders = ','.join('?' * len(monster_ids))
        name_rows = cursor.execute(
            "SELECT monster_ankama_id, language, name FROM monster_names "
            "WHERE monster_ankama_id IN (%s) AND language IN (?, 'en')"
            % name_placeholders, monster_ids + [language]).fetchall()
        level_spans = _monster_level_spans(cursor, monster_ids)
    except Exception:
        return result
    finally:
        if conn is not None:
            conn.close()

    names_by_id = {}
    for monster_id, lang, name in name_rows:
        names_by_id.setdefault(monster_id, {})[lang] = name

    drops_ui = _monster_ui_text()
    level_label = drops_ui['level_label']

    by_resource = {}
    for resource_id, monster_id, rate, conditions in drop_rows:
        by_resource.setdefault(resource_id, []).append((monster_id, rate, conditions))

    for ankama_id, subtype in keys:
        if subtype != RESOURCE_SUBTYPE:
            continue
        rows = by_resource.get(ankama_id)
        if not rows:
            continue
        monsters = []
        for monster_id, rate, conditions in rows[:MAX_MONSTERS_PER_RESOURCE]:
            names = names_by_id.get(monster_id, {})
            monster_name = names.get(language) or names.get('en') or ('#%s' % monster_id)
            span = level_spans.get(monster_id)
            conditions_text = _drop_conditions_text(conditions, drops_ui)
            if conditions and conditions_text is None:
                conditions_text = drops_ui['drop_conditions_label']
            monsters.append({
                'name': monster_name,
                'rate': rate,
                'url': get_monster_link(monster_id, monster_name, game_version),
                'level': _drop_level_text(span, level_label),
                'has_conditions': bool(conditions),
                'conditions_text': conditions_text,
            })
        result[stock_key(ankama_id, subtype)]['monsters'] = monsters

    return result


def get_item_craft_jobs(item_ids, game_version, language):
    """Craft job label per item, plus the highest level needed per job.

    `item_ids` are internal structure ids (already resolved through
    `Structure.current_item_id` by the caller). Returns:

      items    {item_id: {'job_name': str, 'level': int or None}}
      summary  [{'job_name': str, 'level': int or None}, ...] sorted by name

    Job 1 ("Base") is Ankama's placeholder and is never returned. Retro's
    recipe levels are all 0 in the data, so its 'level' is always None.
    """
    item_ids = sorted({i for i in item_ids if i is not None})
    empty = {'items': {}, 'summary': []}
    if not item_ids:
        return empty

    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        if not _table_exists(cursor, 'item_craft_jobs'):
            return empty
        placeholders = ','.join('?' * len(item_ids))
        rows = cursor.execute(
            """
            SELECT cj.item, cj.job_ankama_id, cj.level,
                   (SELECT name FROM job_names
                    WHERE job_ankama_id = cj.job_ankama_id AND language = ?),
                   (SELECT name FROM job_names
                    WHERE job_ankama_id = cj.job_ankama_id AND language = 'en')
            FROM item_craft_jobs cj
            WHERE cj.item IN (%s) AND cj.job_ankama_id != ?
            """ % placeholders, [language] + item_ids + [BASE_JOB_ANKAMA_ID]).fetchall()
    except Exception:
        return empty
    finally:
        if conn is not None:
            conn.close()

    hide_level = game_version in NO_LEVEL_VERSIONS
    items = {}
    by_job = {}
    for item_id, job_ankama_id, level, name_loc, name_en in rows:
        job_name = name_loc or name_en
        if not job_name:
            continue
        items[item_id] = {'job_name': job_name, 'level': None if hide_level else level}
        current = by_job.get(job_ankama_id)
        if current is None or (level or 0) > (current['level'] or 0):
            by_job[job_ankama_id] = {'job_name': job_name, 'level': level}

    summary = sorted(
        ({'job_name': entry['job_name'],
          'level': None if hide_level else entry['level']}
         for entry in by_job.values()),
        key=lambda entry: entry['job_name'].lower())
    return {'items': items, 'summary': summary}
