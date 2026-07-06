#!/usr/bin/env python3
"""
download_retro_spell_images.py: fetch Dofus Retro damage-spell icons.

Source: the community Cyberia CDN (github.com/Lounek09/Cyberia.Cdn), which serves
Retro spell icons keyed by spell id at images/dofus/spells/<size>/<id>.jpg. We only
need icons for the damage spells the app actually displays (RETRO_DAMAGE_SPELLS), so
this reads retro_damage_spells.json (which carries each spell's id + French name),
pulls the 128px icon, resizes to 96x96 PNG, and saves it under the name the spell
view expects.

  CDN icon : https://raw.githubusercontent.com/Lounek09/Cyberia.Cdn/main/images/dofus/spells/128/<id>.jpg
  saved as : fashionsite/chardata/static/chardata/spells/retro/<french_name>.png

Idempotent: skips icons already on disk unless --force.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CDN = 'https://raw.githubusercontent.com/Lounek09/Cyberia.Cdn/main/images/dofus/spells/128/%s.jpg'
DEST = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata' / 'spells' / 'retro'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--spells', default=str(Path(__file__).resolve().parent / 'retro' / 'retro_damage_spells.json'))
    p.add_argument('--force', action='store_true', help='Re-download icons already on disk')
    args = p.parse_args(argv)

    by_class = json.loads(Path(args.spells).read_text(encoding='utf-8'))
    # Collect unique (id, name); the same spell can appear under several classes.
    seen = {}
    for spells in by_class.values():
        for s in spells:
            sid, name = s.get('id'), s.get('name')
            if sid is not None and name:
                seen.setdefault(name, sid)

    session = requests.Session()
    written = skipped = missing = bad_name = 0
    for name, sid in seen.items():
        dest = DEST / ('%s.png' % name)
        try:
            if dest.exists() and not args.force:
                skipped += 1
                continue
        except OSError:
            bad_name += 1
            continue
        png = _fetch_resized(session, sid)
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

    print(f'Done. written={written} skipped(existing)={skipped} '
          f'missing(no CDN icon)={missing} bad-filename(OS)={bad_name}')
    return 0


def _fetch_resized(session, sid):
    try:
        r = session.get(CDN % sid, timeout=30)
        if r.status_code != 200 or not r.content:
            return None
        img = Image.open(io.BytesIO(r.content)).convert('RGBA').resize((96, 96), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='PNG')
        return out.getvalue()
    except Exception:
        return None


if __name__ == '__main__':
    raise SystemExit(main())
