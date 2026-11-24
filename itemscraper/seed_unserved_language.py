# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Seed a language the early Touch channel no longer serves from the login channel's files on disk, wherever the English text did not move."""

from __future__ import annotations

import argparse
import json
import os
import sys

import touch_channels

ALL_LANGS = ('fr', 'en', 'es', 'pt', 'de')
SOURCE_LANG = 'en'

TEXT_AND_READ_FIELDS_BY_TABLE = {
    'Items': (('nameId', 'descriptionId'), ('id',)),
    'ItemSets': (('nameId',), ('id',)),
    'ItemTypes': (('nameId',), ('id',)),
    'Monsters': (('nameId',), ('id',)),
    'Recipes': (('jobName',), ('resultId', 'jobId', 'resultLevel')),
    'SubAreas': (('nameId',), ('id', 'areaId', 'level', 'monsters')),
}


def _path(channel, table, lang):
    return os.path.join(touch_channels.raw_dir(channel), '%s_%s.json' % (table, lang))


def _load(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def seed_table(early_source, login_source, login_lang, text_fields, carried):
    """{id: record} in the language: the login text where the English text of the id is unchanged, the early English text otherwise."""
    seeded = {}
    for key, record in early_source.items():
        if not isinstance(record, dict):
            continue
        before = login_source.get(key) or {}
        kept = login_lang.get(key) or {}
        out = {field: record[field] for field in carried if field in record}
        for field in text_fields:
            if field not in record:
                continue
            same = field in before and before[field] == record[field]
            out[field] = kept[field] if same and kept.get(field) else record[field]
        seeded[key] = out
    return seeded


def seed(channel, tables=None, langs=None):
    """Write the channel's file of each unserved language, and return {(table, lang): (rows, rows from login)}."""
    served = touch_channels.served_languages(channel)
    done = {}
    if not served:
        return done
    for lang in langs or ALL_LANGS:
        if lang in served or lang == 'fr':
            continue
        for table in tables or TEXT_AND_READ_FIELDS_BY_TABLE:
            text_fields, carried = TEXT_AND_READ_FIELDS_BY_TABLE[table]
            early_source = _load(_path(channel, table, SOURCE_LANG))
            login_source = _load(_path(touch_channels.DEFAULT_CHANNEL, table, SOURCE_LANG))
            login_lang = _load(_path(touch_channels.DEFAULT_CHANNEL, table, lang))
            if early_source is None or login_source is None or login_lang is None:
                print('  %s_%s: nothing to seed from, readers fall back to English'
                      % (table, lang))
                continue
            seeded = seed_table(early_source, login_source, login_lang, text_fields, carried)
            with open(_path(channel, table, lang), 'w', encoding='utf-8') as handle:
                json.dump(seeded, handle, ensure_ascii=False)
            from_login = sum(
                1 for key, row in seeded.items()
                if any(row.get(f) != early_source[key].get(f) for f in text_fields))
            done[(table, lang)] = (len(seeded), from_login)
            print('  %s_%s.json: %d rows, %d with the login %s text, the rest in English'
                  % (table, lang, len(seeded), from_login, lang))
    return done


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    touch_channels.add_channel_argument(parser)
    parser.add_argument('--tables', nargs='*', choices=sorted(TEXT_AND_READ_FIELDS_BY_TABLE), default=None)
    args = parser.parse_args(argv)
    if args.channel == touch_channels.DEFAULT_CHANNEL:
        print('  the login channel is the source of the seed, nothing to do')
        return 0
    seed(args.channel, args.tables)
    return 0


if __name__ == '__main__':
    sys.exit(main())
