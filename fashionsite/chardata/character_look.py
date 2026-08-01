# -*- coding: utf-8 -*-
"""Body, head and gear skins the preview needs to draw a build."""
import json
import os

from django.conf import settings

from fashionistapulp.structure import get_structure

from chardata.character_assets import has_bone

# Ankama breed ids. 19 is unused, Forgelance is 20.
CLASS_TO_BREED = {
    'Feca': 1, 'Osamodas': 2, 'Enutrof': 3, 'Sram': 4, 'Xelor': 5,
    'Ecaflip': 6, 'Eniripsa': 7, 'Iop': 8, 'Cra': 9, 'Sadida': 10,
    'Sacrier': 11, 'Pandawa': 12, 'Rogue': 13, 'Masqueraider': 14,
    'Foggernaut': 15, 'Eliotrope': 16, 'Huppermage': 17, 'Ouginak': 18,
    'Forgelance': 20,
}

# The look string says 1, and the player skeletons are the named bundles
# bone_1-<breed>-static. The numbered bones (2 and up) are monsters and mounts.
BONES_FOR_BREED = '1-%d-static'

# Seated upper body, no legs. The slot's depth in the mount's paint list is
# what puts the near leg in front of the rider.
RIDER_BONES = '9582'
RIDER_SLOT = 'carried_2_0'


def player_bones(breed):
    return BONES_FOR_BREED % breed

# Slot -> skeleton node.
SLOT_TO_NODE = {
    'hat': 'Chapeau',
    'cloak': 'Cape',
    'shield': 'Bouclier',
    'weapon': 'Arme',
}

# A weapon has art and a node name in the skeleton, but not one of the 23
# baked poses places an Arme node, so nothing ever draws it. Measured, not
# assumed: hiding the weapon on a build that has one moves zero pixels.
UNDRAWN_SLOTS = ('weapon',)

MOUNT_SLOT = 'mount'

REFERENCE_SCALE = 53.0

# Dofus 3 art. Beta shares the client; the others have their own.
VERSIONS_WITH_ART = ('dofus3', 'beta')

# The ColorGray slots the art exposes. Six, not five: slot 6 was left out and
# every piece wearing it stayed grey.
COLOR_SLOTS = 6
# Only a fallback for a breed whose look carries none; the real ones come from
# the client, per breed and per gender.
DEFAULT_COLORS = ['c49a7a', '4a5c84', 'd6c4a0', '605046', '968c82', '968c82']


def breed_colors(breed, gender):
    entry = _breed_looks().get('%d-%d' % (breed, gender)) or {}
    colors = [c for c in (entry.get('colors') or []) if c]
    return colors if len(colors) == COLOR_SLOTS else list(DEFAULT_COLORS)


def parse_colors(raw, defaults=None):
    """The hex triplets a build stores, or the game's own colours."""
    parts = [p.strip().lstrip('#').lower() for p in (raw or '').split(',')]
    parts = [p for p in parts if len(p) == 6 and all(c in '0123456789abcdef' for c in p)]
    if len(parts) != COLOR_SLOTS:
        return list(defaults or DEFAULT_COLORS)
    return parts


def colors_as_rgb(raw, defaults=None):
    """Slot number -> [r, g, b], the shape the preview draws with."""
    return {index + 1: [int(value[i:i + 2], 16) for i in (0, 2, 4)]
            for index, value in enumerate(parse_colors(raw, defaults))}


def parse_hidden(raw):
    """The slots a build leaves off the preview, in a stable order."""
    wanted = {p.strip().lower() for p in (raw or '').split(',')}
    known = sorted(SLOT_TO_NODE) + [MOUNT_SLOT]
    return [slot for slot in known if slot in wanted]


# Spelled out rather than scaled from one base: the canvas has to stay exactly
# twice the css size and keep the 5:7 shape, and rounding a percentage breaks
# both. The percent is only the label the account page stores.
PREVIEW_BOXES = {
    75: {'canvas': (110, 154), 'css': (55, 77), 'scale': 0.455},
    100: {'canvas': (150, 210), 'css': (75, 105), 'scale': 0.62},
    150: {'canvas': (220, 308), 'css': (110, 154), 'scale': 0.909},
}
PREVIEW_SIZES = tuple(sorted(PREVIEW_BOXES))


def preview_box(percent):
    """Canvas, css size and draw scale for a preview size in percent."""
    if percent not in PREVIEW_BOXES:
        percent = 100
    box = PREVIEW_BOXES[percent]
    return {'percent': percent,
            'canvas_width': box['canvas'][0],
            'canvas_height': box['canvas'][1],
            'css_width': box['css'][0],
            'css_height': box['css'][1],
            'scale': box['scale']}


_looks = None
_mount_looks = {}


def mount_look(item_id, game_version='dofus3'):
    """Skeleton, colours and scale, or None: not every variant is listed."""
    looks = _mount_looks.get(game_version)
    if looks is None:
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        looks = {}
        conn = sqlite3.connect(get_items_db_path(game_version))
        try:
            for row in conn.execute(
                    'SELECT item, bone, colors, scale FROM mount_looks'):
                looks[row[0]] = {'bone': row[1],
                                 'colors': [c for c in row[2].split(',') if c],
                                 'scale': row[3],
                                 'slot': RIDER_SLOT}
        except sqlite3.OperationalError:
            looks = {}
        finally:
            conn.close()
        _mount_looks[game_version] = looks
    return looks.get(item_id)


def _breed_looks():
    global _looks
    if _looks is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'data', 'breed_looks.json')
        with open(path, encoding='utf-8') as fh:
            _looks = json.load(fh)
    return _looks


def get_character_look(char, solution, game_version='dofus3'):
    """None if the version has no art or the class is unknown."""
    if game_version not in VERSIONS_WITH_ART:
        return None
    breed = CLASS_TO_BREED.get(char.char_class)
    if breed is None:
        return None
    gender = getattr(char, 'gender', 0) or 0
    entry = _breed_looks().get('%d-%d' % (breed, gender))
    if entry is None:
        return None

    hidden = parse_hidden(getattr(char, 'hidden_parts', ''))
    look = {'bones': player_bones(breed), 'body': entry['body'],
            'head': entry['head'],
            'scale': round(int(entry['scale']) / REFERENCE_SCALE, 3),
            'colors': colors_as_rgb(getattr(char, 'colors', ''),
                                    breed_colors(breed, gender)),
            'hidden': hidden, 'gear': {}, 'mount': None}
    model_result = getattr(solution, 'model_result', solution)
    items = getattr(model_result, 'item_list', None)
    if not items:
        return look

    if MOUNT_SLOT not in hidden:
        for result_item in items:
            if result_item.slot != 'pet' or not getattr(result_item, 'item_added', False):
                continue
            mount = mount_look(result_item.id, game_version)
            # No legs on the rider, so only switch when the mount can be drawn.
            if mount and has_bone(mount['bone']) and has_bone(RIDER_BONES):
                look['mount'] = mount
                look['bones'] = RIDER_BONES
            break

    structure = get_structure(game_version)
    for result_item in items:
        node = SLOT_TO_NODE.get(result_item.slot)
        if node is None or result_item.slot in hidden:
            continue
        if not getattr(result_item, 'item_added', False):
            continue
        item = structure.get_item_by_id(result_item.id)
        skin = getattr(item, 'skin', None) if item else None
        if skin:
            look['gear'][node] = skin
    return look
