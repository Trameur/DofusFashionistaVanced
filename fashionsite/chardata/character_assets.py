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

# The standing idle. Its name carries the breed number, so it is matched rather
# than spelled out. The same skeletons also carry AnimStatiqueExploRetro (the
# older stance) and AnimStatiqueCombat (fists up, and only two orientations).
# The rider skeleton, and the mounts, name it plainly instead, so both spellings
# are tried in order.
ANIMATIONS = (re.compile(r'^AnimStatiqueExploNewAge\d*_(\d)$'),
              re.compile(r'^AnimStatique_(\d)$'))

# Flag bitfield. Bit 4 marks a record, bit 5 says its node index is real, bit 0
# that a symbol id follows, bit 2 that four bytes of colour sit before the
# matrix. So a record is 36 or 40 bytes, and the ones without bit 5 are nested
# symbols with nothing of ours to draw.
FLAG_RECORD = 0x10
FLAG_NODE = 0x20
FLAG_SYMBOL = 0x01
FLAG_COLOUR = 0x04
FLAG_BITS = 0x3F
HEADER = 12

# A mount piece says which of its look colours it wears in its node name.
COLOUR_SLOT = re.compile(r'^ColorGray_(\d+)_')

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


class _Geometry(object):
    """One mesh of a bundle, in the shape bake_part reads."""

    def __init__(self, tree, textures):
        self.parts = {}
        self.triangles = tree['triangles']
        self.vertices = tree['vertices']
        self.textures = textures

    geometry = Skin.geometry


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

    def _offsets(self, animation):
        """The block offsets. The header counts the TABLE first, the frames
        last, and the two differ: reading `frames` entries walks past the
        table into the first block."""
        raw = self.animations[animation]
        table, _records, _unused, frames = struct.unpack_from('<4H', raw, 0)
        table = min(table, max(0, (len(raw) - 8) // 4))
        offsets = list(struct.unpack_from('<%dI' % table, raw, 8)) if table else []
        offsets = [o for o in offsets if o <= len(raw)]
        return raw, offsets, min(frames, len(offsets))

    def _bounds(self, animation, index):
        raw, offsets, usable = self._offsets(animation)
        if not usable:
            return raw, len(raw), len(raw)
        index = min(index, usable - 1)
        end = offsets[index + 1] if index + 1 < usable else len(raw)
        return raw, offsets[index], end

    def _walk(self, raw, start, end):
        """Read the block record by record. None if it does not add up."""
        out, pos = [], start
        while pos + HEADER <= end:
            order, flag, _symbol, node = struct.unpack_from('<4H', raw, pos)
            if not flag & FLAG_RECORD or flag & ~FLAG_BITS:
                return None
            head = HEADER + (4 if flag & FLAG_COLOUR else 0)
            if pos + head + 24 > end:
                return None
            if flag & FLAG_NODE and node < len(self.node_names):
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
        # Painted in the order they are stored. The `order` field is not that
        # order: it swaps around every record without a symbol.
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
        return self._offsets(animation)[2]


class Mount(Bone):
    """A mount keeps its own art in its bone bundle.

    The character pairs a skin to a skeleton by node name. A mount does not:
    its records carry no node, and the symbol is the index into the bundle's
    `graphics` table, which also names the mesh the geometry indexes into.
    """

    def __init__(self, path):
        env = _unity().load(path)
        textures, meshes, tree = [], {}, None
        for obj in env.objects:
            if obj.type.name == 'Texture2D':
                textures.append(obj.read().image.convert('RGBA'))
            elif obj.type.name == 'MonoBehaviour':
                candidate = obj.read_typetree()
                if 'exposedNodeNames' in candidate:
                    tree = candidate
                elif candidate.get('vertices'):
                    meshes[obj.path_id] = candidate
        if tree is None:
            raise ValueError('%s is not a bone' % path)
        self.node_names = tree['exposedNodeNames']
        self.frame_rate = tree['defaultFrameRate']
        self.animations = {a['name']: bytes(bytearray(a['dataBytes']))
                           for a in tree['animations']}
        self.graphics = tree.get('graphics') or []
        self._holders = {path_id: _Geometry(mesh, textures)
                         for path_id, mesh in meshes.items()}

    def part(self, index):
        """The geometry holder and part name behind a graphics index, or None."""
        if index is None or not 0 <= index < len(self.graphics):
            return None
        entry = self.graphics[index]
        holder = self._holders.get(entry['asset']['m_PathID'])
        if holder is None:
            return None
        part = entry['part']
        holder.parts[part['name']] = part
        return holder, part['name']

    def key_frame(self, animation):
        """The mount's own pieces, in paint order.

        Only a record with the symbol bit carries art; the symbol is the
        graphics index. A record with a node and no symbol names the pieces that
        follow it, which is how a piece learns which look colour it wears, and
        one name can cover several pieces. A `carried` node is where the rider
        goes and carries nothing itself.
        """
        raw, start, end = self._bounds(animation, 0)
        out, pos, named = [], start, ''
        while pos + HEADER <= end:
            _order, flag, symbol, node = struct.unpack_from('<4H', raw, pos)
            if not flag & FLAG_RECORD or flag & ~FLAG_BITS:
                return out
            head = HEADER + (4 if flag & FLAG_COLOUR else 0)
            if pos + head + 24 > end:
                return out
            name = (self.node_names[node]
                    if flag & FLAG_NODE and node < len(self.node_names) else '')
            matrix = [round(x, 4) for x in struct.unpack_from('<6f', raw, pos + head)]
            if name.startswith('carried_'):
                out.append({'rider': name, 'm': matrix})
            elif not flag & FLAG_SYMBOL:
                named = name
            elif 0 <= symbol < len(self.graphics):
                row = {'part': symbol, 'm': matrix}
                tint = COLOUR_SLOT.match(name or named)
                if tint:
                    row['slot'] = int(tint.group(1))
                out.append(row)
            pos += head + 24
        return out


def _mount_cache(bone_id):
    return os.path.join(cache_dir(), 'mounts', str(bone_id))


def has_bone(bone_id):
    """Whether a skeleton can be drawn, without paying to bake it.

    Already baked counts. A server carrying the cache and no bundles is the
    normal setup: the bundles are 861 MB and are only ever needed to bake.
    """
    bone_id = str(bone_id)
    if os.path.exists(os.path.join(cache_dir(), 'poses',
                                   '%s-v%d.json' % (bone_id, POSE_FORMAT))):
        return True
    if os.path.exists(os.path.join(_mount_cache(bone_id),
                                   'mount-v%d.json' % MOUNT_FORMAT)):
        return True
    source = bundle_dir()
    return bool(source) and os.path.exists(
        os.path.join(source, 'bones_assets_bone_%s.bundle' % bone_id))


def ensure_mount(bone_id):
    """Bake a mount's pieces and its standing pose. None if there is no bundle."""
    bone_id = str(bone_id)
    if not bone_id.isdigit():
        return None
    target = _mount_cache(bone_id)
    manifest_path = os.path.join(target, 'mount-v%d.json' % MOUNT_FORMAT)
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding='utf-8') as fh:
            return json.load(fh)
    source = bundle_dir()
    if not source:
        return None
    bundle = os.path.join(source, 'bones_assets_bone_%s.bundle' % bone_id)
    if not os.path.exists(bundle):
        return None
    with _lock:
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding='utf-8') as fh:
                return json.load(fh)
        os.makedirs(target, exist_ok=True)
        mount = Mount(bundle)
        manifest = {'parts': {}, 'orientations': {}}
        for orientation in ORIENTATIONS:
            animation = 'AnimStatique_%s' % orientation
            if animation not in mount.animations:
                continue
            frame = mount.key_frame(animation)
            manifest['orientations'][orientation] = frame
            for row in frame:
                index = row.get('part')
                if index is None or str(index) in manifest['parts']:
                    continue
                resolved = mount.part(index)
                if resolved is None:
                    continue
                holder, name = resolved
                image, bounds = bake_part(holder, name)
                if image is None or not image.getbbox():
                    continue
                image.save(os.path.join(target, '%d.png' % index))
                manifest['parts'][str(index)] = bounds
        manifest['orientations'] = {
            orientation: [row for row in frame
                          if 'rider' in row or str(row['part']) in manifest['parts']]
            for orientation, frame in manifest['orientations'].items()}
        with open(manifest_path, 'w', encoding='utf-8') as fh:
            json.dump(manifest, fh)
        return manifest


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


