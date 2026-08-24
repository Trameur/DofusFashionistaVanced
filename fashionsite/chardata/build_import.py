"""Impose a set on a character from a list of Ankama item ids.

Where the ids come from is deliberately not this module's business. A player
pasting a link, a file, a list typed by hand: each of those is a reader for
somebody else to write, and every one of them ends here. Keeping the core free
of any one source is what lets the question "which site do we import from"
stay open without the answer costing a rewrite.

The ids are Ankama's own, the ones the game itself uses, and the item table
carries them on all 3826 items. So the join is on an integer, never on a
displayed name: names are translated, duplicated across versions and edited
between patches, and matching on them is how an importer quietly puts the
wrong ring on someone.

An import REPLACES the set, it does not add to it. Merging was the first
version of this module and it was wrong twice over: the hat of the previous
build stayed locked under the new one, and a single ring landed in a hand that
still held its own copy, which the solver in retro answers with Infeasible.

Nothing is ever dropped in silence. Every id that does not end up on the
character comes back in the report with the reason, because an import that
says "done" while having thrown away three items is worse than one that fails.
"""

from fashionistapulp.dofus_constants import (SLOTS, TYPE_NAME_TO_SLOT,
                                             TYPE_NAME_TO_SLOT_NUMBER)
from fashionistapulp.game_versions import get_game_version

from chardata.lock_forbid import set_inclusions_dict_and_check_exclusions


# Why an id did not make it onto the character. They are returned, never logged
# and forgotten, so a caller can tell the reader exactly what was left behind.
UNKNOWN_ITEM = 'unknown_item'
UNKNOWN_TYPE = 'unknown_type'
NO_FREE_SLOT = 'no_free_slot'
ALREADY_PLACED = 'already_placed'
ABOVE_CHAR_LEVEL = 'above_char_level'


def slots_for_type_name(type_name):
    """Every slot an item of this type could occupy, in the order they fill.

    A ring has two, a dofus six, everything else one. The numbering is the
    site's own ('ring1', 'ring2'), so what this returns can be handed straight
    to the inclusion dictionary.
    """
    base = TYPE_NAME_TO_SLOT.get(type_name)
    if base is None:
        return []
    count = TYPE_NAME_TO_SLOT_NUMBER.get(type_name, 1)
    if count <= 1:
        return [base]
    return ['%s%d' % (base, i) for i in range(1, count + 1)]


def _can_be_worn_twice(structure, item, type_name, game_version):
    """Whether a second copy of this very item is a set the game allows.

    The rule is the solver's own, not one invented here: model.py grants a
    second copy to a ring that belongs to no set, and only in the versions
    whose registry entry says rings can double. Retro says no, and answers a
    doubled ring with Infeasible rather than with a worse set.
    """
    if type_name != 'Ring' or getattr(item, 'set', None) is not None:
        return False
    try:
        return bool(get_game_version(game_version).rings_can_double)
    except Exception:
        # An unknown version is not a licence to double.
        return False


def plan_ankama_ids(structure, ankama_ids, game_version='dofus3',
                    char_level=None):
    """Work out where each id would go, without touching any character.

    Separated from applying it so the same decision can be shown to a reader
    before anything is written, and so it can be tested without a database.

    `game_version` decides whether a repeated ring is legal. `char_level`, when
    given, refuses items the character could not wear: the solver would answer
    Infeasible and the reader would never learn which item caused it.

    Returns (placed, rejected): placed is a list of (slot, item), rejected a
    list of (ankama_id, reason).
    """
    placed = []
    rejected = []
    pris = set()
    poses = {}

    for brut in ankama_ids:
        try:
            ankama_id = int(brut)
        except (TypeError, ValueError, OverflowError):
            # OverflowError is float('inf'). It belongs here and not in a
            # traceback: the promise of this module is that everything handed
            # in comes back one way or the other.
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
            # A third ring or a seventh dofus. The set is simply not one the
            # game allows, and saying so beats keeping an arbitrary six.
            rejected.append((ankama_id, NO_FREE_SLOT))
            continue

        pris.add(libre)
        poses[ankama_id] = poses.get(ankama_id, 0) + 1
        placed.append((libre, item))

    return placed, rejected


def apply_ankama_ids(char, structure, ankama_ids):
    """Replace the character's imposed set with the one the ids name.

    Every slot the import does not fill is emptied, so nothing of the previous
    build survives underneath. The version and the level are read off the
    character rather than asked of the caller, since getting either wrong is
    silent.

    Returns {'placed': [(slot, item_id, name)], 'rejected': [(id, reason)]}.
    """
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
