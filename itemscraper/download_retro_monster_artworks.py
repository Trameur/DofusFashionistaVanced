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

"""Extract the Retro monster artworks from the official 1.29 client.

First-hand source: Ankama's own game files, served by the Cytrus CDN that
the Ankama Launcher uses (cytrus.cdn.ankama.com). The client ships one
artwork clip per gfxId in clips/artworks/big/<gfxId>.swf; the official
lang (retro_raw/monsters_fr.json, category "monsters") maps each monster
to its gfxId. No fan site involved.

The clips are Flash vectors placed off-canvas (the game slides them in at
runtime), so a plain frame render comes out blank. The working chain is:
  1. read the Cytrus manifest (FlatBuffers) and download the clip;
  2. export the frame as SVG with JPEXS ffdec;
  3. drop the stage background, the invisible guide shapes and the
     runtime _mcMask helper, then set the viewBox to the real content
     (every path point pushed through the placement matrices);
  4. rasterize with resvg, crop to the alpha bounding box with Pillow,
     store as 96px WebP under chardata/monsters/retro/96/<ankama_id>.webp
     (same layout, size and quality as the other versions).

External tools (both free software, fetched once by hand): JPEXS ffdec
(ffdec.jar, needs a Java runtime) and resvg. Point to them with
--ffdec-jar/--java/--resvg or the FFDEC_JAR/JAVA_EXE/RESVG_EXE env vars.
Without them the script warns and exits 0 so the retro pipeline can run
on machines that only need the committed WebPs.

Usage (from itemscraper/):
    python download_retro_monster_artworks.py [--workers 6]
"""

import argparse
import io
import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)

CYTRUS_BASE = 'https://cytrus.cdn.ankama.com'
DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                       'items_retro.db')
LANG_MONSTERS = os.path.join(CURRENT_DIR, 'retro_raw', 'monsters_fr.json')
SWF_CACHE_DIR = os.path.join(CURRENT_DIR, 'retro_raw', 'artworks_big')
ARTWORK_PREFIX = 'resources/app/retroclient/clips/artworks/big/'
SIZE = 96

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'
ET.register_namespace('', SVG_NS)
ET.register_namespace('xlink', XLINK_NS)
_NUM = re.compile(r'-?\d+(?:\.\d+)?(?:e-?\d+)?')


def target_dirs():
    parts = ['monsters', 'retro', '96']
    return [
        os.path.join(ROOT, 'fashionsite', 'chardata', 'static', 'chardata',
                     *parts),
        os.path.join(ROOT, 'fashionsite', 'staticfiles', 'chardata', *parts),
    ]


def fetch_bytes(url, byte_range=None):
    headers = {'User-Agent': 'Mozilla/5.0 (DofusFashionista asset sync)'}
    if byte_range:
        headers['Range'] = 'bytes=%d-%d' % byte_range
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# Cytrus v6 manifest (FlatBuffers). Community-documented schema:
#   Manifest { fragments:[Fragment] }
#   Fragment { name:string; files:[File]; bundles:[Bundle] }
#   File     { name:string; size:long; hash:[byte]; chunks:[Chunk] }
#   Bundle   { hash:[byte]; chunks:[Chunk] }
#   Chunk    { hash:[byte]; size:long; offset:long }

def _field_pos(buf, table_pos, slot):
    vtable_pos = table_pos - struct.unpack_from('<i', buf, table_pos)[0]
    vtable_size = struct.unpack_from('<H', buf, vtable_pos)[0]
    entry = 4 + 2 * slot
    if entry >= vtable_size:
        return None
    rel = struct.unpack_from('<H', buf, vtable_pos + entry)[0]
    return table_pos + rel if rel else None


def _string(buf, table_pos, slot):
    pos = _field_pos(buf, table_pos, slot)
    if pos is None:
        return None
    spos = pos + struct.unpack_from('<I', buf, pos)[0]
    length = struct.unpack_from('<I', buf, spos)[0]
    return buf[spos + 4:spos + 4 + length].decode('utf-8')


