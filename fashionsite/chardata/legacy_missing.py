# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Names the pieces a build wears that the catalogue no longer has."""

import json
import os

# Mount id space, as in modelresult; a stored mount id is offset by it
_MOUNT_ID_OFFSET = 1000000

_CHEMIN = os.path.join(os.path.dirname(__file__), 'legacy_missing_items.json')
_TABLES = None


def _tables():
    global _TABLES
    if _TABLES is None:
        with open(_CHEMIN, encoding='utf-8') as fichier:
            _TABLES = json.load(fichier)
    return _TABLES


def name_of_missing(game_version, item_id, language='en'):
    """This missing piece's name in the given language, or None."""
    table = _tables().get(game_version or '')
    if not table or not isinstance(item_id, int):
        return None
    for candidat in (item_id, item_id - _MOUNT_ID_OFFSET):
        entree = table.get(str(candidat))
        if entree:
            return entree.get(language) or entree.get('en')
    return None


def missing_names(char, minimal_solution, language='en'):
    """Names of this build's missing pieces, in slot order, without duplicates."""
    par_slot = getattr(minimal_solution, 'item_per_slot', None) or {}
    if not par_slot:
        return []
    from fashionistapulp.modelresult import get_item_in_slot
    from fashionistapulp.structure import get_structure
    game_version = getattr(char, 'game_version', None) or 'dofus3'
    try:
        structure = get_structure(game_version)
    except Exception:
        return []
    noms = []
    for slot in sorted(par_slot, key=str):
        item_id = par_slot[slot]
        if item_id is None:
            continue
        if get_item_in_slot(structure, item_id, slot) is not None:
            continue
        nom = name_of_missing(game_version, item_id, language)
        if nom and nom not in noms:
            noms.append(nom)
    return noms
