# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Detect icon drift between the committed files and their live sources.

The download pipelines skip files that already exist, so a visual rework on
the game side (new renders, redrawn icons) would never reach the site. This
tool samples committed icons per family, re-fetches the SOURCE image, applies
the same resize as the downloader, and measures the mean absolute pixel
difference. A family with several drifted samples deserves a --force rerun
of its downloader.

Families audited (URL-based sources only):
  - resources dofus3/dofus2 (dofusdude raw icon urls)
  - resources touch (official Touch CDN, iconId mapping)
  - monsters dofus3 (DofusDB img urls, gfx-keyed)
  - monsters touch (official Touch CDN, monster-id-keyed)
Retro is excluded on purpose: its icons are rendered from the client via
Cytrus (download_retro_images/download_retro_monster_artworks --force), and
a client update is already visible through the Cytrus version string.

Usage (from itemscraper/):
    python audit_icon_drift.py [--sample 12] [--threshold 8.0]
Exit code 0 always: this is a report, not a gate.
"""

import argparse
import io
import os
import random
import sys

import requests
from PIL import Image

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
STATIC = os.path.join(ROOT, 'fashionsite', 'chardata', 'static', 'chardata')

sys.path.insert(0, CURRENT_DIR)


def _on_white(image):
    canvas = Image.new('RGBA', image.size, (255, 255, 255, 255))
    canvas.paste(image, (0, 0), image)
    return canvas.convert('RGB')


def mean_abs_diff(local_path, source_bytes, size, thumbnail):
    """Reproduce the downloader's resize, then compare pixel by pixel.
    Both sides are composited on white first: webp zeroes the RGB of fully
    transparent pixels while the source PNG keeps arbitrary values there,
    which would read as huge fake drift. Lossy webp still leaves a few
    units of codec noise; the threshold sits above it."""
    local = Image.open(local_path).convert('RGBA')
    remote = Image.open(io.BytesIO(source_bytes)).convert('RGBA')
    if thumbnail:
        remote.thumbnail(size, Image.LANCZOS)
    else:
        remote = remote.resize(size)
    if local.size != remote.size:
        remote = remote.resize(local.size)
    local_rgb = _on_white(local)
    remote_rgb = _on_white(remote)
    pairs = zip(local_rgb.get_flattened_data(),
                remote_rgb.get_flattened_data())
    total = count = 0
    for a, b in pairs:
        total += sum(abs(x - y) for x, y in zip(a, b))
        count += 3
    return total / count


def audit_family(label, session, url_of, directory, id_of_name, size,
                 sample, threshold, rng, ext='.png', thumbnail=False):
    if not os.path.isdir(directory):
        print('%s: directory missing, skipped' % label)
        return
    names = [n for n in os.listdir(directory) if n.endswith(ext)]
    rng.shuffle(names)
    checked = drifted = missing = errors = 0
    worst = 0.0
    for name in names:
        if checked >= sample:
            break
        icon_id = id_of_name(name)
        if icon_id is None:
            continue
        url = url_of(icon_id)
        if not url:
            continue
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200 or not resp.content:
                missing += 1
                continue
            diff = mean_abs_diff(os.path.join(directory, name),
                                 resp.content, size, thumbnail)
        except Exception:
            errors += 1
            continue
        checked += 1
        worst = max(worst, diff)
        if diff > threshold:
            drifted += 1
            print('  %s: %s drift %.1f' % (label, name, diff))
    verdict = 'DRIFT SUSPECTED' if drifted >= max(2, checked // 4) else 'ok'
    print('%s: checked %d, drifted %d, missing-at-source %d, errors %d, '
          'worst %.1f -> %s' % (label, checked, drifted, missing, errors,
                                worst, verdict))


def numeric_id(name):
    stem = name.split('-', 1)[0]
    return int(stem) if stem.isdigit() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=int, default=12)
    parser.add_argument('--threshold', type=float, default=8.0,
                        help='mean abs pixel diff (0-255) above which a '
                             'sample counts as drifted')
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (DofusFashionista asset sync)'

    import download_resource_icons as res
    import download_monster_images as mon

    # resources dofus3 + dofus2: ankama id -> source url from the raws.
    urls_d3 = res.icon_urls()
    audit_family(
        'resources dofus3', session, urls_d3.get,
        os.path.join(STATIC, 'resources', '60x60'),
        numeric_id, (60, 60), args.sample, args.threshold, rng)
    urls_d2 = res.icon_urls([os.path.join(CURRENT_DIR, 'dofus2')])
    audit_family(
        'resources dofus2', session, urls_d2.get,
        os.path.join(STATIC, 'resources', 'dofus2', '60x60'),
        numeric_id, (60, 60), args.sample, args.threshold, rng)

    # resources touch: official CDN by iconId.
    urls_touch = res.touch_icon_urls()
    audit_family(
        'resources touch', session, urls_touch.get,
        os.path.join(STATIC, 'resources', 'touch', '60x60'),
        numeric_id, (60, 60), args.sample, args.threshold, rng)

    # monsters dofus3: DofusDB img urls (gfx-keyed, fetched via the API).
    monster_urls = mon.image_urls(session)
    audit_family(
        'monsters dofus3', session, monster_urls.get,
        os.path.join(STATIC, 'monsters', '96'),
        lambda n: int(n[:-5]) if n[:-5].isdigit() else None,
        (96, 96), args.sample, args.threshold, rng,
        ext='.webp', thumbnail=True)

    # monsters touch: official CDN by monster id.
    ids = mon.monster_ids(mon.TOUCH_DB_PATHS)
    touch_urls = mon.touch_image_urls(session, ids)
    audit_family(
        'monsters touch', session, touch_urls.get,
        os.path.join(STATIC, 'monsters', 'touch', '96'),
        lambda n: int(n[:-5]) if n[:-5].isdigit() else None,
        (96, 96), args.sample, args.threshold, rng,
        ext='.webp', thumbnail=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