def _int64(buf, table_pos, slot):
    pos = _field_pos(buf, table_pos, slot)
    return struct.unpack_from('<q', buf, pos)[0] if pos is not None else 0


def _byte_vector_hex(buf, table_pos, slot):
    pos = _field_pos(buf, table_pos, slot)
    if pos is None:
        return ''
    vpos = pos + struct.unpack_from('<I', buf, pos)[0]
    length = struct.unpack_from('<I', buf, vpos)[0]
    return bytes(buf[vpos + 4:vpos + 4 + length]).hex()


def _table_vector(buf, table_pos, slot):
    pos = _field_pos(buf, table_pos, slot)
    if pos is None:
        return []
    vpos = pos + struct.unpack_from('<I', buf, pos)[0]
    length = struct.unpack_from('<I', buf, vpos)[0]
    out = []
    for i in range(length):
        el = vpos + 4 + 4 * i
        out.append(el + struct.unpack_from('<I', buf, el)[0])
    return out


def _chunk(buf, pos):
    return {'hash': _byte_vector_hex(buf, pos, 0),
            'size': _int64(buf, pos, 1),
            'offset': _int64(buf, pos, 2)}


def load_fragment(manifest_buf, fragment_name):
    """The fragment's files ({name: file}) and chunk map ({hash: location})."""
    root = struct.unpack_from('<I', manifest_buf, 0)[0]
    for fpos in _table_vector(manifest_buf, root, 0):
        if _string(manifest_buf, fpos, 0) != fragment_name:
            continue
        files = {}
        for filepos in _table_vector(manifest_buf, fpos, 1):
            name = _string(manifest_buf, filepos, 0)
            files[name] = {
                'size': _int64(manifest_buf, filepos, 1),
                'hash': _byte_vector_hex(manifest_buf, filepos, 2),
                'chunks': [_chunk(manifest_buf, c)
                           for c in _table_vector(manifest_buf, filepos, 3)],
            }
        chunk_map = {}
        for bpos in _table_vector(manifest_buf, fpos, 2):
            bundle_hash = _byte_vector_hex(manifest_buf, bpos, 0)
            for c in _table_vector(manifest_buf, bpos, 1):
                chunk = _chunk(manifest_buf, c)
                chunk_map[chunk['hash']] = (bundle_hash, chunk['offset'])
        return files, chunk_map
    raise RuntimeError('fragment %r not found in manifest' % fragment_name)


def download_manifest():
    cytrus = json.loads(fetch_bytes(CYTRUS_BASE + '/cytrus.json'))
    version = cytrus['games']['retro']['platforms']['windows']['main']
    print('retro client version: %s' % version)
    url = '%s/retro/releases/main/windows/%s.manifest' % (CYTRUS_BASE, version)
    return fetch_bytes(url)


def download_file(entry, chunk_map, out_path):
    chunks = sorted(entry['chunks'], key=lambda c: c['offset']) or [
        {'hash': entry['hash'], 'size': entry['size']}]
    pieces = []
    for chunk in chunks:
        bundle_hash, offset = chunk_map[chunk['hash']]
        url = '%s/retro/bundles/%s/%s' % (CYTRUS_BASE, bundle_hash[:2],
                                          bundle_hash)
        pieces.append(fetch_bytes(url, (offset, offset + chunk['size'] - 1)))
    blob = b''.join(pieces)
    with open(out_path, 'wb') as fh:
        fh.write(blob)


# ---------------------------------------------------------------------------
# SWF frame SVG -> cropped PNG

def _matrix(transform):
    m = re.match(r'\s*matrix\(([^)]*)\)', transform or '')
    if not m:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return tuple(float(x) for x in m.group(1).replace(',', ' ').split())


