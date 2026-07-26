#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull single files straight from Ankama's official game CDN (cytrus).

First-hand game data is the top of our sourcing rule, and this is as first-hand
as it gets: the same CDN the Ankama launcher installs the game from, public and
without any authentication. It already backs our Retro lang data; this makes the
rest of it reachable too.

Ankama ships the game content addressed. A manifest lists every file with the
chunks it is made of, each chunk lives inside a bundle, and the CDN answers HTTP
range requests. So one file comes down for its own weight rather than the game's:
a single character skin is about 47 KB out of a 51 MB manifest.

    python itemscraper/cytrus_cdn.py --list Characters/Skins | head
    python itemscraper/cytrus_cdn.py --fetch Dofus_Data/StreamingAssets/Content/Data/data_assets_itemsdataroot.asset.bundle

Releases are separate games and must never be mixed: dofus3 and beta are the
Unity client, main is Dofus 2, and Dofus Retro lives under its own game name
with a 1.29 channel.

The manifest is a flatbuffer. Its schema is four small tables (taken from
dofusdude/ankabuffer, GPL-3.0), so it is read here directly rather than adding a
flatbuffers dependency to the pipeline:

    Chunk    { hash:[ubyte], size:long, offset:long, done:bool }
    File     { name:string, size:long, hash:[ubyte], chunks:[Chunk], ... }
    Bundle   { hash:[ubyte], chunks:[Chunk] }
    Fragment { name:string, files:[File], bundles:[Bundle] }
    Manifest { fragments:[Fragment] }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import urllib.request

CDN = 'https://cytrus.cdn.ankama.com'
VERSIONS_URL = '%s/cytrus.json' % CDN

# Every one of these is a different game with its own assets, like everywhere
# else in this project. (game, release) as named by Ankama. Retro is its own
# game rather than a release of Dofus, and the channel serving it is "main":
# the "1.29" name only appears on the meta side, not on the platforms.
RELEASES = {
    'dofus3': ('dofus', 'dofus3'),
    'beta': ('dofus', 'beta'),
    'dofus2': ('dofus', 'main'),
    'retro': ('retro', 'main'),
}


class _Table:
    """One flatbuffer table. Fields are read by their index in the schema."""

    def __init__(self, buf, pos):
        self.buf = buf
        self.pos = pos
        self.vtable = pos - struct.unpack_from('<i', buf, pos)[0]
        self.vtable_size = struct.unpack_from('<H', buf, self.vtable)[0]

    def _offset(self, field):
        slot = self.vtable + 4 + 2 * field
        if slot - self.vtable >= self.vtable_size:
            return 0
        return struct.unpack_from('<H', self.buf, slot)[0]

    def string(self, field):
        off = self._offset(field)
        if not off:
            return ''
        pos = self.pos + off
        start = pos + struct.unpack_from('<I', self.buf, pos)[0]
        length = struct.unpack_from('<I', self.buf, start)[0]
        return self.buf[start + 4:start + 4 + length].decode('utf-8')

    def int64(self, field):
        off = self._offset(field)
        return struct.unpack_from('<q', self.buf, self.pos + off)[0] if off else 0

    def hash(self, field):
        off = self._offset(field)
        if not off:
            return ''
        pos = self.pos + off
        start = pos + struct.unpack_from('<I', self.buf, pos)[0]
        length = struct.unpack_from('<I', self.buf, start)[0]
        return self.buf[start + 4:start + 4 + length].hex()

    def tables(self, field):
        off = self._offset(field)
        if not off:
            return
        pos = self.pos + off
        start = pos + struct.unpack_from('<I', self.buf, pos)[0]
        count = struct.unpack_from('<I', self.buf, start)[0]
        for i in range(count):
            element = start + 4 + 4 * i
            yield _Table(self.buf,
                         element + struct.unpack_from('<I', self.buf, element)[0])


def _chunks_of(table, field):
    for chunk in table.tables(field):
        yield {'hash': chunk.hash(0), 'size': chunk.int64(1), 'offset': chunk.int64(2)}


def get_version(game_version, platform='windows'):
    """The version Ankama currently serves for one of our game versions."""
    game, release = RELEASES[game_version]
    with urllib.request.urlopen(VERSIONS_URL, timeout=60) as resp:
        catalog = json.load(resp)
    return catalog['games'][game]['platforms'][platform][release]


