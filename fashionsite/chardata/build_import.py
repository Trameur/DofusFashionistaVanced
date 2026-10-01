"""Impose a set on a character from a list of Ankama item ids."""

from fashionistapulp.dofus_constants import (TYPE_NAME_TO_SLOT,
                                             TYPE_NAME_TO_SLOT_NUMBER, slots_for)
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.structure import fits_the_class, fits_the_wearer, level_to_wear

from chardata.lock_forbid import set_inclusions_dict_and_check_exclusions


# Why an id was rejected
UNKNOWN_ITEM = 'unknown_item'
UNKNOWN_TYPE = 'unknown_type'
NO_FREE_SLOT = 'no_free_slot'
ALREADY_PLACED = 'already_placed'
ABOVE_CHAR_LEVEL = 'above_char_level'
PAST_MAX_LEVEL = 'past_max_level'
UNUSABLE = 'unusable'
WRONG_CLASS = 'wrong_class'
WRONG_SEX = 'wrong_sex'
WRONG_NAME = 'wrong_name'
NOT_WORN_TOGETHER = 'not_worn_together'


def slots_for_type_name(type_name):
    """Every slot an item of this type could occupy ('ring1', 'ring2'), in fill order."""
    base = TYPE_NAME_TO_SLOT.get(type_name)
    if base is None:
        return []
    count = TYPE_NAME_TO_SLOT_NUMBER.get(type_name, 1)
    if count <= 1:
        return [base]
    return ['%s%d' % (base, i) for i in range(1, count + 1)]


def _can_be_worn_twice(structure, item, type_name, game_version):
    """Same rule as model.py: only a ring with no set, where rings_can_double."""
    if type_name != 'Ring' or getattr(item, 'set', None) is not None:
        return False
    try:
        return bool(get_game_version(game_version).rings_can_double)
    except Exception:
        return False


def plan_ankama_ids(structure, ankama_ids, game_version='dofus3',
                    char_level=None, char_class=None, gender=None, char_name=None):
    """Place each id without writing: returns ([(slot, item)], [(ankama_id, reason)])."""
    placed = []
    rejected = []
    pris = set()
    poses = {}

    for brut in ankama_ids:
        try:
            ankama_id = int(brut)
        except (TypeError, ValueError, OverflowError):
            # OverflowError is int(float('inf'))
            rejected.append((brut, UNKNOWN_ITEM))
            continue

        item = structure.get_item_by_ankama_id(ankama_id)
        if item is None:
            rejected.append((ankama_id, UNKNOWN_ITEM))
            continue

        type_name = structure.get_type_name_by_id(item.type)
        candidats = [slot for slot in slots_for_type_name(type_name)
                     if slot in slots_for(game_version)]
        if not candidats:
            rejected.append((ankama_id, UNKNOWN_TYPE))
            continue

        if char_level is not None and level_to_wear(item) > char_level:
            rejected.append((ankama_id, ABOVE_CHAR_LEVEL))
            continue

        highest = getattr(item, 'max_level', None)
        if char_level is not None and highest is not None and char_level > highest:
            rejected.append((ankama_id, PAST_MAX_LEVEL))
            continue

        if getattr(item, 'unusable', False):
            rejected.append((ankama_id, UNUSABLE))
            continue

        if char_class is not None and not fits_the_class(item, char_class):
            rejected.append((ankama_id, WRONG_CLASS))
            continue

        if not fits_the_wearer(item, gender=gender):
            rejected.append((ankama_id, WRONG_SEX))
            continue

        if not fits_the_wearer(item, char_name=char_name):
            rejected.append((ankama_id, WRONG_NAME))
            continue

        clash = set(getattr(item, 'not_worn_with', ()))
        if any(other.id in clash for _slot, other in placed):
            rejected.append((ankama_id, NOT_WORN_TOGETHER))
            continue

        if poses.get(ankama_id):
            if not _can_be_worn_twice(structure, item, type_name, game_version):
                rejected.append((ankama_id, ALREADY_PLACED))
                continue
            if poses[ankama_id] >= 2:
                rejected.append((ankama_id, ALREADY_PLACED))
                continue

        libre = next((s for s in candidats if s not in pris), None)
        if libre is None:
            # A third ring or a seventh dofus
            rejected.append((ankama_id, NO_FREE_SLOT))
            continue

        pris.add(libre)
        poses[ankama_id] = poses.get(ankama_id, 0) + 1
        placed.append((libre, item))

    return placed, rejected


def apply_ankama_ids(char, structure, ankama_ids):
    """Returns {'placed': [(slot, item_id, name)], 'rejected': [(id, reason)]}."""
    game_version = getattr(char, 'game_version', 'dofus3')
    placed, rejected = plan_ankama_ids(
        structure, ankama_ids,
        game_version=game_version,
        char_level=getattr(char, 'level', None),
        char_class=getattr(char, 'char_class', None),
        gender=getattr(char, 'gender', None) or 0,
        char_name=getattr(char, 'char_name', None) or '')

    inclusions = {slot: '' for slot in slots_for(game_version)}
    inclusions.update({slot: item.id for slot, item in placed})
    set_inclusions_dict_and_check_exclusions(char, inclusions)

    return {
        'placed': [(slot, item.id, item.name) for slot, item in placed],
        'rejected': rejected,
    }