# In the cache file name. Nothing ever expires it, so a decoder change needs a
# new name.
POSE_FORMAT = 4
MOUNT_FORMAT = 5

BONE_NAME = re.compile(r'^[\w-]+$')


def ensure_pose(bone_id):
    bone_id = str(bone_id)
    if not BONE_NAME.match(bone_id):
        return None
    target = os.path.join(cache_dir(), 'poses')
    path = os.path.join(target, '%s-v%d.json' % (bone_id, POSE_FORMAT))
    if os.path.exists(path):
        return path
    source = bundle_dir()
    if not source:
        return None
    bundle = os.path.join(source, 'bones_assets_bone_%s.bundle' % bone_id)
    if not os.path.exists(bundle):
        return None
    with _lock:
        if os.path.exists(path):
            return path
        os.makedirs(target, exist_ok=True)
        bone = Bone(bundle)
        poses = {'frameRate': bone.frame_rate, 'orientations': {}}
        for pattern in ANIMATIONS:
            for animation in sorted(bone.animations):
                match = pattern.match(animation)
                if not match or match.group(1) not in ORIENTATIONS:
                    continue
                poses['orientations'][match.group(1)] = [
                    bone.frame(animation, i)
                    for i in range(bone.frame_count(animation))]
            if poses['orientations']:
                break
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


def mount_manifest_view(request, bone_id):
    manifest = ensure_mount(bone_id)
    if manifest is None:
        raise Http404
    return _forever(JsonResponse(manifest))


def mount_part_view(request, bone_id, part):
    manifest = ensure_mount(bone_id)
    if manifest is None or part not in manifest['parts']:
        raise Http404
    path = os.path.join(_mount_cache(bone_id), '%s.png' % part)
    if not os.path.exists(path):
        raise Http404
    return _forever(FileResponse(open(path, 'rb'), content_type='image/png'))


def pose_view(request, bone_id):
    path = ensure_pose(bone_id)
    if path is None:
        raise Http404
    return _forever(FileResponse(open(path, 'rb'), content_type='application/json'))