def _mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _paths_of(el, defs, depth=0):
    """Every path el draws, resolving <use> references (sprite defs hold
    no direct <path> children, only uses of other defs)."""
    if depth > 8:
        return
    tag = el.tag.rsplit('}', 1)[-1]
    if tag == 'path':
        yield el
    elif tag == 'use':
        href = (el.get('{%s}href' % XLINK_NS) or el.get('href') or '')
        target = defs.get(href.lstrip('#'))
        if target is not None:
            yield from _paths_of(target, defs, depth + 1)
    else:
        for child in el:
            yield from _paths_of(child, defs, depth)


def _is_invisible(el, defs):
    """True for the guide shapes: paths everywhere but none drawn. A def
    with no path at any depth draws nothing either way, so keep it."""
    paths = list(_paths_of(el, defs))
    if not paths:
        return False
    for path in paths:
        if (path.get('fill', 'black') != 'none'
                and float(path.get('fill-opacity', '1') or 1) > 0):
            return False
        if (path.get('stroke', 'none') != 'none'
                and float(path.get('stroke-opacity', '1') or 1) > 0):
            return False
    return True


def _collect_points(el, defs, parent_matrix, out, depth=0):
    if depth > 8:
        return
    local = _mul(parent_matrix, _matrix(el.get('transform')))
    tag = el.tag.rsplit('}', 1)[-1]
    if tag == 'path':
        numbers = _NUM.findall(el.get('d', ''))
        it = iter(numbers)
        for x in it:
            y = next(it, None)
            if y is None:
                break
            a, b, c, d, e, f = local
            x, y = float(x), float(y)
            out.append((a * x + c * y + e, b * x + d * y + f))
    elif tag == 'use':
        href = (el.get('{%s}href' % XLINK_NS) or el.get('href') or '')
        target = defs.get(href.lstrip('#'))
        if target is not None:
            _collect_points(target, defs, local, out, depth + 1)
    else:
        for child in el:
            _collect_points(child, defs, local, out, depth)


def svg_to_cropped_png(svg_path, png_path, resvg_exe, target=512):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    defs = {}
    for defs_el in root.findall('{%s}defs' % SVG_NS):
        for el in defs_el:
            if el.get('id'):
                defs[el.get('id')] = el

    points = []
    for group in root.findall('{%s}g' % SVG_NS):
        group_m = _matrix(group.get('transform'))
        for el in list(group):
            tag = el.tag.rsplit('}', 1)[-1]
            if tag == 'rect':
                group.remove(el)
                continue
            if tag == 'use':
                if 'mask' in (el.get('id') or '').lower():
                    group.remove(el)
                    continue
                href = (el.get('{%s}href' % XLINK_NS) or el.get('href') or '')
                target_el = defs.get(href.lstrip('#'))
                if target_el is not None and _is_invisible(target_el, defs):
                    group.remove(el)
                    continue
            _collect_points(el, defs, group_m, points)

    if not points:
        return False
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    pad = 4
    width = max(xs) - min(xs) + 2 * pad
    height = max(ys) - min(ys) + 2 * pad
    root.set('viewBox', '%f %f %f %f'
             % (min(xs) - pad, min(ys) - pad, width, height))
    root.set('width', '%fpx' % width)
    root.set('height', '%fpx' % height)

    tmp_svg = png_path + '.svg'
    tree.write(tmp_svg, encoding='utf-8', xml_declaration=True)
    try:
        subprocess.run(
            [resvg_exe, '--zoom', '%f' % (target / max(width, height)),
             tmp_svg, png_path],
            check=True, capture_output=True)
    finally:
        os.remove(tmp_svg)

    image = Image.open(png_path).convert('RGBA')
    bbox = image.getbbox()
    if not bbox:
        os.remove(png_path)
        return False
    image.crop(bbox).save(png_path)
    return True


