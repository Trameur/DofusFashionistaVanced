# -*- coding: utf-8 -*-
"""What the character preview needs to draw: the body, the head, and the skin
of every piece that actually shows on the character."""
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

# The look string says bones 1 for every class; the bundle that holds the
# player skeleton is 2.
PLAYER_BONES = 2

# Slot -> the node family the skeleton exposes for it.
SLOT_TO_NODE = {
    'hat': 'Chapeau',
    'cloak': 'Cape',
    'shield': 'Bouclier',
    'weapon': 'Arme',
}

REFERENCE_SCALE = 53.0

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
    """None when the version has no character art or the class is unknown."""
    breed = CLASS_TO_BREED.get(char.char_class)
    if breed is None:
        return None
    gender = getattr(char, 'gender', 0) or 0
    entry = _breed_looks().get('%d-%d' % (breed, gender))
    if entry is None:
        return None

    look = {'bones': PLAYER_BONES, 'body': entry['body'], 'head': entry['head'],
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
