#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download single files from Ankama's game CDN (cytrus), no auth needed.

    python itemscraper/cytrus_cdn.py --list Characters/Skins
    python itemscraper/cytrus_cdn.py --fetch Dofus_Data/StreamingAssets/Content/Data/data_assets_itemsdataroot.asset.bundle

Files are content addressed: the manifest lists chunks, chunks live in bundles,
and the CDN answers range requests, so a file costs its own size and not the
game's. Manifest schema comes from dofusdude/ankabuffer (GPL-3.0):

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

# (game, release) as Ankama names them. Retro is its own game, served on main.
RELEASES = {
    'dofus3': ('dofus', 'dofus3'),
    'beta': ('dofus', 'beta'),
    'dofus2': ('dofus', 'main'),
    'retro': ('retro', 'main'),
}


class _Table:

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

    def _vector(self, field):
        off = self._offset(field)
        if not off:
            return None, 0
        pos = self.pos + off
        start = pos + struct.unpack_from('<I', self.buf, pos)[0]
        return start + 4, struct.unpack_from('<I', self.buf, start)[0]

    def string(self, field):
        start, length = self._vector(field)
        return self.buf[start:start + length].decode('utf-8') if start else ''

    def hash(self, field):
        start, length = self._vector(field)
        return self.buf[start:start + length].hex() if start else ''

    def int64(self, field):
        off = self._offset(field)
        return struct.unpack_from('<q', self.buf, self.pos + off)[0] if off else 0

    def tables(self, field):
        start, count = self._vector(field)
        if not start:
            return
        for i in range(count):
            element = start + 4 * i
            yield _Table(self.buf,
                         element + struct.unpack_from('<I', self.buf, element)[0])


def _chunks_of(table, field):
    for chunk in table.tables(field):
        yield {'hash': chunk.hash(0), 'size': chunk.int64(1), 'offset': chunk.int64(2)}


def _root(manifest):
    return _Table(manifest, struct.unpack_from('<I', manifest, 0)[0])


def get_version(game_version, platform='windows'):
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
    for fragment in _root(manifest).tables(0):
        fragment_name = fragment.string(0)
        for entry in fragment.tables(1):
            yield fragment_name, entry.string(0)


def find_file(manifest, wanted_name):
    for fragment in _root(manifest).tables(0):
        found = None
        for entry in fragment.tables(1):
            if entry.string(0) == wanted_name:
                found = {'name': wanted_name, 'size': entry.int64(1),
                         'hash': entry.hash(2), 'chunks': list(_chunks_of(entry, 3)),
                         'fragment': fragment.string(0)}
                break
        if found is None:
            continue
        # A file small enough to ship whole has no chunks and sits under its own hash.
        needed = {c['hash'] for c in found['chunks']} or {found['hash']}
        placement = {}
        for bundle in fragment.tables(2):
            bundle_hash = bundle.hash(0)
            for chunk in _chunks_of(bundle, 1):
                if chunk['hash'] in needed:
                    placement[chunk['hash']] = (bundle_hash, chunk['offset'], chunk['size'])
        missing = needed - set(placement)
        if missing:
            raise LookupError('%s: %d chunk(s) in no bundle' % (wanted_name, len(missing)))
        found['placement'] = placement
        return found
    return None


def fetch_file(entry, timeout=180):
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
    parser.add_argument('--list', metavar='PATTERN', help='file names matching this regex')
    parser.add_argument('--fetch', metavar='NAME', help='download one file by exact name')
    parser.add_argument('--dest', default='.')
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
