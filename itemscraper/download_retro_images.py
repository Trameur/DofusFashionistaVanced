#!/usr/bin/env python3
"""
download_retro_images.py: render Dofus Retro item/mount/pet icons.

First-hand source: the official 1.29 client served by Ankama's Cytrus CDN
(the community Cyberia CDN mirror was used before the sourcing policy of
2026-07-20). Each icon is a Flash clip at clips/items/<type>/<gfx>.swf;
the type/gfx mapping comes from the official lang (retro_raw/items_*.json)
exactly like before.

Rendering: JPEXS ffdec's own frame renderer (the SVG+resvg chain used for
the monster artworks mis-renders some icon gradients, e.g. Toady). Frame
exports are always composited on the stage color, so the clip is rendered
TWICE, once on a black and once on a white stage (the SetBackgroundColor
tag is patched in a temp copy), and the true straight-alpha image is
recovered pixel by pixel from the pair (alpha = 255 - (white - black);
these icons genuinely use translucency, e.g. Toady's spots). The result is
cropped, centered on a square canvas and stored as the 60x60 PNG that
image_store.get_image_url expects:

  fashionsite/chardata/static/chardata/{items,pets}/retro/60x60/<normalized_name>-60-60.png

External tools: JPEXS ffdec (needs Java), see
download_retro_monster_artworks. Without them the script warns and exits 0
so pipelines keep the committed icons.

Idempotent: skips icons already on disk unless --force. A gfx missing in
the client leaves the existing file untouched.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'fashionistapulp'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import struct
import zlib

import numpy as np

from fashionistapulp.fashion_util import normalize_name, safe_icon_name
from get_equipments_retro import TYPE_MAP
from download_retro_monster_artworks import (
    download_manifest, load_fragment, download_file, find_tool)

STATIC = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata'
ICON_PREFIX = 'resources/app/retroclient/clips/items/'
CACHE_DIR = Path(__file__).resolve().parent / 'retro_raw' / 'item_icons'
SIZE = 60
ZOOM = 4
# Content fills the square minus a small margin, like the original icons.
MARGIN = 0.06


def _with_background(swf_bytes, rgb):
    """The SWF re-written uncompressed with its SetBackgroundColor patched."""
    data = swf_bytes
    if data[:3] == b'CWS':
        data = data[:8] + zlib.decompress(data[8:])
    data = bytearray(data)
    nbits = data[8] >> 3
    pos = 8 + (5 + 4 * nbits + 7) // 8 + 4
    while pos < len(data):
        code_len = struct.unpack_from('<H', data, pos)[0]
        code, length = code_len >> 6, code_len & 0x3F
        pos += 2
        if length == 0x3F:
            length = struct.unpack_from('<I', data, pos)[0]
            pos += 4
        if code == 9:  # SetBackgroundColor
            data[pos:pos + 3] = bytes(rgb)
            break
        if code == 0:
            return None
        pos += length
    else:
        return None
    data[0:3] = b'FWS'
    struct.pack_into('<I', data, 4, len(data))
    return bytes(data)


def render_icon(swf_path, java, ffdec_jar):
    """60x60 straight-alpha PNG bytes from an item icon clip, or None."""
    swf_bytes = Path(swf_path).read_bytes()
    on_white = _with_background(swf_bytes, (255, 255, 255))
    on_black = _with_background(swf_bytes, (0, 0, 0))
    if on_white is None:
        return None
    with tempfile.TemporaryDirectory(prefix='retro_icon_') as tmp:
        renders = []
        for label, blob in (('w', on_white), ('b', on_black)):
            swf = os.path.join(tmp, label + '.swf')
            Path(swf).write_bytes(blob)
            out_dir = os.path.join(tmp, label)
            subprocess.run(
                [java, '-jar', ffdec_jar, '-zoom', str(ZOOM),
                 '-format', 'frame:png', '-export', 'frame', out_dir, swf],
                check=True, capture_output=True)
            png = os.path.join(out_dir, '1.png')
            if not os.path.exists(png):
                return None
            renders.append(np.asarray(
                Image.open(png).convert('RGB'), dtype=np.int16))
        white_r, black_r = renders
    # c_white = a*C + (1-a)*255 and c_black = a*C, per channel, so the
    # channel-averaged difference gives (1-a)*255 and black is the
    # premultiplied color.
    alpha = 255 - (white_r - black_r).clip(0, 255).mean(axis=2)
    safe = np.maximum(alpha, 1)
    color = (black_r * 255.0 / safe[:, :, None]).clip(0, 255)
    rgba = np.dstack([color, alpha]).astype(np.uint8)
    image = Image.fromarray(rgba, 'RGBA')
    bbox = image.getbbox()
    if not bbox:
        return None
    image = image.crop(bbox)
    side = int(max(image.size) * (1 + 2 * MARGIN))
    square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - image.width) // 2,
                         (side - image.height) // 2), image)
    out = io.BytesIO()
    square.resize((SIZE, SIZE), Image.LANCZOS).save(out, format='PNG')
    return out.getvalue()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw-dir', default=str(Path(__file__).resolve().parent / 'retro_raw'))
    p.add_argument('--lang', default='fr')
    p.add_argument('--force', action='store_true', help='Re-render icons already on disk')
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--java', help='java executable')
    p.add_argument('--ffdec-jar', help='path to ffdec.jar')
    args = p.parse_args(argv)

    java = find_tool(args.java, 'JAVA_EXE', ['java'])
    ffdec_jar = args.ffdec_jar or os.environ.get('FFDEC_JAR')
    if not (java and ffdec_jar and os.path.exists(ffdec_jar)):
        print('WARNING: java + ffdec.jar are needed to render the icons '
              '(see download_retro_monster_artworks); skipping, the '
              'committed PNGs stay as they are.')
        return 0

    raw = Path(args.raw_dir)
    items = json.loads((raw / f'items_{args.lang}.json').read_text(encoding='utf-8'))['I']['u']
    # No lang file is complete and French is the thinnest, so get_equipments_retro
    # fills the gaps from the other four, in this order. Read only the French one
    # here and 52 items the database does carry were never offered to the
    # renderer at all: they showed the placeholder.
    for lang in ('en', 'es', 'pt', 'de'):
        if lang == args.lang:
            continue
        path = raw / f'items_{lang}.json'
        if not path.exists():
            continue
        other = json.loads(path.read_text(encoding='utf-8'))['I']['u']
        for iid, it in other.items():
            if iid not in items and isinstance(it, dict):
                items[iid] = it
    en_path = raw / 'items_en.json'
    names_en = {}
    if en_path.exists():
        en_items = json.loads(en_path.read_text(encoding='utf-8'))['I']['u']
        names_en = {k: v.get('n') for k, v in en_items.items() if isinstance(v, dict)}

    # (type, gfx) -> destinations that need a render.
    todo = {}
    skipped = bad_name = 0
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
        # safe_icon_name mirrors image_store's lookup ("Wand Else?" is
        # requested without the '?', which Windows cannot store anyway).
        dest = (STATIC / type_dir / 'retro' / '60x60'
                / ('%s-60-60.png' % safe_icon_name(normalize_name(name))))
        try:
            if dest.exists() and not args.force:
                skipped += 1
                continue
        except OSError:
            bad_name += 1
            continue
        todo.setdefault((type_id, str(gfx)), set()).add(dest)

    print(f'icons to render: {len(todo)} (for {sum(len(d) for d in todo.values())} files), '
          f'skipped(existing)={skipped}')
    if not todo:
        print('Done. nothing to render')
        return 0

    manifest = download_manifest()
    files, chunk_map = load_fragment(manifest, 'classic')
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    counts = {'ok': 0, 'missing': 0, 'empty': 0, 'error': 0}
    written = bad_write = 0

    def process(key):
        type_id, gfx = key
        entry = files.get('%s%s/%s.swf' % (ICON_PREFIX, type_id, gfx))
        if entry is None:
            return key, 'missing', None
        swf_path = CACHE_DIR / ('%s_%s.swf' % (type_id, gfx))
        try:
            if not swf_path.exists():
                download_file(entry, chunk_map, str(swf_path))
            png = render_icon(swf_path, java, ffdec_jar)
            return key, ('ok' if png else 'empty'), png
        except Exception as exc:
            print('  ERROR %s/%s: %s' % (type_id, gfx, exc))
            return key, 'error', None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for key, status, png in pool.map(process, sorted(todo)):
            counts[status] += 1
            if png:
                for dest in todo[key]:
                    try:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(png)
                        written += 1
                    except OSError:
                        bad_write += 1
            done = sum(counts.values())
            if done % 250 == 0:
                print('  %d/%d %s' % (done, len(todo), counts))

    print(f'Done. renders={counts} files written={written} '
          f'bad-filename(OS)={bad_name + bad_write}')
    return 0 if counts['error'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
