#!/usr/bin/env python3
"""Fetch and decode the Wakfu client's item, breed, effect, set, state and ability tables, and label files.

    python itemscraper/get_wakfu_client.py
    python itemscraper/get_wakfu_client.py --from-install DIR --manifest PATH \\
        --client-version VERSION [--out itemscraper/wakfu_client]

The first form reads the current client from Ankama's CDN. The second reads
the launcher's install folder and needs no network: the manifest is the CDN's
one for that client, and every file must match both it and the install's own
manifest.json. A 403 or a 429 from the CDN stops the step and is never retried.
The files and what is decoded from them stay local and are never committed:
decoded.json holds the items, breeds and labels, tables.json the effects,
effect groups, item sets, states and abilities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cytrus_cdn  # noqa: E402
import wakfu_client  # noqa: E402

LANGUAGES = ('fr', 'en', 'es', 'pt')
ITEMS_JAR = 'contents/bdata/35.jar'
BREEDS_JAR = 'contents/bdata/86.jar'
LABEL_JARS = {language: 'contents/i18n/i18n_%s.jar' % language
              for language in LANGUAGES}
# Tables 29 effect groups, 36 item sets, 67 states, 68 static effects,
# 135 abilities, 136 fixed ability categories
TABLE_JARS = {number: 'contents/bdata/%d.jar' % number
              for number in (29, 36, 67, 68, 135, 136)}
FILES = (ITEMS_JAR, BREEDS_JAR) + tuple(LABEL_JARS.values()) + tuple(TABLE_JARS.values())
KEEP_VERSIONS = 2


class ClientError(Exception):
    pass


def game_version_of(client_version):
    """'1.93.1' for '6.0_1.93.1.5312.334'."""
    tail = client_version.split('_', 1)[-1]
    return '.'.join(tail.split('.')[:3])


def sha1_of(blob):
    return hashlib.sha1(blob).hexdigest()


def decode(folder, client_version, hashes):
    """The decoded.json payload of the 12 files in a folder."""
    items = wakfu_client.read_items(folder / ITEMS_JAR.rsplit('/', 1)[1])
    breeds = wakfu_client.read_breeds(folder / BREEDS_JAR.rsplit('/', 1)[1])
    labels, nations = {}, {}
    for language, path in LABEL_JARS.items():
        labels[language], nations[language] = wakfu_client.read_labels(
            folder / path.rsplit('/', 1)[1], language)
    return {
        'client_version': client_version,
        'game_version': game_version_of(client_version),
        'files': {path: {'size': size, 'sha1': sha1} for path, (size, sha1)
                  in sorted(hashes.items())},
        'items': {str(ident): {
            'level': record.level, 'type': record.type, 'rarity': record.rarity,
            'properties': record.properties, 'criteria': record.criteria,
            'actions': record.actions, 'sub_records': record.sub_records}
            for ident, record in sorted(items.items())},
        'breeds': [{'id': record.id, 'name': record.name, 'base': record.base}
                   for record in breeds],
        'labels': labels,
        'nations': {language: {str(ident): name for ident, name in table.items()}
                    for language, table in nations.items()},
    }


def decode_tables(folder, client_version, item_ids):
    """The tables.json payload: the effect, group, set, state and ability tables.

    item_ids: the ids of the client's item table, because an effect can name an
    item the client no longer has.
    """
    def path(number):
        return folder / TABLE_JARS[number].rsplit('/', 1)[1]

    return {
        'client_version': client_version,
        'game_version': game_version_of(client_version),
        'item_ids': sorted(int(ident) for ident in item_ids),
        'effects': [record._asdict() for record in wakfu_client.read_effects(path(68))],
        'groups': [record._asdict()
                   for record in wakfu_client.read_effect_groups(path(29))],
        'sets': [{'id': record.id, 'elG': record.elG, 'item_ids': record.item_ids,
                  'bonuses': sorted(record.bonuses.items())}
                 for record in wakfu_client.read_item_sets(path(36))],
        'states': [record._asdict() for record in wakfu_client.read_states(path(67))],
        'abilities': [record._asdict()
                      for record in wakfu_client.read_abilities(path(135))],
        'ability_categories': [
            record._asdict() for record in wakfu_client.read_ability_categories(path(136))],
    }


def is_current(folder, wanted):
    """True when decoded.json and tables.json are there, made from files with these sha1s."""
    path = folder / 'decoded.json'
    if not path.exists() or not (folder / 'tables.json').exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return False
    return {name: entry['sha1'] for name, entry in payload.get('files', {}).items()} \
        == dict(wanted)


def version_key(name):
    """A folder name as a sortable tuple: 1.100.0 comes after 1.93.0."""
    return tuple((0, int(part), '') if part.isascii() and part.isdigit() else (1, 0, part)
                 for part in re.split(r'[.\-_]', name))


def prune(out_dir, keep):
    folders = sorted((path for path in Path(out_dir).iterdir() if path.is_dir()),
                     key=lambda path: version_key(path.name))
    for path in folders[:-KEEP_VERSIONS]:
        if path.name != keep:
            shutil.rmtree(path)


def from_install(args):
    """{path: bytes} of the 12 files, checked against both manifests."""
    install = Path(args.from_install)
    manifest = Path(args.manifest).read_bytes()
    own = json.loads((install / 'manifest.json').read_text(encoding='utf-8'))
    blobs = {}
    for path in FILES:
        entry = cytrus_cdn.find_file(manifest, path)
        if entry is None:
            raise ClientError('%s is not in the manifest' % path)
        blob = (install / path).read_bytes()
        theirs = own.get(path) or {}
        if len(blob) != entry['size'] or sha1_of(blob) != entry['hash']:
            raise ClientError('%s does not match the cytrus manifest' % path)
        if len(blob) != theirs.get('size') or sha1_of(blob) != theirs.get('hash'):
            raise ClientError("%s does not match the install's manifest.json" % path)
        blobs[path] = blob
    return blobs


def from_cytrus(client_version, manifest_bytes):
    blobs = {}
    for path in FILES:
        entry = cytrus_cdn.find_file(manifest_bytes, path)
        if entry is None:
            raise ClientError('%s is not in the manifest' % path)
        try:
            blobs[path] = cytrus_cdn.fetch_file(entry, timeout=180, game='wakfu')
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                raise ClientError('HTTP %d from %s, not retried' % (error.code, error.url))
            raise
    return blobs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-install', help='the launcher install folder')
    parser.add_argument('--manifest', help='the cytrus manifest of that client')
    parser.add_argument('--client-version', help='for example 6.0_1.93.1.5312.334')
    parser.add_argument('--out', default='itemscraper/wakfu_client')
    args = parser.parse_args(argv)
    try:
        if args.from_install:
            if not args.manifest or not args.client_version:
                parser.error('--from-install needs --manifest and --client-version')
            client_version = args.client_version
            manifest_bytes = Path(args.manifest).read_bytes()
        else:
            client_version = cytrus_cdn.get_version('wakfu')
            manifest_bytes = cytrus_cdn.download_manifest('wakfu', client_version)
        wanted = {}
        for path in FILES:
            entry = cytrus_cdn.find_file(manifest_bytes, path)
            if entry is None:
                raise ClientError('%s is not in the manifest' % path)
            wanted[path] = entry['hash']
        folder = Path(args.out) / client_version
        if is_current(folder, wanted):
            print('client %s is already decoded' % client_version)
            return 0
        blobs = from_install(args) if args.from_install else \
            from_cytrus(client_version, manifest_bytes)
        folder.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for path, blob in blobs.items():
            (folder / path.rsplit('/', 1)[1]).write_bytes(blob)
            hashes[path] = (len(blob), sha1_of(blob))
        payload = decode(folder, client_version, hashes)
        tables = decode_tables(folder, client_version, payload['items'])
    except (ClientError, wakfu_client.TableError, urllib.error.URLError, OSError) as error:
        print('the client files could not be read: %s' % error)
        return 1
    (folder / 'decoded.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True),
        encoding='utf-8')
    (folder / 'tables.json').write_text(
        json.dumps(tables, ensure_ascii=False, separators=(',', ':'), sort_keys=True),
        encoding='utf-8')
    prune(args.out, client_version)
    print('client %s' % client_version)
    print('entries %d size or id mismatches 0' % len(payload['items']))
    print('breeds %d' % len(payload['breeds']))
    for name, rows in sorted(tables.items()):
        if isinstance(rows, list):
            print('%s %d' % (name.replace('_', ' '), len(rows)))
    for language in LANGUAGES:
        print('%s: %d critere keys, %d nations' % (
            language, len(payload['labels'][language]),
            len(payload['nations'][language])))
    print('wrote %s and %s' % (folder / 'decoded.json', folder / 'tables.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
