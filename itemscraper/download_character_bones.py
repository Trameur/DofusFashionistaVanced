#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download the standing player skeletons from Ankama's CDN, one per class.

    python itemscraper/download_character_bones.py --manifest <file> --dest character_bundles

Nineteen bundles, about 15 MB. Resumable: existing files are skipped.
The numbered bones (bone_2 and up) are monsters and mounts, not players.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cytrus_cdn

BONE_DIR = 'Dofus_Data/StreamingAssets/Content/Characters/Bones'
# Ankama breed ids. 19 is unused, Forgelance is 20.
BREEDS = list(range(1, 19)) + [20]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=sorted(cytrus_cdn.RELEASES))
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--dest', required=True)
    parser.add_argument('--pose', default='static', choices=('static', 'combat'))
    args = parser.parse_args()

    if os.path.exists(args.manifest):
        manifest = open(args.manifest, 'rb').read()
    else:
        manifest = cytrus_cdn.download_manifest(args.game_version)
        open(args.manifest, 'wb').write(manifest)

    os.makedirs(args.dest, exist_ok=True)
    done = skipped = 0
    for breed in BREEDS:
        stem = '1-%d-%s' % (breed, args.pose)
        path = os.path.join(args.dest, 'bones_assets_bone_%s.bundle' % stem)
        if os.path.exists(path) and os.path.getsize(path):
            skipped += 1
            continue
        entry = cytrus_cdn.find_file(
            manifest, '%s/bones_assets_bone_%s.bundle' % (BONE_DIR, stem))
        open(path, 'wb').write(cytrus_cdn.fetch_file(entry))
        done += 1
        print('%s downloaded' % stem, flush=True)
    print('done: %d downloaded, %d already there' % (done, skipped))


if __name__ == '__main__':
    main()
