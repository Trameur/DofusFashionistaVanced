# -*- coding: utf-8 -*-
"""Serve character preview art, baking a skin the first time it is asked for.

Bundles live in CHARACTER_BUNDLE_DIR, baked PNGs in CHARACTER_CACHE_DIR.
"""
import json
import os
import re
import struct
import threading
import warnings

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse

RECORD = 36
DELTA = 28
ORIENTATIONS = ('0', '1', '2', '5', '6')
PIXELS_PER_UNIT = 4.0
PAD = 2

# A keyframe record is a flag word, then a matrix. The flag is a bitfield over
# 0x30: bit 0 says a symbol id follows, bit 2 adds a four byte colour before
# the matrix, which is why records are not all the same length.
FLAG_BASE = 0x30
FLAG_SYMBOL = 0x01
FLAG_COLOUR = 0x04
HEADER = 12

_lock = threading.Lock()
_unity_ready = False


def _unity():
    """Ankama blanks the Unity version in the header, so set it ourselves."""
    global _unity_ready
    import UnityPy
    if not _unity_ready:
        UnityPy.config.FALLBACK_UNITY_VERSION = '2022.3.0f1'
        try:
            from UnityPy.exceptions import UnityVersionFallbackWarning
            warnings.simplefilter('ignore', UnityVersionFallbackWarning)
        except ImportError:
            warnings.filterwarnings('ignore', message='No valid Unity version found')
        _unity_ready = True
    return UnityPy


def bundle_dir():
    return getattr(settings, 'CHARACTER_BUNDLE_DIR', None)


def cache_dir():
    return getattr(settings, 'CHARACTER_CACHE_DIR',
                   os.path.join(settings.BASE_DIR, 'character_cache'))


class Skin(object):

    def __init__(self, path):
        env = _unity().load(path)
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
        import numpy as np
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


def bake_part(skin, name):
    import numpy as np
    from PIL import Image
    pos, uv, faces = skin.geometry(name)
    if not len(pos):
        return None, None
    min_x, min_y = pos.min(axis=0)
    max_x, max_y = pos.max(axis=0)
    width = int(np.ceil((max_x - min_x) * PIXELS_PER_UNIT)) + PAD * 2
    height = int(np.ceil((max_y - min_y) * PIXELS_PER_UNIT)) + PAD * 2
    if width <= 0 or height <= 0:
        return None, None

    screen = np.empty_like(pos)
    screen[:, 0] = (pos[:, 0] - min_x) * PIXELS_PER_UNIT + PAD
    screen[:, 1] = (max_y - pos[:, 1]) * PIXELS_PER_UNIT + PAD
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

    bounds = {'x': float(min_x), 'y': float(max_y), 'w': width, 'h': height,
              'ppu': PIXELS_PER_UNIT}
    return Image.fromarray(out, 'RGBA'), bounds


class Bone(object):

    def __init__(self, path):
        env = _unity().load(path)
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
        # Records are painted in the order they are stored. The `order` field
        # is not that order: it swaps around every record without a symbol,
        # which is what put hats under heads.
        raw, start, end = self._bounds(animation, 0)
        return self._walk(raw, start, end) or self._scan(raw, start, end)

    def frame(self, animation, index=0):
        key = self.key_frame(animation)
        if index == 0:
            return key
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
        return [{'order': r['order'], 'node': r['node'], 'm': moved.get(r['order'], r['m'])}
                for r in key]

    def frame_count(self, animation):
        return struct.unpack_from('<4H', self.animations[animation], 0)[3]


def _skin_cache(skin_id):
    return os.path.join(cache_dir(), 'parts', str(skin_id))


def ensure_skin(skin_id):
    """Bake once, then read from the cache. None if the bundle is missing."""
    target = _skin_cache(skin_id)
    manifest_path = os.path.join(target, 'parts.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding='utf-8') as fh:
            return json.load(fh)
    source = bundle_dir()
    if not source:
        return None
    bundle = os.path.join(source, 'skin_%d.bundle' % skin_id)
    if not os.path.exists(bundle):
        return None
    with _lock:
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding='utf-8') as fh:
                return json.load(fh)
        os.makedirs(target, exist_ok=True)
        skin = Skin(bundle)
        manifest = {}
        for part in skin.parts:
            image, bounds = bake_part(skin, part)
            if image is None or not image.getbbox():
                continue
            image.save(os.path.join(target, '%s.png' % part))
            manifest[part] = bounds
        with open(manifest_path, 'w', encoding='utf-8') as fh:
            json.dump(manifest, fh)
        return manifest


# Bumped whenever the decoder changes, so a cached pose from an older read is
# not served for the life of the volume.
POSE_FORMAT = 3


def ensure_pose(bone_id):
    target = os.path.join(cache_dir(), 'poses')
    path = os.path.join(target, '%d-v%d.json' % (bone_id, POSE_FORMAT))
    if os.path.exists(path):
        return path
    source = bundle_dir()
    if not source:
        return None
    bundle = os.path.join(source, 'bones_assets_bone_%d.bundle' % bone_id)
    if not os.path.exists(bundle):
        return None
    with _lock:
        if os.path.exists(path):
            return path
        os.makedirs(target, exist_ok=True)
        bone = Bone(bundle)
        poses = {'frameRate': bone.frame_rate, 'orientations': {}}
        for orientation in ORIENTATIONS:
            animation = 'AnimStatique_%s' % orientation
            if animation not in bone.animations:
                continue
            poses['orientations'][orientation] = [
                bone.frame(animation, i) for i in range(bone.frame_count(animation))]
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(poses, fh)
        return path


# A part is named by its skin and its own name, and Ankama ships a new skin id
# rather than changing one, so what is here never changes. A body is 539 files;
# without this every page view fetches them again.
FOREVER = 'public, max-age=31536000, immutable'


def _forever(response):
    response['Cache-Control'] = FOREVER
    return response


def parts_manifest_view(request, skin_id):
    manifest = ensure_skin(int(skin_id))
    if manifest is None:
        raise Http404
    return _forever(JsonResponse(manifest))


def part_image_view(request, skin_id, part):
    if not re.match(r'^[\w.\-]+$', part):
        raise Http404
    manifest = ensure_skin(int(skin_id))
    if manifest is None or part not in manifest:
        raise Http404
    path = os.path.join(_skin_cache(int(skin_id)), '%s.png' % part)
    if not os.path.exists(path):
        raise Http404
    return _forever(FileResponse(open(path, 'rb'), content_type='image/png'))


def pose_view(request, bone_id):
    path = ensure_pose(int(bone_id))
    if path is None:
        raise Http404
    return _forever(FileResponse(open(path, 'rb'), content_type='application/json'))
