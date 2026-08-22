#!/usr/bin/env python3
"""The "[!]" tag upstream puts in front of a name it could not translate.

It marks a language that falls back to French, not internal content: the French
row of the same name is always clean. A reader of the other four languages
should get the fallback, not the tag.

Run as a script to strip it from a version already stored:

    python itemscraper/sanitize_untranslated_tags.py --game-version dofus3
"""
from __future__ import annotations

TAG = '[!]'

# "[wip]" is the same kind of note on an unfinished text. It is stripped from
# descriptions only: on an item name it is what the default-exclusion guard
# reads to keep Ankama's own working content out of the pool.
WIP_TAG = '[wip]'


def clean_display_name(value):
    """Drop the tag from a name or a description, leaving everything else."""
    if not value or TAG not in value:
        return value
    return value.replace(TAG, '').strip()


def clean_description(value):
    """Same, plus the unfinished-text note that only descriptions carry."""
    value = clean_display_name(value)
    if not value:
        return value
    lowered = value.lower()
    while WIP_TAG in lowered:
        start = lowered.index(WIP_TAG)
        value = value[:start] + value[start + len(WIP_TAG):]
        lowered = value.lower()
    return value.strip()


def has_tag(value):
    return bool(value) and TAG in value


def text_columns(cursor, table):
    """Column names of `table` that can hold a display string."""
    columns = []
    for row in cursor.execute('PRAGMA table_info("%s")' % table):
        name, declared = row[1], (row[2] or '').upper()
        if 'CHAR' in declared or 'TEXT' in declared or 'CLOB' in declared or not declared:
            columns.append(name)
    return columns


def cleaner_for(column):
    """Descriptions also lose the unfinished-text note; names keep it."""
    return clean_description if 'description' in column.lower() else clean_display_name


def tagged_rows(conn):
    """Every (table, column, rowid, value) a cleaner would still change."""
    cursor = conn.cursor()
    tables = [row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%'")]
    found = []
    for table in tables:
        for column in text_columns(cursor, table):
            clean = cleaner_for(column)
            markers = [TAG] if clean is clean_display_name else [TAG, WIP_TAG]
            for marker in markers:
                try:
                    rows = cursor.execute(
                        'SELECT rowid, "%s" FROM "%s" WHERE "%s" LIKE ?'
                        % (column, table, column), ('%' + marker + '%',)).fetchall()
                except Exception:
                    continue
                for rowid, value in rows:
                    if clean(value) != value:
                        found.append((table, column, rowid, value))
    return found


def strip_tag_everywhere(conn):
    """Strip the notes from every stored display string. Returns the row count."""
    cursor = conn.cursor()
    stripped = 0
    for table, column, rowid, value in tagged_rows(conn):
        cursor.execute('UPDATE "%s" SET "%s" = ? WHERE rowid = ?'
                       % (table, column), (cleaner_for(column)(value), rowid))
        stripped += 1
    return stripped
