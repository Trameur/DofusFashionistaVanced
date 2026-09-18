"""Impose a set on a character from a list of Ankama item ids."""

from fashionistapulp.dofus_constants import (SLOTS, TYPE_NAME_TO_SLOT,
                                             TYPE_NAME_TO_SLOT_NUMBER)
from fashionistapulp.game_versions import get_game_version

from chardata.lock_forbid import set_inclusions_dict_and_check_exclusions


# Why an id was rejected
UNKNOWN_ITEM = 'unknown_item'
UNKNOWN_TYPE = 'unknown_type'
NO_FREE_SLOT = 'no_free_slot'
ALREADY_PLACED = 'already_placed'
ABOVE_CHAR_LEVEL = 'above_char_level'


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
                    char_level=None):
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
        candidats = slots_for_type_name(type_name)
        if not candidats:
            rejected.append((ankama_id, UNKNOWN_TYPE))
            continue

        if char_level is not None and getattr(item, 'level', 0) > char_level:
            rejected.append((ankama_id, ABOVE_CHAR_LEVEL))
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
    placed, rejected = plan_ankama_ids(
        structure, ankama_ids,
        game_version=getattr(char, 'game_version', 'dofus3'),
        char_level=getattr(char, 'level', None))

    inclusions = {slot: '' for slot in SLOTS}
    inclusions.update({slot: item.id for slot, item in placed})
    set_inclusions_dict_and_check_exclusions(char, inclusions)

    return {
        'placed': [(slot, item.id, item.name) for slot, item in placed],
        'rejected': rejected,
    }
