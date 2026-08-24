#!/usr/bin/env python3
"""Fetch the Wakfu item artwork from Ankama and store it the way the site does.

    python get_item_images_wakfu.py [--size 64] [--limit 50]

Run `get_items_wakfu.py` first: the list of pictures to fetch is the set of
gfx ids in the dump it writes, and nothing here reads Ankama's item catalogue.

WHERE THE PICTURES COME FROM. Ankama serves them itself, which is the source
this project prefers over any fan mirror:

    https://static.ankama.com/wakfu/portal/game/item/<size>/<gfxId>.png

Sizes 115, 64 and 21 answer; 45 answers 403, so the sizes are not a free
parameter and `--size` is checked against the three that exist. The site shows
item pictures at 60 pixels, so 64 is the one to keep: downscaling by four
pixels in the browser costs nothing, while upscaling from 21 would show.

WHY gfx ids AND NOT ITEM IDS. 7785 pieces of gear share 3928 pictures, so
naming the files by item would store the same drawing twice as often as not.
It also matches how the monster artwork is already stored, by id rather than by
name: a name is different in five languages and changes when Ankama renames a
piece, an id does not.

The files are webp, like the monster artwork, because Pillow is already a
dependency and the saving is worth having on several thousand files.

A run that stops halfway can be run again: a picture already on disk is never
fetched twice, so the second run costs almost nothing.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
STATIC = HERE / 'fashionsite' / 'chardata' / 'static' / 'chardata' / 'items'

URL = 'https://static.ankama.com/wakfu/portal/game/item/%d/%d.png'
# The three the CDN answers. 45 returns 403, so a typo would otherwise look
# like an outage.
SIZES = (115, 64, 21)
BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
           ' (KHTML, like Gecko) Chrome/120 Safari/537.36')
PACE = 0.12


def wanted(dump_path):
    """Every distinct picture the gear in the dump points at."""
    with io.open(dump_path, encoding='utf-8') as handle:
        dump = json.load(handle)
    ids = {item['gfx_id'] for item in dump['equipment']
           if item['positions'] and item.get('gfx_id')}
    return sorted(ids)


def fetch(gfx_id, size):
    request = urllib.request.Request(URL % (size, gfx_id),
                                     headers={'User-Agent': BROWSER})
    return urllib.request.urlopen(request, timeout=40).read()


def store(body, path):
    """Write the picture as webp, keeping the transparency Ankama sends."""
    from PIL import Image
    with Image.open(io.BytesIO(body)) as picture:
        picture.load()
        if picture.mode not in ('RGBA', 'LA'):
            picture = picture.convert('RGBA')
        picture.save(str(path), 'WEBP', quality=90, method=6)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', default='itemscraper/transformed_wakfu.json')
    parser.add_argument('--size', type=int, default=64, choices=SIZES)
    parser.add_argument('--limit', type=int,
                        help='stop after this many pictures, for a dry run')
    args = parser.parse_args(argv)

    dump_path = Path(args.dump)
    if not dump_path.exists():
        parser.error('%s is missing; run itemscraper/get_items_wakfu.py first'
                     % dump_path)
    ids = wanted(dump_path)
    if args.limit:
        ids = ids[:args.limit]

    out_dir = STATIC / 'wakfu' / str(args.size)
    out_dir.mkdir(parents=True, exist_ok=True)

    had = fetched = missing = 0
    bytes_written = 0
    for number, gfx_id in enumerate(ids, start=1):
        path = out_dir / ('%d.webp' % gfx_id)
        if path.exists():
            had += 1
            continue
        try:
            body = fetch(gfx_id, args.size)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                missing += 1
                continue
            raise
        store(body, path)
        bytes_written += path.stat().st_size
        fetched += 1
        time.sleep(PACE)
        if fetched % 200 == 0:
            print('   %d of %d, %.1f MB' % (number, len(ids),
                                            bytes_written / 1e6))

    print('%d pictures at size %d in %s' % (len(ids), args.size, out_dir))
    print('   already there   %6d' % had)
    print('   fetched         %6d  (%.1f MB)' % (fetched, bytes_written / 1e6))
    print('   no picture      %6d' % missing)
    return 0


if __name__ == '__main__':
    sys.exit(main())
