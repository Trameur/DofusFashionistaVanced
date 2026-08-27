#!/usr/bin/env python3
"""
download_retro_spell_images.py: Dofus Retro damage-spell icons.

The committed icons are Ankama's own 1.29 spell-book renders, served by the
old official web CDN and mirrored today by the community Cyberia CDN
(credited on /about). That mirror is frozen: a handful of spells never got
an icon there, and the mirror cannot produce new ones.

--compose-missing rebuilds those missing icons from first-hand parts:
  - the spell's icon recipe comes from the official lang
    (retro_raw/spells_fr.json, dict "i": up = stencil clip id, bc = the
    per-spell colors; proven against the existing icons: bc[3] is the disc
    color, pixel-exact);
  - the stencil clips/spells/icons/up/<id>.swf comes from the official
    client via the Cytrus CDN, rendered with ffdec + resvg (the shared
    helpers of download_retro_monster_artworks);
  - the ornate frame ring is learned from the committed icons themselves:
    per-pixel affine regression in bc[2]/bc[3] over the full set (the
    frame is fixed geometry recolored per spell, so the linear model
    reproduces it; the disc is then filled bc[3] and the stencil pasted
    in white, the dominant polarity of the set).

Needs java + ffdec + resvg (JAVA_EXE/FFDEC_JAR/RESVG_EXE or --java/
--ffdec-jar/--resvg) plus numpy; without them it warns and exits 0.

Saved as: fashionsite/chardata/static/chardata/spells/retro/<name_fr>.png
(96x96 PNG, the name the spell view expects). Existing files are never
overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / 'fashionistapulp'))

from fashionistapulp.reserved_filenames import safe_asset_stem  # noqa: E402

DEST = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata' / 'spells' / 'retro'
LANG_SPELLS = Path(__file__).resolve().parent / 'retro_raw' / 'spells_fr.json'
STENCIL_CACHE = Path(__file__).resolve().parent / 'retro_raw' / 'spell_stencils'
UP_PREFIX = 'resources/app/retroclient/clips/spells/icons/up/'
SIZE = 96
DISC_RADIUS = 29.5
GLYPH_MAX = 50


def load_targets(spells_path):
    """name -> spell id for every spell the app displays."""
    by_class = json.loads(Path(spells_path).read_text(encoding='utf-8'))
    targets = {}
    for spells in by_class.values():
        for s in spells:
            if s.get('id') is not None and s.get('name'):
                targets.setdefault(s['name'], s['id'])
    return targets


def compose_missing(missing, java, ffdec_jar, resvg_exe):
    import glob
    import subprocess
    import tempfile

    import numpy as np
    from PIL import Image

    from download_retro_monster_artworks import (
        download_manifest, load_fragment, download_file, svg_to_cropped_png)

    lang = json.loads(LANG_SPELLS.read_text(encoding='utf-8'))['S']
    targets_all = load_targets(
        Path(__file__).resolve().parent / 'retro' / 'retro_damage_spells.json')

    # Ring model: per-pixel affine in bc[2]/bc[3] over the committed icons.
    icons, bc2s, bc3s = [], [], []
    for p in sorted(glob.glob(str(DEST / '*.png'))):
        name = os.path.basename(p)[:-4]
        sid = targets_all.get(name)
        entry = lang.get(str(sid)) if sid is not None else None
        if not (isinstance(entry, dict) and isinstance(entry.get('i'), dict)):
            continue
        bc = entry['i']['bc']
        icons.append(np.asarray(
            Image.open(p).convert('RGB').resize((SIZE, SIZE))).astype(float))
        bc2s.append([(bc[2] >> s) & 255 for s in (16, 8, 0)])
        bc3s.append([(bc[3] >> s) & 255 for s in (16, 8, 0)])
    if len(icons) < 20:
        print('not enough committed icons to learn the frame (%d)' % len(icons))
        return 0
    icons = np.stack(icons)
    bc2s = np.array(bc2s, float)
    bc3s = np.array(bc3s, float)
    n = icons.shape[0]
    model = np.zeros((SIZE, SIZE, 3, 3))
    for ch in range(3):
        x = np.stack([np.ones(n), bc2s[:, ch], bc3s[:, ch]], axis=1)
        y = icons[:, :, :, ch].reshape(n, -1)
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        model[:, :, ch, :] = coef.T.reshape(SIZE, SIZE, 3)
    print('frame model learned from %d icons' % n)

    manifest = download_manifest()
    files, chunk_map = load_fragment(manifest, 'classic')
    STENCIL_CACHE.mkdir(parents=True, exist_ok=True)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    rad = np.hypot(yy - (SIZE - 1) / 2.0, xx - (SIZE - 1) / 2.0)

    written = failed = 0
    for name, sid in sorted(missing.items()):
        entry = lang.get(str(sid))
        info = entry.get('i') if isinstance(entry, dict) else None
        if not (isinstance(info, dict) and info.get('up', -1) > 0):
            print('  %s: no icon recipe in the lang' % name)
            failed += 1
            continue
        swf = STENCIL_CACHE / ('%d.swf' % info['up'])
        cdn_entry = files.get('%s%d.swf' % (UP_PREFIX, info['up']))
        if cdn_entry is None:
            print('  %s: stencil %d not in the client' % (name, info['up']))
            failed += 1
            continue
        try:
            if not swf.exists():
                download_file(cdn_entry, chunk_map, str(swf))
            with tempfile.TemporaryDirectory(prefix='retro_spell_') as tmp:
                subprocess.run(
                    [java, '-jar', ffdec_jar, '-format', 'frame:svg',
                     '-export', 'frame', tmp, str(swf)],
                    check=True, capture_output=True)
                mask_png = os.path.join(tmp, 'mask.png')
                if not svg_to_cropped_png(os.path.join(tmp, '1.svg'),
                                          mask_png, resvg_exe, target=256):
                    raise RuntimeError('empty stencil render')
                mask = Image.open(mask_png).convert('RGBA')
                mask.load()
        except Exception as exc:
            print('  %s: %s' % (name, exc))
            failed += 1
            continue

        bc2 = np.array([(info['bc'][2] >> s) & 255 for s in (16, 8, 0)], float)
        bc3 = np.array([(info['bc'][3] >> s) & 255 for s in (16, 8, 0)], float)
        img = (model[:, :, :, 0]
               + model[:, :, :, 1] * bc2.reshape(1, 1, 3)
               + model[:, :, :, 2] * bc3.reshape(1, 1, 3)).clip(0, 255)
        img[rad < DISC_RADIUS] = bc3
        out = Image.fromarray(img.astype(np.uint8), 'RGB').convert('RGBA')
        scale = GLYPH_MAX / max(mask.size)
        m = mask.resize((max(1, round(mask.width * scale)),
                         max(1, round(mask.height * scale))), Image.LANCZOS)
        white = Image.new('RGBA', m.size, (255, 255, 255, 255))
        white.putalpha(m.split()[3])
        out.paste(white, (SIZE // 2 - m.width // 2, SIZE // 2 - m.height // 2),
                  white)
        out.save(DEST / ('%s.png' % safe_asset_stem(name)))
        written += 1
        print('  %s: composed (up %d)' % (name, info['up']))
    print('composed=%d failed=%d' % (written, failed))
    return 0 if failed == 0 else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--spells', default=str(Path(__file__).resolve().parent / 'retro' / 'retro_damage_spells.json'))
    p.add_argument('--compose-missing', action='store_true',
                   help='Compose icons the frozen mirror never had, from '
                        'the official lang + client stencils')
    p.add_argument('--java', help='java executable')
    p.add_argument('--ffdec-jar', help='path to ffdec.jar')
    p.add_argument('--resvg', help='resvg executable')
    args = p.parse_args(argv)

    targets = load_targets(args.spells)
    missing = {}
    for name, sid in targets.items():
        try:
            if not (DEST / ('%s.png' % name)).exists():
                missing[name] = sid
        except OSError:
            continue
    print('spells: %d | icons present: %d | missing: %d'
          % (len(targets), len(targets) - len(missing), len(missing)))
    if not missing:
        return 0
    if not args.compose_missing:
        print('missing: %s' % sorted(missing))
        print('(the mirror of the old official CDN is frozen; use '
              '--compose-missing to build them from the client)')
        return 0

    from download_retro_monster_artworks import find_tool
    java = find_tool(args.java, 'JAVA_EXE', ['java'])
    ffdec_jar = args.ffdec_jar or os.environ.get('FFDEC_JAR')
    resvg_exe = find_tool(args.resvg, 'RESVG_EXE', ['resvg'])
    if not (java and ffdec_jar and os.path.exists(ffdec_jar) and resvg_exe):
        print('WARNING: java + ffdec.jar + resvg are needed to compose the '
              'missing icons; skipping, the committed PNGs stay as they are.')
        return 0
    return compose_missing(missing, java, ffdec_jar, resvg_exe)


if __name__ == '__main__':
    raise SystemExit(main())
