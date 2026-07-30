#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bake character skins into flat PNGs plus the pose the browser applies.

Each skin part is drawn once in its own local space; the bone frame supplies an
affine matrix per node. The page then just stacks images with a canvas
transform, so nothing about meshes or Unity has to exist client side.

    python itemscraper/bake_character_parts.py --skins <dir> --bone <bundle> --out <dir>

Produces <out>/parts/<skin>/<part>.png, <out>/parts/<skin>/parts.json with the
local bounds, and <out>/poses/<bone>.json with one entry per orientation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import warnings

import numpy as np
import UnityPy
from PIL import Image

UnityPy.config.FALLBACK_UNITY_VERSION = '2022.3.0f1'
try:
    from UnityPy.exceptions import UnityVersionFallbackWarning
    warnings.simplefilter('ignore', UnityVersionFallbackWarning)
except ImportError:
    warnings.filterwarnings('ignore', message='No valid Unity version found')

RECORD = 36
DELTA = 28
ORIENTATIONS = ('0', '1', '2', '5', '6')
PIXELS_PER_UNIT = 4.0

# A keyframe record is a flag word, then a matrix. The flag is a bitfield over
# 0x30: bit 0 says a symbol id follows, bit 2 adds a four byte colour before
# the matrix, which is why records are not all the same length.
FLAG_BASE = 0x30
FLAG_SYMBOL = 0x01
FLAG_COLOUR = 0x04
HEADER = 12


class Skin:

    def __init__(self, path):
        env = UnityPy.load(path)
        self.textures = []
        tree = None
        for obj in env.objects:
            if obj.type.name == 'Texture2D':
                self.textures.append(obj.read().image.convert('RGBA'))
            elif obj.type.name == 'MonoBehaviour':
                candidate = obj.read_typetree()
                if candidate.get('vertices'):
                    tree = candidate
        if tree is None:
            raise ValueError('%s has no mesh' % path)
        self.parts = dict(zip(tree['m_keys'], tree['m_values']))
        self.triangles = tree['triangles']
        self.vertices = tree['vertices']

    def geometry(self, name):
        pos, uv, faces = [], [], []
        for chunk in self.parts[name]['skinChunks']:
            base = len(pos)
            start = chunk['startVertexIndex']
            for vertex in self.vertices[start:start + chunk['vertexCount']]:
                pos.append((vertex['pos']['x'], vertex['pos']['y']))
                uv.append((vertex['uv']['x'], vertex['uv']['y']))
            idx = self.triangles[chunk['startIndexIndex']:
                                 chunk['startIndexIndex'] + chunk['indexCount']]
            for i in range(0, len(idx), 3):
                faces.append((base + idx[i], base + idx[i + 1], base + idx[i + 2],
                              chunk['textureIndex']))
        return np.array(pos, dtype=np.float64), np.array(uv, dtype=np.float64), faces


def bake_part(skin, name, ppu=PIXELS_PER_UNIT, pad=2):
    pos, uv, faces = skin.geometry(name)
    if not len(pos):
        return None, None
    min_x, min_y = pos.min(axis=0)
    max_x, max_y = pos.max(axis=0)
    width = int(np.ceil((max_x - min_x) * ppu)) + pad * 2
    height = int(np.ceil((max_y - min_y) * ppu)) + pad * 2
    if width <= 0 or height <= 0:
        return None, None

    screen = np.empty_like(pos)
    screen[:, 0] = (pos[:, 0] - min_x) * ppu + pad
    screen[:, 1] = (max_y - pos[:, 1]) * ppu + pad
    out = np.zeros((height, width, 4), dtype=np.uint8)

    for a, b, c, tex_index in faces:
        tri = screen[[a, b, c]]
        uvs = uv[[a, b, c]]
        texture = skin.textures[tex_index] if tex_index < len(skin.textures) else skin.textures[0]
        tex = np.asarray(texture)
        th, tw = tex.shape[0], tex.shape[1]

        lo_x = max(int(np.floor(tri[:, 0].min())), 0)
        hi_x = min(int(np.ceil(tri[:, 0].max())) + 1, width)
        lo_y = max(int(np.floor(tri[:, 1].min())), 0)
        hi_y = min(int(np.ceil(tri[:, 1].max())) + 1, height)
        if lo_x >= hi_x or lo_y >= hi_y:
            continue

        gx, gy = np.meshgrid(np.arange(lo_x, hi_x) + 0.5, np.arange(lo_y, hi_y) + 0.5)
        x1, y1 = tri[0]
        x2, y2 = tri[1]
        x3, y3 = tri[2]
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(det) < 1e-9:
            continue
        l1 = ((y2 - y3) * (gx - x3) + (x3 - x2) * (gy - y3)) / det
        l2 = ((y3 - y1) * (gx - x3) + (x1 - x3) * (gy - y3)) / det
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not inside.any():
            continue
        u = l1 * uvs[0, 0] + l2 * uvs[1, 0] + l3 * uvs[2, 0]
        v = l1 * uvs[0, 1] + l2 * uvs[1, 1] + l3 * uvs[2, 1]
        px = np.clip((u * tw).astype(np.int64), 0, tw - 1)
        py = np.clip(((1.0 - v) * th).astype(np.int64), 0, th - 1)
        sample = tex[py, px]
        region = out[lo_y:hi_y, lo_x:hi_x]
        mask = inside & (sample[..., 3] > 0)
        region[mask] = sample[mask]

    image = Image.fromarray(out, 'RGBA')
    bounds = {'x': float(min_x), 'y': float(max_y), 'w': width, 'h': height, 'ppu': ppu}
    return image, bounds


