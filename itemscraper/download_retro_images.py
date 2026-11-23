#!/usr/bin/env python3
"""
download_retro_images.py: render Dofus Retro item/mount/pet icons.

Each icon is a Flash clip at clips/items/<type>/<gfx>.swf in the official
1.29 client (Ankama's Cytrus CDN); the type/gfx mapping comes from the lang
files in retro_raw/items_*.json.

ffdec frame exports are always composited on the stage color, so each clip
is rendered twice, once on a black and once on a white stage (the
SetBackgroundColor tag is patched in a temp copy), and the straight-alpha
image is recovered from the pair. The result lands as the 60x60 PNG that
image_store.get_image_url expects:

  fashionsite/chardata/static/chardata/{items,pets}/retro/60x60/<normalized_name>-60-60.png

Needs JPEXS ffdec and Java (see download_retro_monster_artworks); without
them the script warns and exits 0. Skips icons already on disk unless
--force.

With --release beta the lang files come from retrobeta_raw and the clips from
the beta manifest; an icon is rendered into {items,pets}/retrobeta/60x60 only
when its clip is not the one main renders under that name (other type or gfx,
or another content hash), the others keep main's icon.
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

from fashionistapulp.fashion_util import normalize_name, safe_icon_name
from get_equipments_retro import TYPE_MAP
from download_retro_monster_artworks import (
    download_manifest, load_fragment, download_file, find_tool, clip_differs)
import retro_release

STATIC = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata'
ICON_PREFIX = 'resources/app/retroclient/clips/items/'
CACHE_DIR = Path(__file__).resolve().parent / 'retro_raw' / 'item_icons'
SIZE = 60
ZOOM = 4
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
    import numpy as np

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
    # c_white = a*C + (1-a)*255 and c_black = a*C per channel, so the averaged
    # difference gives (1-a)*255 and black is the premultiplied color.
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


def lang_items(raw, primary):
    """The items of a raw folder, gaps filled from the other languages, and their English names."""
    items = json.loads((raw / f'items_{primary}.json').read_text(encoding='utf-8'))['I']['u']
    # No lang file is complete and French is the thinnest, so the gaps come from
    # the other four, in the order get_equipments_retro uses.
    for lang in ('en', 'es', 'pt', 'de'):
        if lang == primary:
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
    return items, names_en


def icon_clips(items, names_en, release=retro_release.MAIN):
    """(item id, destination, (type, gfx)) for every item that has an icon."""
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
        # safe_icon_name mirrors image_store's lookup ("Wand Else?" is stored
        # without the '?', which Windows cannot put in a filename).
        dest = (STATIC / type_dir / retro_release.version_key(release) / '60x60'
                / ('%s-60-60.png' % safe_icon_name(normalize_name(name))))
        yield iid, dest, (type_id, str(gfx))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw-dir', default=None,
                   help='default retro_raw, or retrobeta_raw with --release beta')
    p.add_argument('--lang', default='fr')
    p.add_argument('--force', action='store_true', help='Re-render icons already on disk')
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--java', help='java executable')
    p.add_argument('--ffdec-jar', help='path to ffdec.jar')
    retro_release.add_release_argument(p)
    args = p.parse_args(argv)
    beta = retro_release.is_beta(args.release)
    if args.raw_dir is None:
        args.raw_dir = str(retro_release.raw_dir(args.release) if beta
                           else Path(__file__).resolve().parent / 'retro_raw')
    cache_dir = Path(args.raw_dir) / 'item_icons' if beta else CACHE_DIR

    java = find_tool(args.java, 'JAVA_EXE', ['java'])
    ffdec_jar = args.ffdec_jar or os.environ.get('FFDEC_JAR')
    if not (java and ffdec_jar and os.path.exists(ffdec_jar)):
        print('WARNING: java + ffdec.jar are needed to render the icons '
              '(see download_retro_monster_artworks); skipping, the '
              'committed PNGs stay as they are.')
        return 0

    items, names_en = lang_items(Path(args.raw_dir), args.lang)

    manifest = main_clips = None
    reused = 0
    if beta:
        main_items, main_names = lang_items(retro_release.raw_dir(), args.lang)
        main_clips = {}
        for _iid, dest, clip in icon_clips(main_items, main_names):
            main_clips.setdefault((dest.parents[2].name, dest.name), set()).add(clip)
        manifest = download_manifest(args.release)
        files, chunk_map = load_fragment(manifest, 'classic')
        main_files, _main_chunks = load_fragment(download_manifest(), 'classic')

    # (type, gfx) -> destinations that need a render.
    todo = {}
    skipped = bad_name = 0
    for iid, dest, clip in icon_clips(items, names_en, args.release):
        if main_clips is not None:
            path = '%s%s/%s.swf' % (ICON_PREFIX, clip[0], clip[1])
            if (clip in main_clips.get((dest.parents[2].name, dest.name), ())
                    and not clip_differs(path, files, main_files)):
                reused += 1
                continue
        try:
            if dest.exists() and not args.force:
                skipped += 1
                continue
        except OSError:
            bad_name += 1
            continue
        todo.setdefault(clip, set()).add(dest)

    print(f'icons to render: {len(todo)} (for {sum(len(d) for d in todo.values())} files), '
          f'skipped(existing)={skipped}')
    if beta:
        retro_release.notice(
            'item icons: %d clips to render for %d files, %d icons reuse the one of main, '
            '%d already rendered for the beta'
            % (len(todo), sum(len(d) for d in todo.values()), reused, skipped))
    if not todo:
        print('Done. nothing to render')
        return 0

    if manifest is None:
        manifest = download_manifest()
        files, chunk_map = load_fragment(manifest, 'classic')
    cache_dir.mkdir(parents=True, exist_ok=True)

    counts = {'ok': 0, 'missing': 0, 'empty': 0, 'error': 0}
    written = bad_write = 0

    def process(key):
        type_id, gfx = key
        entry = files.get('%s%s/%s.swf' % (ICON_PREFIX, type_id, gfx))
        if entry is None:
            return key, 'missing', None
        swf_path = cache_dir / ('%s_%s.swf' % (type_id, gfx))
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
    if beta:
        retro_release.notice('item icons rendered for the beta: %s, files written %d'
                             % (counts, written))
    return 0 if counts['error'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
