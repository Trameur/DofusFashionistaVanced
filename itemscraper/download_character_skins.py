#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download every character skin bundle from Ankama's CDN.

    python itemscraper/download_character_skins.py --dest itemscraper/skins_dofus3

About 5500 bundles, 780 MB for dofus3. Resumable: existing files are skipped.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cytrus_cdn

SKIN_RE = re.compile(r'Characters/Skins/skins_assets_skin_(\d+)\.bundle$')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=sorted(cytrus_cdn.RELEASES))
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--dest', required=True)
    args = parser.parse_args()

    if os.path.exists(args.manifest):
        manifest = open(args.manifest, 'rb').read()
    else:
        manifest = cytrus_cdn.download_manifest(args.game_version)
        open(args.manifest, 'wb').write(manifest)

    os.makedirs(args.dest, exist_ok=True)
    names = [n for _, n in cytrus_cdn.iter_files(manifest) if SKIN_RE.search(n)]
    print('%d skins' % len(names))

    done = skipped = 0
    for name in names:
        skin_id = SKIN_RE.search(name).group(1)
        path = os.path.join(args.dest, 'skin_%s.bundle' % skin_id)
        if os.path.exists(path) and os.path.getsize(path):
            skipped += 1
            continue
        entry = cytrus_cdn.find_file(manifest, name)
        open(path, 'wb').write(cytrus_cdn.fetch_file(entry))
        done += 1
        if done % 100 == 0:
            print('%d downloaded, %d already there' % (done, skipped), flush=True)
    print('done: %d downloaded, %d skipped' % (done, skipped))


if __name__ == '__main__':
    main()
