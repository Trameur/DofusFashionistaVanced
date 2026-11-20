# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Dracorune a player cannot take off a locked piece: options key {slot: variant key}, kept only while the slot stays locked on that piece."""

import logging
import pickle

from chardata.char_blobs import read_char_blob
from fashionistapulp import dracorune_terms
from fashionistapulp.model import readable_runes
from fashionistapulp.structure import get_structure

KEY = 'dracorune_locks'

logger = logging.getLogger(__name__)


def stored_locks(char):
    """{slot: variant key} the build holds, empty when none."""
    if not char.options:
        return {}
    locks = read_char_blob(char.options, {}, 'options', char).get(KEY)
    return dict(locks) if isinstance(locks, dict) else {}


def valid_locks(locks, inclusions, version):
    """The entries whose slot is locked on a piece that still takes that rune, {slot: variant key}."""
    runes = readable_runes(version) if locks and isinstance(locks, dict) else None
    if not runes or not isinstance(inclusions, dict):
        return {}
    structure = get_structure(version)
    found = {}
    for slot, key in sorted(locks.items(), key=repr):
        item = structure.get_item_by_id(inclusions.get(slot)) if inclusions.get(slot) else None
        if item is None or not isinstance(key, str):
            continue
        try:
            if not dracorune_terms.is_eligible(item, structure, runes):
                continue
            variants = dracorune_terms.item_variants(item, runes, structure)
        except (KeyError, TypeError, ValueError):
            logger.warning('The dracorune lock %r of slot %s cannot be read', key, slot)
            continue
        if any(variant.key == key for variant in variants):
            found[slot] = key
    return found


def _save(char, locks):
    options = read_char_blob(char.options, {}, 'options', char)
    if locks:
        options[KEY] = locks
    else:
        options.pop(KEY, None)
    char.options = pickle.dumps(options)
    char.save()


def drop_changed_locks(char, new_inclusions):
    """Forgets the rune of every slot whose lock is gone or holds another piece than the one saved now."""
    locks = stored_locks(char)
    if not locks:
        return
    from chardata.lock_forbid import get_inclusions_dict
    old_inclusions = get_inclusions_dict(char)
    kept = {slot: key for slot, key in locks.items()
            if new_inclusions.get(slot) and new_inclusions.get(slot) == old_inclusions.get(slot)}
    if kept != locks:
        _save(char, kept)


def record_lock(char, slot, item_id):
    """Locks the rune the saved solution puts on that slot's piece, nothing when it carries none."""
    if readable_runes(char.game_version) is None:
        return
    locks = stored_locks(char)
    wanted = _rune_in_solution(char, slot, item_id)
    if wanted is None:
        locks.pop(slot, None)
    else:
        locks[slot] = wanted
    from chardata.lock_forbid import get_inclusions_dict
    locks = valid_locks(locks, get_inclusions_dict(char), char.game_version)
    if locks != stored_locks(char):
        _save(char, locks)


def _rune_in_solution(char, slot, item_id):
    minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
    placed = (getattr(minimal, 'dracorunes', None) or {}).get(slot)
    if (not placed or getattr(minimal, 'item_per_slot', {}).get(slot) != item_id
            or placed[0] != item_id):
        return None
    return placed[1]


def forget_stale_locks(char, options):
    """options without the entries of slots no longer locked on a piece taking that rune."""
    from chardata.lock_forbid import get_inclusions_dict
    locks = options.get(KEY)
    if not locks:
        return options
    kept = valid_locks(locks, get_inclusions_dict(char), char.game_version)
    options = dict(options)
    if kept:
        options[KEY] = kept
    else:
        options.pop(KEY)
    return options


def locks_above_count(char, options):
    """True when the runes of locked pieces outnumber the runes the build allows."""
    locks = options.get(KEY)
    if not locks:
        return False
    from chardata.lock_forbid import get_inclusions_dict
    from fashionistapulp.model import dracorune_count
    return len(valid_locks(locks, get_inclusions_dict(char), char.game_version)) > dracorune_count(options)
