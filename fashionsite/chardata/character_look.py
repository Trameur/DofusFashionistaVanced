# -*- coding: utf-8 -*-
"""Body, head and gear skins the preview needs to draw a build."""
import json
import os

from django.conf import settings

from fashionistapulp.structure import get_structure

# Ankama breed ids. 19 is unused, Forgelance is 20.
CLASS_TO_BREED = {
    'Feca': 1, 'Osamodas': 2, 'Enutrof': 3, 'Sram': 4, 'Xelor': 5,
    'Ecaflip': 6, 'Eniripsa': 7, 'Iop': 8, 'Cra': 9, 'Sadida': 10,
    'Sacrier': 11, 'Pandawa': 12, 'Rogue': 13, 'Masqueraider': 14,
    'Foggernaut': 15, 'Eliotrope': 16, 'Huppermage': 17, 'Ouginak': 18,
    'Forgelance': 20,
}

# The look string says 1, and the player skeletons are the named bundles
# bone_1-<breed>-static. The numbered bones (2 and up) are monsters and mounts:
# bone_2 draws the character sitting astride, which is how it looks when the
# mount it belongs to is not there.
BONES_FOR_BREED = '1-%d-static'


def player_bones(breed):
    return BONES_FOR_BREED % breed

# Slot -> skeleton node.
SLOT_TO_NODE = {
    'hat': 'Chapeau',
    'cloak': 'Cape',
    'shield': 'Bouclier',
    'weapon': 'Arme',
}

REFERENCE_SCALE = 53.0

# Dofus 3 art. Beta shares the client; the others have their own.
VERSIONS_WITH_ART = ('dofus3', 'beta')

_looks = None


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

    look = {'bones': player_bones(breed), 'body': entry['body'],
            'head': entry['head'],
            'scale': round(int(entry['scale']) / REFERENCE_SCALE, 3), 'gear': {}}
    model_result = getattr(solution, 'model_result', solution)
    items = getattr(model_result, 'item_list', None)
    if not items:
        return look

    structure = get_structure(game_version)
    for result_item in items:
        node = SLOT_TO_NODE.get(result_item.slot)
        if node is None or not getattr(result_item, 'item_added', False):
            continue
        item = structure.get_item_by_id(result_item.id)
        skin = getattr(item, 'skin', None) if item else None
        if skin:
            look['gear'][node] = skin
    return look