class Bone:

    def __init__(self, path):
        env = UnityPy.load(path)
        for obj in env.objects:
            if obj.type.name != 'MonoBehaviour':
                continue
            tree = obj.read_typetree()
            if 'exposedNodeNames' not in tree:
                continue
            self.node_names = tree['exposedNodeNames']
            self.frame_rate = tree['defaultFrameRate']
            self.animations = {a['name']: bytes(bytearray(a['dataBytes']))
                               for a in tree['animations']}
            return
        raise ValueError('%s is not a bone' % path)

    def _bounds(self, animation, index):
        raw = self.animations[animation]
        _, _, _, frames = struct.unpack_from('<4H', raw, 0)
        offsets = list(struct.unpack_from('<%dI' % frames, raw, 8))
        index = min(index, frames - 1)
        return raw, offsets[index], (offsets[index + 1] if index + 1 < frames else len(raw))

    def _walk(self, raw, start, end):
        """Read the block record by record. None if it does not add up."""
        out, pos = [], start
        while pos + HEADER <= end:
            order, flag, _symbol, node = struct.unpack_from('<4H', raw, pos)
            if flag & ~(FLAG_SYMBOL | FLAG_COLOUR) != FLAG_BASE:
                return None
            if node >= len(self.node_names):
                return None
            head = HEADER + (4 if flag & FLAG_COLOUR else 0)
            if pos + head + 24 > end:
                return None
            matrix = struct.unpack_from('<6f', raw, pos + head)
            out.append({'order': order, 'node': self.node_names[node],
                        'm': [round(x, 4) for x in matrix]})
            pos += head + 24
        return out if pos == end else None

    def _scan(self, raw, start, end):
        """Fallback for a block the walk cannot read: hunt for what fits."""
        out, pos = [], start
        while pos + RECORD <= end:
            order, flag, _symbol, node = struct.unpack_from('<4H', raw, pos)
            if flag in (48, 49) and node < len(self.node_names) and order < 200:
                matrix = struct.unpack_from('<6f', raw, pos + 12)
                if all(abs(x) < 5000 for x in matrix):
                    out.append({'order': order, 'node': self.node_names[node],
                                'm': [round(x, 4) for x in matrix]})
                    pos += RECORD
                    continue
            pos += 2
        return out

    def key_frame(self, animation):
        """Frame 0 holds full records, each naming its node, in paint order.

        The `order` field is not the paint order: it swaps around every record
        without a symbol, which is what put hats under heads.
        """
        raw, start, end = self._bounds(animation, 0)
        return self._walk(raw, start, end) or self._scan(raw, start, end)

    def frame(self, animation, index=0):
        key = self.key_frame(animation)
        if index == 0:
            return key
        # Later frames are 28 byte deltas, keyed by the draw order of frame 0.
        node_of = {r['order']: r['node'] for r in key}
        raw, start, end = self._bounds(animation, index)
        moved, pos = {}, start + 4
        while pos + DELTA <= end:
            order, flag = struct.unpack_from('<2H', raw, pos)
            if flag == 16 and order in node_of:
                matrix = struct.unpack_from('<6f', raw, pos + 4)
                if all(abs(x) < 5000 for x in matrix):
                    moved[order] = [round(x, 4) for x in matrix]
                    pos += DELTA
                    continue
            pos += 2
        if not moved:
            return key
        return [{'order': r['order'], 'node': r['node'],
                 'm': moved.get(r['order'], r['m'])} for r in key]

    def frame_count(self, animation):
        return struct.unpack_from('<4H', self.animations[animation], 0)[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skins', nargs='+', required=True, help='skin bundles')
    parser.add_argument('--bone')
    parser.add_argument('--frames', type=int, default=1)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    os.makedirs(os.path.join(args.out, 'parts'), exist_ok=True)
    for path in args.skins:
        skin_id = re.search(r'(\d+)', os.path.basename(path)).group(1)
        target = os.path.join(args.out, 'parts', skin_id)
        os.makedirs(target, exist_ok=True)
        skin = Skin(path)
        manifest = {}
        for part in skin.parts:
            image, bounds = bake_part(skin, part)
            if image is None or not image.getbbox():
                continue
            image.save(os.path.join(target, '%s.png' % part))
            manifest[part] = bounds
        json.dump(manifest, open(os.path.join(target, 'parts.json'), 'w'), indent=0)
        print('skin %s: %d parts' % (skin_id, len(manifest)), flush=True)

    if args.bone:
        os.makedirs(os.path.join(args.out, 'poses'), exist_ok=True)
        bone = Bone(args.bone)
        bone_id = re.search(r'(\d+)', os.path.basename(args.bone)).group(1)
        poses = {'frameRate': bone.frame_rate, 'orientations': {}}
        for orientation in ORIENTATIONS:
            animation = 'AnimStatique_%s' % orientation
            if animation not in bone.animations:
                continue
            count = min(args.frames, bone.frame_count(animation))
            poses['orientations'][orientation] = [bone.frame(animation, i)
                                                  for i in range(count)]
        json.dump(poses, open(os.path.join(args.out, 'poses', '%s.json' % bone_id), 'w'))
        print('pose %s: %d orientations' % (bone_id, len(poses['orientations'])))


if __name__ == '__main__':
    main()