def download_manifest(game_version, version=None, platform='windows'):
    game, release = RELEASES[game_version]
    version = version or get_version(game_version, platform)
    url = '%s/%s/releases/%s/%s/%s.manifest' % (CDN, game, release, platform, version)
    with urllib.request.urlopen(url, timeout=600) as resp:
        return resp.read()


def iter_files(manifest):
    """Yield (fragment name, file name) for the whole manifest.

    Reading names only, so it stays cheap on a 51 MB manifest.
    """
    root = _Table(manifest, struct.unpack_from('<I', manifest, 0)[0])
    for fragment in root.tables(0):
        fragment_name = fragment.string(0)
        for entry in fragment.tables(1):
            yield fragment_name, entry.string(0)


def find_file(manifest, wanted_name):
    """The file entry plus the bundle each of its chunks sits in.

    A file small enough to be shipped whole has no chunk of its own and is
    placed under its own hash, which is the case for most single skins.
    """
    root = _Table(manifest, struct.unpack_from('<I', manifest, 0)[0])
    for fragment in root.tables(0):
        found = None
        for entry in fragment.tables(1):
            if entry.string(0) == wanted_name:
                found = {'name': wanted_name, 'size': entry.int64(1),
                         'hash': entry.hash(2), 'chunks': list(_chunks_of(entry, 3)),
                         'fragment': fragment.string(0)}
                break
        if found is None:
            continue
        # Only now walk the bundles, and only the ones of this fragment.
        needed = {c['hash'] for c in found['chunks']} or {found['hash']}
        placement = {}
        for bundle in fragment.tables(2):
            bundle_hash = bundle.hash(0)
            for chunk in _chunks_of(bundle, 1):
                if chunk['hash'] in needed:
                    placement[chunk['hash']] = (bundle_hash, chunk['offset'], chunk['size'])
        missing = needed - set(placement)
        if missing:
            raise LookupError('%s: %d chunk(s) placed in no bundle' % (wanted_name, len(missing)))
        found['placement'] = placement
        return found
    return None


def fetch_file(entry, timeout=180):
    """Rebuild one game file from the CDN, checking every hash on the way."""
    pieces = entry['chunks'] or [{'hash': entry['hash'], 'offset': 0, 'size': entry['size']}]
    out = bytearray(entry['size'])
    for chunk in pieces:
        bundle_hash, offset, size = entry['placement'][chunk['hash']]
        url = '%s/dofus/bundles/%s/%s' % (CDN, bundle_hash[:2], bundle_hash)
        request = urllib.request.Request(
            url, headers={'Range': 'bytes=%d-%d' % (offset, offset + size - 1)})
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            piece = resp.read()
        if hashlib.sha1(piece).hexdigest() != chunk['hash']:
            raise ValueError('chunk %s does not match its hash' % chunk['hash'])
        out[chunk['offset']:chunk['offset'] + chunk['size']] = piece
    blob = bytes(out)
    if hashlib.sha1(blob).hexdigest() != entry['hash']:
        raise ValueError('%s does not match its hash' % entry['name'])
    return blob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=sorted(RELEASES))
    parser.add_argument('--manifest', help='reuse a manifest already on disk')
    parser.add_argument('--list', metavar='PATTERN',
                        help='print the file names matching this regular expression')
    parser.add_argument('--fetch', metavar='NAME', help='download one file by its exact name')
    parser.add_argument('--dest', default='.', help='where --fetch writes')
    args = parser.parse_args()

    if args.manifest and os.path.exists(args.manifest):
        manifest = open(args.manifest, 'rb').read()
    else:
        manifest = download_manifest(args.game_version)
        if args.manifest:
            open(args.manifest, 'wb').write(manifest)

    if args.list:
        pattern = re.compile(args.list)
        for fragment_name, name in iter_files(manifest):
            if pattern.search(name):
                print('%-12s %s' % (fragment_name, name))

    if args.fetch:
        entry = find_file(manifest, args.fetch)
        if entry is None:
            raise SystemExit('%s: not in the manifest' % args.fetch)
        blob = fetch_file(entry)
        out_path = os.path.join(args.dest, os.path.basename(args.fetch))
        open(out_path, 'wb').write(blob)
        print('%s -> %s (%d bytes, hash verified)' % (args.fetch, out_path, len(blob)))


if __name__ == '__main__':
    main()
