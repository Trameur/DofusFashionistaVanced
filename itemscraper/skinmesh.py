# -*- coding: utf-8 -*-
"""Read a Dofus 3 SkinAsset bundle and rasterise its parts."""
import numpy as np
import UnityPy
from PIL import Image

UnityPy.config.FALLBACK_UNITY_VERSION = '2022.3.0f1'


class Skin:

    def __init__(self, path):
        env = UnityPy.load(path)
        self.textures = []
        tree = None
        for obj in env.objects:
            if obj.type.name == 'Texture2D':
                self.textures.append(obj.read().image.convert('RGBA'))
            elif obj.type.name == 'MonoBehaviour':
                t = obj.read_typetree()
                if t.get('vertices'):
                    tree = t
        if tree is None:
            raise ValueError('%s has no mesh' % path)
        self.parts = dict(zip(tree['m_keys'], tree['m_values']))
        self.triangles = tree['triangles']
        self.vertices = tree['vertices']

    def part_names(self):
        return list(self.parts)

    def geometry(self, name):
        """(positions, uvs, colors, faces) for one part, indices rebased at 0."""
        part = self.parts[name]
        pos, uv, col, faces = [], [], [], []
        for chunk in part['skinChunks']:
            start_v = chunk['startVertexIndex']
            base = len(pos)
            for v in self.vertices[start_v:start_v + chunk['vertexCount']]:
                pos.append((v['pos']['x'], v['pos']['y']))
                uv.append((v['uv']['x'], v['uv']['y']))
                col.append(v['multiplicativeColor'])
            idx = self.triangles[chunk['startIndexIndex']:
                                 chunk['startIndexIndex'] + chunk['indexCount']]
            for i in range(0, len(idx), 3):
                faces.append((base + idx[i], base + idx[i + 1], base + idx[i + 2],
                              chunk['textureIndex']))
        return np.array(pos, dtype=np.float64), np.array(uv, dtype=np.float64), col, faces


def rasterise(skin, name, size=(360, 460), scale=4.0, offset=(0.0, 0.0), tint=None):
    """Draw one part into an RGBA image. y is flipped: game space is y up."""
    pos, uv, _col, faces = skin.geometry(name)
    if not len(pos):
        return None
    width, height = size
    out = np.zeros((height, width, 4), dtype=np.float64)

    screen = np.empty_like(pos)
    screen[:, 0] = pos[:, 0] * scale + width / 2.0 + offset[0]
    screen[:, 1] = -pos[:, 1] * scale + height / 2.0 + offset[1]

    for a, b, c, tex_index in faces:
        tri = screen[[a, b, c]]
        uvs = uv[[a, b, c]]
        texture = skin.textures[tex_index] if tex_index < len(skin.textures) else skin.textures[0]
        tex = np.asarray(texture, dtype=np.float64)
        th, tw = tex.shape[0], tex.shape[1]

        min_x = max(int(np.floor(tri[:, 0].min())), 0)
        max_x = min(int(np.ceil(tri[:, 0].max())) + 1, width)
        min_y = max(int(np.floor(tri[:, 1].min())), 0)
        max_y = min(int(np.ceil(tri[:, 1].max())) + 1, height)
        if min_x >= max_x or min_y >= max_y:
            continue

        xs = np.arange(min_x, max_x) + 0.5
        ys = np.arange(min_y, max_y) + 0.5
        gx, gy = np.meshgrid(xs, ys)

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

        region = out[min_y:max_y, min_x:max_x]
        alpha = sample[..., 3:4] / 255.0
        mask = inside[..., None] & (alpha > 0)
        region[...] = np.where(mask, sample, region)

    img = Image.fromarray(out.astype(np.uint8), 'RGBA')
    if tint:
        img = apply_tint(img, tint)
    return img


def apply_tint(img, rgb):
    arr = np.asarray(img, dtype=np.float64)
    factor = np.array(rgb, dtype=np.float64) / 128.0
    arr[..., :3] = np.clip(arr[..., :3] * factor, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')
