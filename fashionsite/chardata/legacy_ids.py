# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Read-time repair of Dofus 3 item ids saved before the switch to Ankama ids."""

import json
import os

# Old sequential id -> ankama id, per version
_CHEMIN = os.path.join(os.path.dirname(__file__), 'legacy_item_ids.json')
_TABLES = None

# Mount id space, same as modelresult
_MOUNT_ID_OFFSET = 1000000

# Mounts our data source renumbered, matched on exact English name and type
_CHEMIN_RENUMEROTES = os.path.join(os.path.dirname(__file__),
                                   'legacy_renumbered_items.json')
_RENUMEROTES = None


def _tables():
    global _TABLES
    if _TABLES is None:
        with open(_CHEMIN, encoding='utf-8') as fichier:
            _TABLES = json.load(fichier)
    return _TABLES


def _renumerotes():
    global _RENUMEROTES
    if _RENUMEROTES is None:
        with open(_CHEMIN_RENUMEROTES, encoding='utf-8') as fichier:
            _RENUMEROTES = json.load(fichier)
    return _RENUMEROTES


def renumbered_item_id(game_version, item_id):
    """Current id of a renumbered mount, or None."""
    table = _renumerotes().get(game_version or '')
    if not table or not isinstance(item_id, int):
        return None
    # Saved as bare ankama id or in the mount id space, depending on when
    for candidat in (item_id, item_id - _MOUNT_ID_OFFSET):
        trouve = table.get(str(candidat))
        if trouve is not None:
            return trouve
    return None


def ankama_id_of_legacy(game_version, item_id):
    """Ankama id this old number stood for, or None."""
    table = _tables().get(game_version or '')
    if not table:
        return None
    return table.get(str(item_id))


def _fits(structure, slot, item):
    from chardata.shared_builds_view import _get_valid_slots_for_type
    if item is None:
        return False
    return slot in _get_valid_slots_for_type(
        structure.get_type_name_by_id(item.type))


def repaired_slots(structure, game_version, item_per_slot):
    """{slot: item id} with misfit slots repaired, or None when nothing changes."""
    from fashionistapulp.modelresult import get_item_in_slot
    if not item_per_slot:
        return None
    corrige = {}
    change = False
    for slot, item_id in item_per_slot.items():
        corrige[slot] = item_id
        if item_id is None:
            continue
        if _fits(structure, slot, get_item_in_slot(structure, item_id, slot)):
            continue
        autre = None
        ankama = ankama_id_of_legacy(game_version, item_id)
        if ankama is not None:
            autre = structure.items_dict_ankama.get(ankama)
        if not _fits(structure, slot, autre):
            # Then a renumbered mount
            neuf = renumbered_item_id(game_version, item_id)
            autre = structure.get_item_by_id(neuf) if neuf is not None else None
        if not _fits(structure, slot, autre):
            continue
        corrige[slot] = autre.id
        change = True
    return corrige if change else None


def _reslot_mismatched(structure, par_slot):
    """Move misfit items to a free slot of their type, never over another item."""
    from chardata.shared_builds_view import _get_valid_slots_for_type
    from fashionistapulp.modelresult import get_item_in_slot
    occupes = {slot for slot, iid in par_slot.items() if iid is not None}
    change = False
    for slot in sorted(par_slot, key=str):
        item_id = par_slot.get(slot)
        if item_id is None:
            continue
        item = get_item_in_slot(structure, item_id, slot)
        if item is None:
            continue
        places = _get_valid_slots_for_type(
            structure.get_type_name_by_id(item.type))
        if not places or slot in places:
            continue
        libres = sorted(places - occupes)
        if not libres:
            continue
        cible = libres[0]
        par_slot[cible] = item_id
        par_slot[slot] = None
        occupes.discard(slot)
        occupes.add(cible)
        change = True
    return change


def repair_minimal_solution(char, minimal_solution):
    """Repair a stored solution, in memory only."""
    par_slot = getattr(minimal_solution, 'item_per_slot', None)
    if not par_slot:
        return False
    from fashionistapulp.structure import get_structure
    game_version = getattr(char, 'game_version', None) or 'dofus3'
    try:
        structure = get_structure(game_version)
    except Exception:
        return False
    corrige = repaired_slots(structure, game_version, par_slot)
    change = corrige is not None
    corrige = dict(corrige if change else par_slot)
    # Then items still in a slot of another type
    if _reslot_mismatched(structure, corrige):
        change = True
    if not change:
        return False
    minimal_solution.item_per_slot = corrige
    return True
