#!/usr/bin/env python3
"""
Fetch Dofus Touch item and pet icons.

Icons live on the Touch assets CDN at assetsUrl + "/gfx/items/<iconId>.png", the
same path the client loads them from. We read assetsUrl from config.json so it
tracks the current asset version.

  icon  : https://dofustouch.cdn.ankama.com/assets/<ver>_<hash>/gfx/items/<iconId>.png
  saved : fashionsite/chardata/static/chardata/{items,pets}/touch/60x60/<en_name>-60-60.png

Each icon is resized to 60x60 and saved under the name image_store.get_image_url
expects for the touch version. Icons already on disk are skipped unless --force.
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

from fashionistapulp.fashion_util import normalize_name, safe_icon_name
from get_equipments_touch import TYPE_MAP

CONFIG_URL = "https://earlyproxy.touch.dofus.com/config.json"
FALLBACK_ASSETS_URL = ("https://dofustouch.cdn.ankama.com/assets/"
                       "3.2.4_sF,kf0I9t9aOjYb3X_EPiZJZYCo.brI5")
USER_AGENT = "Dofus/2 CFNetwork"
STATIC = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata'
# Mounts have no icon; the Touch CDN renders them from their "look" string.
MOUNT_RENDERER = 'https://static.ankama.com/dofustouch/renderer/look/%s/full/1/60_60-10.png'
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def resolve_assets_url() -> str:
    try:
        r = requests.get(CONFIG_URL + '?lang=fr', headers={'User-Agent': USER_AGENT}, timeout=30)
        r.raise_for_status()
        url = r.json().get('assetsUrl')
        if url:
            return url.rstrip('/')
    except Exception as exc:
        print(f"  ! could not read config.json ({exc}); using fallback", file=sys.stderr)
    return FALLBACK_ASSETS_URL


def _fetch_resized(session, base_url, icon_id):
    try:
        r = session.get('%s/gfx/items/%s.png' % (base_url, icon_id),
                        headers={'User-Agent': USER_AGENT}, timeout=30)
        if r.status_code != 200 or not r.content:
            return None
        img = Image.open(io.BytesIO(r.content)).convert('RGBA').resize((60, 60), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='PNG')
        return out.getvalue()
    except Exception:
        return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw-dir', default=str(Path(__file__).resolve().parent / 'touch_raw'))
    p.add_argument('--assets-url', default=None, help='Override assetsUrl (else resolved live)')
    p.add_argument('--force', action='store_true', help='Re-download icons already on disk')
    args = p.parse_args(argv)

    raw = Path(args.raw_dir)
    items = json.loads((raw / 'Items_fr.json').read_text(encoding='utf-8'))
    en_path = raw / 'Items_en.json'
    names_en = {}
    if en_path.exists():
        en_items = json.loads(en_path.read_text(encoding='utf-8'))
        names_en = {k: v.get('nameId') for k, v in en_items.items() if isinstance(v, dict)}

    base_url = args.assets_url.rstrip('/') if args.assets_url else resolve_assets_url()
    print(f"Dofus Touch assets CDN: {base_url}")

    session = requests.Session()
    cache = {}  # icon_id -> resized PNG bytes or None (missing on CDN)
    written = skipped = missing = bad_name = 0

    for iid, it in items.items():
        if not isinstance(it, dict):
            continue
        if it.get('typeId') not in TYPE_MAP:
            continue
        icon_id = it.get('iconId')
        if not icon_id:
            continue
        name = names_en.get(iid) or it.get('nameId') or ''
        if not name:
            continue
        type_dir = 'pets' if TYPE_MAP[it['typeId']][0] == 'Pet' else 'items'
        dest = STATIC / type_dir / 'touch' / '60x60' / ('%s-60-60.png' % safe_icon_name(normalize_name(name)))
        try:
            if dest.exists() and not args.force:
                skipped += 1
                continue
        except OSError:
            bad_name += 1
            continue

        if icon_id not in cache:
            cache[icon_id] = _fetch_resized(session, base_url, icon_id)
        png = cache[icon_id]
        if png is None:
            missing += 1
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(png)
        except OSError:
            bad_name += 1
            continue
        written += 1
        if written % 500 == 0:
            print(f'  ... {written} written')

    print(f'Done. written={written} skipped(existing)={skipped} missing(no CDN icon)={missing} '
          f'bad-filename(OS)={bad_name}, unique icons fetched={sum(1 for v in cache.values() if v)}')

    # Mounts: rendered by the Touch CDN from their look string (download_touch_mounts.py).
    mounts_path = raw / 'mounts.json'
    if mounts_path.exists():
        mounts = json.loads(mounts_path.read_text(encoding='utf-8'))
        m_written = m_skipped = m_missing = 0
        for m in mounts:
            look = m.get('look')
            name = m.get('name_en')
            if not look or not name:
                continue
            dest = STATIC / 'pets' / 'touch' / '60x60' / ('%s-60-60.png' % normalize_name(name))
            try:
                if dest.exists() and not args.force:
                    m_skipped += 1
                    continue
            except OSError:
                continue
            try:
                r = session.get(MOUNT_RENDERER % look.encode('utf-8').hex(),
                                headers={'User-Agent': WEB_UA}, timeout=30)
                if r.status_code != 200 or not r.content:
                    m_missing += 1
                    continue
                img = Image.open(io.BytesIO(r.content)).convert('RGBA').resize((60, 60), Image.LANCZOS)
                out = io.BytesIO()
                img.save(out, format='PNG')
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(out.getvalue())
                m_written += 1
            except Exception:
                m_missing += 1
        print(f'Mounts: written={m_written} skipped(existing)={m_skipped} missing={m_missing}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
