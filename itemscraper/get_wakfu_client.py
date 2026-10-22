#!/usr/bin/env python3
"""Fetch and decode the Wakfu client's item, breed, effect, set, state, ability, spell, pet, mount,
monster and loot list tables, and label files, and keep its picture archive for
get_wakfu_images.py.

    python itemscraper/get_wakfu_client.py
    python itemscraper/get_wakfu_client.py --from-install DIR --manifest PATH \\
        --client-version VERSION [--out itemscraper/wakfu_client]

The first form reads the current client from Ankama's CDN. The second reads
the launcher's install folder and needs no network: the manifest is the CDN's
one for that client, and every file must match both it and the install's own
manifest.json. A 403 or a 429 from the CDN stops the step and is never retried.
The files and what is decoded from them stay local and are never committed:
decoded.json holds the items, breeds and labels, tables.json the effects,
effect groups, item sets, states, abilities, spells, pets, mounts, monsters and
loot lists, texts.json the names and texts of the language files. gui.jar, the
picture archive, is kept as a file and never decoded here; only the newest client
folder keeps it, and a file whose sha1 is already in another folder is linked
or copied from there instead of fetched.
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
# 135 abilities, 136 fixed ability categories, 66 spells, 117 pets, 144 mounts,
# 42 monsters, 39 loot lists
TABLE_JARS = {number: 'contents/bdata/%d.jar' % number
              for number in (29, 36, 67, 68, 135, 136, 66, 117, 144, 42, 39)}
GUI_JAR = 'contents/gui_jar/gui.jar'
CONFIG = 'config.properties'
FILES = ((ITEMS_JAR, BREEDS_JAR) + tuple(LABEL_JARS.values()) + tuple(TABLE_JARS.values())
         + (GUI_JAR, CONFIG))
KEEP_VERSIONS = 2
# From this size a file is written piece by piece and never held in memory
BIG_FILE = 32 * 1024 * 1024


class ClientError(Exception):
    pass


def game_version_of(client_version):
    """'1.93.1' for '6.0_1.93.1.5312.334'."""
    tail = client_version.split('_', 1)[-1]
    return '.'.join(tail.split('.')[:3])


def sha1_of(blob):
    return hashlib.sha1(blob).hexdigest()


def sha1_of_file(path):
    digest = hashlib.sha1()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def decode(folder, client_version, hashes):
    """The decoded.json payload of the files in a folder."""
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
            'gfx': record.gfx,
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
    """The tables.json payload: the effect, group, set, state, ability, spell, pet,
    mount, monster and loot list tables.

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
        'spells': [record._asdict() for record in wakfu_client.read_spells(path(66))],
        'pets': [record._asdict() for record in wakfu_client.read_pets(path(117))],
        'mounts': [record._asdict() for record in wakfu_client.read_mounts(path(144))],
        'monsters': [
            {'id': record.id, 'family': record.family, 'picture': record.picture,
             'drops': [drop._asdict() for drop in record.drops],
             'harvests': [harvest._asdict() for harvest in record.harvests]}
            for record in wakfu_client.read_monsters(path(42))],
        'loot_lists': [
            {'id': record.id, 'rows': [row._asdict() for row in record.rows]}
            for record in wakfu_client.read_loot_lists(path(39))],
    }


def decode_texts(folder, client_version):
    """The texts.json payload: {family: {language: {id: text}}}, the whole families."""
    texts = {family: {} for family in wakfu_client.ALL_TEXT_FAMILIES}
    for language, path in LABEL_JARS.items():
        read = wakfu_client.read_texts(folder / path.rsplit('/', 1)[1], language)
        for family, table in read.items():
            texts[family][language] = {str(ident): text for ident, text in table.items()}
    return {
        'client_version': client_version,
        'game_version': game_version_of(client_version),
        'texts': texts,
    }