def render_swf(swf_path, webp_name, dirs, java, ffdec_jar, resvg_exe):
    with tempfile.TemporaryDirectory(prefix='retro_art_') as tmp:
        subprocess.run(
            [java, '-jar', ffdec_jar, '-format', 'frame:svg',
             '-export', 'frame', tmp, swf_path],
            check=True, capture_output=True)
        svg_path = os.path.join(tmp, '1.svg')
        if not os.path.exists(svg_path):
            return False
        png_path = os.path.join(tmp, 'render.png')
        if not svg_to_cropped_png(svg_path, png_path, resvg_exe):
            return False
        image = Image.open(png_path).convert('RGBA')
        image.thumbnail((SIZE, SIZE), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, 'WEBP', quality=82, method=6)
    for directory in dirs:
        with open(os.path.join(directory, webp_name), 'wb') as fh:
            fh.write(buffer.getvalue())
    return True


# ---------------------------------------------------------------------------

def find_tool(explicit, env_var, candidates):
    if explicit:
        return explicit
    if os.environ.get(env_var):
        return os.environ[env_var]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def monster_gfx_ids():
    """ankama id -> gfxId for every monster that has an encyclopedia page."""
    with open(LANG_MONSTERS, encoding='utf-8') as fh:
        lang = json.load(fh)
    gfx_of = {int(mid): m.get('g') for mid, m in lang['M'].items()
              if isinstance(m, dict) and str(mid).isdigit()}
    con = sqlite3.connect(DB_PATH)
    known = [row[0] for row in con.execute(
        'SELECT DISTINCT monster_ankama_id FROM monster_names')]
    con.close()
    return {mid: gfx_of[mid] for mid in known if gfx_of.get(mid)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--java', help='java executable')
    parser.add_argument('--ffdec-jar', help='path to ffdec.jar')
    parser.add_argument('--resvg', help='resvg executable')
    args = parser.parse_args()

    java = find_tool(args.java, 'JAVA_EXE', ['java'])
    ffdec_jar = args.ffdec_jar or os.environ.get('FFDEC_JAR')
    resvg_exe = find_tool(args.resvg, 'RESVG_EXE', ['resvg'])
    if not (java and ffdec_jar and os.path.exists(ffdec_jar) and resvg_exe):
        print('WARNING: java + ffdec.jar + resvg are needed to render the '
              'artworks (see the module docstring); skipping, the committed '
              'WebPs stay as they are.')
        return 0
    if not os.path.exists(LANG_MONSTERS):
        print('WARNING: %s missing (run the retro lang download step first); '
              'skipping.' % LANG_MONSTERS)
        return 0

    dirs = target_dirs()
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)
    os.makedirs(SWF_CACHE_DIR, exist_ok=True)

    wanted = monster_gfx_ids()
    todo = {mid: gfx for mid, gfx in wanted.items()
            if not all(os.path.exists(os.path.join(d, '%d.webp' % mid))
                       for d in dirs)}
    print('monsters with a page: %d, to render: %d' % (len(wanted), len(todo)))
    if not todo:
        print('done: everything already rendered')
        return 0

    manifest = download_manifest()
    files, chunk_map = load_fragment(manifest, 'classic')

    counts = {'ok': 0, 'no_artwork': 0, 'empty': 0, 'error': 0}

    def process(item):
        mid, gfx = item
        entry = files.get('%s%d.swf' % (ARTWORK_PREFIX, gfx))
        if entry is None:
            return 'no_artwork', mid
        swf_path = os.path.join(SWF_CACHE_DIR, '%d.swf' % gfx)
        try:
            if not os.path.exists(swf_path):
                download_file(entry, chunk_map, swf_path)
            rendered = render_swf(swf_path, '%d.webp' % mid, dirs,
                                  java, ffdec_jar, resvg_exe)
            return ('ok' if rendered else 'empty'), mid
        except Exception as exc:
            print('  ERROR %d (gfx %d): %s' % (mid, gfx, exc))
            return 'error', mid

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for status, mid in pool.map(process, sorted(todo.items())):
            counts[status] += 1
            done = sum(counts.values())
            if done % 100 == 0:
                print('  %d/%d %s' % (done, len(todo), counts))
    print('done: %s' % counts)
    return 0 if counts['error'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
