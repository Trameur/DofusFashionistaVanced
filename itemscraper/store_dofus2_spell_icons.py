#!/usr/bin/env python3
"""store_dofus2_spell_icons.py - the spell icons Dofus 2 cannot borrow.

The Dofus 2 release carries no spell image archive at all (2.73.3.14 ships
items_images and mounts_images and nothing else), so the site sends Dofus 2 to
the Dofus 3 spell directory. That works for the spells both versions still
share, and breaks for the 2.x names Dofus 3 renamed or retired: no file is
stored under the old name, so a Dofus 2 build shows broken icons.

The art itself is not lost. Icons are addressed by iconId, and the Dofus 2
release does publish the spell records with their iconId, so the id from the
2.73 lang picks the right image straight out of the Dofus 3 icon pool. For the
ids that pool no longer holds (the spells Dofus 3 dropped, like the Osamodas
summons), the Dofus 2 client itself still ships every icon as a 128x128 PNG in
its spell archives (content/gfx/spells/spells0*.d2p on the Cytrus CDN); those
are fetched once, kept beside the dump, and shrunk to the 96x96 the pages use.
Both halves stay first hand and no rename table is written down.

Only what the shared directory cannot serve is stored here: chardata's
_spell_image_url falls back to the shared file for every other name.

    python itemscraper/store_dofus2_spell_icons.py

The pool comes from the Dofus 3 image step (download_spell_images.py), which
extracts itemscraper/spell_images/96 from the release archive.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import shutil
import struct
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'fashionistapulp') not in sys.path:
    sys.path.insert(0, str(ROOT / 'fashionistapulp'))
from fashionistapulp.reserved_filenames import safe_asset_stem  # noqa: E402

if str(ROOT / 'itemscraper') not in sys.path:
    sys.path.insert(0, str(ROOT / 'itemscraper'))
import cytrus_cdn  # noqa: E402
from version_tags import version_key  # noqa: E402

CONSTANTS = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'dofus_constants_dofus2.py'
POOL = ROOT / 'itemscraper' / 'spell_images' / '96'
SHARED = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata' / 'spells'
STATIC_DIRS = (SHARED / 'dofus2',
               ROOT / 'fashionsite' / 'staticfiles' / 'chardata' / 'spells' / 'dofus2')

# First archive of the client's spell icon chain; each one names the next
CLIENT_ARCHIVE = 'content/gfx/spells/spells0.d2p'
ICON_SIZE = 96


def damage_spell_names():
    spec = importlib.util.spec_from_file_location('dofus2_constants', CONSTANTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = set()
    for spells in getattr(module, 'DAMAGE_SPELLS', {}).values():
        for spell in spells:
            name = getattr(spell, 'name', None)
            if name:
                names.add(name.strip())
    if not names:
        raise SystemExit('DAMAGE_SPELLS is empty in %s' % CONSTANTS)
    return names


REFERENCE = (ROOT / 'fashionsite' / 'chardata' / 'spell_reference'
             / 'dofus2.json')


def reference_spells():
    """Icon stem -> spell id for every Dofus 2 class spell a page can put an
    icon behind.

    DAMAGE_SPELLS is not that population. The page lists the whole class book
    from spell_reference/dofus2.json, damage or not, and it asks for an icon
    for each. While the reference walked breedSpellsId without following
    spell_variants.json it named 418 spells and the two sets happened to
    overlap; the day it followed them and reached 836, twelve spells arrived on
    the page with no icon and no run could have fetched them.

    Reading the reference rather than the literal means this tool covers
    whatever the page covers, without anyone remembering to widen it. When two
    class spells share a name, the lowest id keeps the bare name and each other
    one is filed as "<name> (<id>)", which is what the page asks for.
    """
    if not REFERENCE.exists():
        return {}
    with REFERENCE.open(encoding='utf-8') as handle:
        classes = json.load(handle)
    ids_by_name = {}
    for block in classes.values():
        for spell in block:
            name = (spell.get('name') or {}).get('en', '').strip()
            if name and spell.get('id') is not None:
                ids_by_name.setdefault(name, set()).add(spell['id'])
    targets = {}
    for name, ids in ids_by_name.items():
        keeper = min(ids)
        targets[name] = keeper
        for sid in sorted(ids - {keeper}):
            targets['%s (%s)' % (name, sid)] = sid
    return targets


def icons_by_spell(raw_dir):
    """(name -> icon ids, spell id -> icon id) from the Dofus 2 release."""
    with open(raw_dir / 'spells.json', encoding='utf-8') as fh:
        spells = json.load(fh)
    with open(raw_dir / 'en.json', encoding='utf-8') as fh:
        texts = json.load(fh)['texts']
    by_name = {}
    by_id = {}
    for spell in spells:
        name = texts.get(str(spell.get('nameId')))
        icon = spell.get('iconId')
        if not icon:
            continue
        if spell.get('id') is not None:
            by_id[spell['id']] = icon
        if name:
            by_name.setdefault(name, []).append(icon)
    return by_name, by_id


def _read_utf(buf, pos):
    length = struct.unpack_from('>H', buf, pos)[0]
    return buf[pos + 2:pos + 2 + length].decode('utf-8'), pos + 2 + length


def read_d2p(path):
    """(bytes, properties, {name: (offset, size)}) of one d2p archive."""
    buf = path.read_bytes()
    if buf[:2] != b'\x02\x01':
        raise ValueError('%s is not a d2p archive' % path)
    (base, _size, index_offset, index_count, properties_offset,
     properties_count) = struct.unpack_from('>6i', buf, len(buf) - 24)
    pos = properties_offset
    properties = {}
    for _ in range(properties_count):
        key, pos = _read_utf(buf, pos)
        properties[key], pos = _read_utf(buf, pos)
    pos = index_offset
    entries = {}
    for _ in range(index_count):
        name, pos = _read_utf(buf, pos)
        offset, size = struct.unpack_from('>ii', buf, pos)
        pos += 8
        entries[name] = (base + offset, size)
    return buf, properties, entries


def _client_manifest(raw_dir):
    version = '6.0_%s' % raw_dir.name
    try:
        return cytrus_cdn.download_manifest('dofus2', version)
    except OSError as exc:
        live = cytrus_cdn.get_version('dofus2')
        print('WARNING: the CDN does not serve the %s manifest (%s); '
              'reading the %s client instead' % (version, exc, live))
        return cytrus_cdn.download_manifest('dofus2', live)


def client_icons(raw_dir, wanted):
    """Icon id -> PNG bytes from the client archives, fetched once and kept under the dump."""
    found = {}
    manifest = None
    name = CLIENT_ARCHIVE
    while name and len(found) < len(wanted):
        path = raw_dir.joinpath(*PurePosixPath(name).parts)
        if not path.exists():
            if manifest is None:
                manifest = _client_manifest(raw_dir)
            entry = cytrus_cdn.find_file(manifest, name)
            if entry is None:
                raise LookupError('%s: not in the client manifest' % name)
            print('fetching %s (%d bytes)' % (name, entry['size']))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(cytrus_cdn.fetch_file(entry))
        buf, properties, entries = read_d2p(path)
        for icon in wanted:
            entry = entries.get('sort_%d.png' % icon)
            if entry and icon not in found:
                offset, size = entry
                found[icon] = buf[offset:offset + size]
        link = properties.get('link')
        name = str(PurePosixPath(name).parent / link) if link else None
    return found


def page_sized(data):
    from PIL import Image
    image = Image.open(io.BytesIO(data)).convert('RGBA')
    if image.size != (ICON_SIZE, ICON_SIZE):
        image = image.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', help='the 2.73 dump; the newest one by default')
    parser.add_argument('--pool', default=str(POOL))
    args = parser.parse_args()

    raw_root = ROOT / 'itemscraper' / 'raw'
    if args.raw_dir:
        raw_dir = Path(args.raw_dir)
    else:
        candidates = [p for p in raw_root.iterdir()
                      if p.is_dir() and p.name.startswith('2.')]
        if not candidates:
            raise SystemExit('no Dofus 2 dump under %s' % raw_root)
        raw_dir = max(candidates, key=lambda p: version_key(p.name))

    pool = Path(args.pool)
    if not pool.is_dir():
        # The pool belongs to the Dofus 3 image step, so a Dofus 2 rebuild on a
        # machine that never ran it keeps the committed icons instead of failing.
        print('WARNING: no icon pool at %s (Dofus 3 spell-images step); '
              'the committed icons stay as they are.' % pool)
        return

    # A damage spell outside the class book is found by name, a class spell by id
    wanted = {name: None for name in damage_spell_names()}
    wanted.update(reference_spells())
    print('%d noms a couvrir (DAMAGE_SPELLS + reference de classe)'
          % len(wanted))
    by_name, by_id = icons_by_spell(raw_dir)
    for directory in STATIC_DIRS:
        directory.mkdir(parents=True, exist_ok=True)

    written = borrowed = unnamed = 0
    missing = []
    not_in_pool = {}
    for name, spell_id in sorted(wanted.items()):
        # Windows reserves a handful of stems and git cannot index a file named
        # after one, so the page asks for the escaped name and so must this.
        stem = safe_asset_stem(name)
        if (SHARED / ('%s.png' % stem)).exists():
            borrowed += 1
            continue
        if spell_id is None:
            ids = by_name.get(name)
        else:
            ids = [by_id[spell_id]] if spell_id in by_id else None
        if not ids:
            unnamed += 1
            missing.append('%s (not in the %s lang)' % (name, raw_dir.name))
            continue
        source = next((pool / ('%d.png' % icon) for icon in ids
                       if (pool / ('%d.png' % icon)).exists()), None)
        if source is None:
            not_in_pool[name] = ids
            continue
        for directory in STATIC_DIRS:
            shutil.copy2(source, directory / ('%s.png' % stem))
        written += 1

    client = {}
    if not_in_pool:
        try:
            client = client_icons(
                raw_dir, {icon for ids in not_in_pool.values() for icon in ids})
        except (OSError, LookupError, ValueError) as exc:
            print('WARNING: the Dofus 2 client archives are out of reach (%s); '
                  'the committed icons stay as they are.' % exc)
    from_client = no_icon = 0
    for name, ids in sorted(not_in_pool.items()):
        data = next((client[icon] for icon in ids if icon in client), None)
        if data is None:
            no_icon += 1
            missing.append('%s (icon %s absent from the pool and the client)'
                           % (name, ids[0]))
            continue
        png = page_sized(data)
        for directory in STATIC_DIRS:
            (directory / ('%s.png' % safe_asset_stem(name))).write_bytes(png)
        from_client += 1

    print('dofus2 spell icons: %d written from the pool, %d from the client'
          ' archives, %d served by the shared directory, %d without a 2.73'
          ' name, %d without an icon anywhere'
          % (written, from_client, borrowed, unnamed, no_icon))
    for line in missing:
        print('   missing: %s' % line)


if __name__ == '__main__':
    main()
