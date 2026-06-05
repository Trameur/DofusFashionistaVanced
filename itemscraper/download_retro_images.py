#!/usr/bin/env python3
"""
download_retro_images.py — fetch Dofus Retro item/mount/pet icons.

Source: the community Cyberia CDN (github.com/Lounek09/Cyberia.Cdn, served at
amphibian.fr), which has real Retro icons keyed by <item_type>/<size>/<gfx>.png.
We pull the 64px icon, resize to 60x60, and save it under the same name the app's
image_store.get_image_url expects, so Retro items show real icons.

  CDN icon : https://raw.githubusercontent.com/Lounek09/Cyberia.Cdn/main/images/dofus/items/<type>/64/<gfx>.png
  saved as : fashionsite/chardata/static/chardata/{items,pets}/retro/60x60/<normalized_name>-60-60.png

Idempotent: skips icons already on disk unless --force.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'fashionistapulp'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fashionistapulp.fashion_util import normalize_name
from get_equipments_retro import TYPE_MAP

CDN = 'https://raw.githubusercontent.com/Lounek09/Cyberia.Cdn/main/images/dofus/items/%s/64/%s.png'
STATIC = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw-dir', default=str(Path(__file__).resolve().parent / 'retro_raw'))
    p.add_argument('--lang', default='fr')
    p.add_argument('--force', action='store_true', help='Re-download icons already on disk')
    args = p.parse_args(argv)

    raw = Path(args.raw_dir)
    items = json.loads((raw / f'items_{args.lang}.json').read_text(encoding='utf-8'))['I']['u']
    en_path = raw / 'items_en.json'
    names_en = {}
    if en_path.exists():
        en_items = json.loads(en_path.read_text(encoding='utf-8'))['I']['u']
        names_en = {k: v.get('n') for k, v in en_items.items() if isinstance(v, dict)}

    session = requests.Session()
    cache = {}  # (type, gfx) -> resized PNG bytes or None (missing on CDN)
    written = skipped = missing = bad_name = 0

    for iid, it in items.items():
        if not isinstance(it, dict):
            continue
        type_id = str(it.get('t'))
        if type_id not in TYPE_MAP:
            continue
        gfx = it.get('g')
        if gfx is None:
            continue
        name = names_en.get(iid) or it.get('n') or ''
        if not name:
            continue
        type_dir = 'pets' if TYPE_MAP[type_id][0] == 'Pet' else 'items'
        dest = STATIC / type_dir / 'retro' / '60x60' / ('%s-60-60.png' % normalize_name(name))
        try:
            if dest.exists() and not args.force:
                skipped += 1
                continue
        except OSError:
            bad_name += 1  # name has chars invalid on this OS (e.g. '?' on Windows)
            continue

        key = (type_id, str(gfx))
        if key not in cache:
            cache[key] = _fetch_resized(session, type_id, gfx)
        png = cache[key]
        if png is None:
            missing += 1
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(png)
        except OSError:
            bad_name += 1  # filename rejected by the OS (Windows: ? : * etc.); fine on Linux
            continue
        written += 1
        if written % 500 == 0:
            print(f'  ... {written} written')

    print(f'Done. written={written} skipped(existing)={skipped} missing(no CDN icon)={missing} '
          f'bad-filename(OS)={bad_name}, unique icons fetched={sum(1 for v in cache.values() if v)}')
    return 0


def _fetch_resized(session, type_id, gfx):
    try:
        r = session.get(CDN % (type_id, gfx), timeout=30)
        if r.status_code != 200 or not r.content:
            return None
        img = Image.open(io.BytesIO(r.content)).convert('RGBA').resize((60, 60), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='PNG')
        return out.getvalue()
    except Exception:
        return None


if __name__ == '__main__':
    raise SystemExit(main())