def is_current(folder, wanted):
    """True when decoded.json, tables.json and a texts.json holding every family are there,
    made from these sha1s."""
    path = folder / 'decoded.json'
    if not path.exists() or not (folder / 'tables.json').exists() \
            or not (folder / 'texts.json').exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return False
    try:
        families = json.loads((folder / 'texts.json').read_text(encoding='utf-8'))['texts']
    except (ValueError, KeyError):
        return False
    if not set(wakfu_client.ALL_TEXT_FAMILIES) <= set(families):
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
    for path in folders[:-1]:
        if path.exists() and path.name != keep:
            (path / GUI_JAR.rsplit('/', 1)[1]).unlink(missing_ok=True)


def matches(path, entry):
    return path.is_file() and path.stat().st_size == entry['size'] \
        and sha1_of_file(path) == entry['hash']


def link_or_copy(source, target):
    part = target.with_name(target.name + '.part')
    part.unlink(missing_ok=True)
    try:
        os.link(source, part)
    except OSError:
        shutil.copyfile(source, part)
    os.replace(part, target)


def reuse(folder, target, entry):
    """True when the file is already in the folder, or was linked from another version folder."""
    if matches(target, entry):
        return True
    for other in sorted(Path(folder).parent.iterdir()):
        candidate = other / target.name
        if other != folder and other.is_dir() and matches(candidate, entry):
            link_or_copy(candidate, target)
            return True
    return False


def from_install(args, entry, path, target):
    """Copy one file of the launcher install, checked against both manifests."""
    install = Path(args.from_install)
    own = json.loads((install / 'manifest.json').read_text(encoding='utf-8'))
    source = install / path
    theirs = own.get(path) or {}
    if not matches(source, entry):
        raise ClientError('%s does not match the cytrus manifest' % path)
    if source.stat().st_size != theirs.get('size') or entry['hash'] != theirs.get('hash'):
        raise ClientError("%s does not match the install's manifest.json" % path)
    part = target.with_name(target.name + '.part')
    shutil.copyfile(source, part)
    os.replace(part, target)


def from_cytrus(entry, target):
    try:
        if entry['size'] >= BIG_FILE:
            cytrus_cdn.fetch_file_to(entry, target, timeout=180, game='wakfu')
        else:
            target.write_bytes(cytrus_cdn.fetch_file(entry, timeout=180, game='wakfu'))
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            raise ClientError('HTTP %d from %s, not retried' % (error.code, error.url))
        raise


def place_files(args, folder, manifest_bytes):
    """Put every file of FILES in the folder; {path: (size, sha1)}."""
    hashes = {}
    for path in FILES:
        entry = cytrus_cdn.find_file(manifest_bytes, path)
        if entry is None:
            raise ClientError('%s is not in the manifest' % path)
        target = folder / path.rsplit('/', 1)[-1]
        if not reuse(folder, target, entry):
            if args.from_install:
                from_install(args, entry, path, target)
            else:
                from_cytrus(entry, target)
        hashes[path] = (entry['size'], entry['hash'])
    return hashes


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
        folder.mkdir(parents=True, exist_ok=True)
        hashes = place_files(args, folder, manifest_bytes)
        payload = decode(folder, client_version, hashes)
        tables = decode_tables(folder, client_version, payload['items'])
        texts = decode_texts(folder, client_version)
    except (ClientError, wakfu_client.TableError, urllib.error.URLError, OSError) as error:
        print('the client files could not be read: %s' % error)
        return 1
    (folder / 'decoded.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True),
        encoding='utf-8')
    (folder / 'tables.json').write_text(
        json.dumps(tables, ensure_ascii=False, separators=(',', ':'), sort_keys=True),
        encoding='utf-8')
    (folder / 'texts.json').write_text(
        json.dumps(texts, ensure_ascii=False, separators=(',', ':'), sort_keys=True),
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
    for family, by_language in sorted(texts['texts'].items()):
        print('texts %s: %s' % (family, ', '.join(
            '%s %d' % (language, len(by_language[language])) for language in LANGUAGES)))
    print('wrote %s, %s and %s' % (
        folder / 'decoded.json', folder / 'tables.json', folder / 'texts.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
