# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Nommer les pieces qu'un build porte et que le catalogue n'a plus.

La section 42 disait a l'auteur <<certains de ses objets n'existent plus dans
le jeu>>. Il ne pouvait pas savoir LESQUELS, donc il ne pouvait rien y faire.
Ce module les nomme, dans sa langue.

Les noms viennent du catalogue du 4 novembre 2025 (`git show 02f18465a`), la
derniere photo qui les portait, table `item_names` comprise: les cinq langues
du site y sont.

**Attention a ce que cette table contient exactement.** 264 objets de ce
catalogue-la n'ont plus le meme numero chez nous, mais 222 d'entre eux sont
toujours dans notre catalogue sous un autre nombre, parce que notre
fournisseur a renumerote les montures: ceux-la sont RENDUS au build par
`legacy_ids.renumbered_item_id` et n'ont rien a faire ici. Ne restent ici que
les **42** qui n'ont vraiment aucun equivalent aujourd'hui, et ce sont les
versions sauvages des montures, que la source ne liste plus.

Ne pas confondre avec ce que fait `legacy_ids`: la, on RETROUVE une piece mal
numerotee; ici, la piece est vraiment absente et on se contente de la nommer,
parce que la nommer est tout ce qu'on peut faire honnetement
([[absence-in-data-is-not-absence-in-game]]: qu'elle ait quitte notre
catalogue ne prouve pas qu'elle ait quitte le jeu).
"""

import json
import os

#: L'espace d'identifiants des montures, le meme que `modelresult`. Une
#: monture est enregistree a cet offset, donc un build qui en porte une
#: stocke un nombre au-dela.
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
    """Le nom de cette piece disparue dans la langue demandee, ou None.

    L'identifiant stocke peut etre l'ankama nu ou l'ankama decale de l'espace
    des montures, selon ce que le catalogue en faisait le jour ou le build a
    ete enregistre. Les deux sont essayes, l'un apres l'autre.
    """
    table = _tables().get(game_version or '')
    if not table or not isinstance(item_id, int):
        return None
    for candidat in (item_id, item_id - _MOUNT_ID_OFFSET):
        entree = table.get(str(candidat))
        if entree:
            return entree.get(language) or entree.get('en')
    return None


def missing_names(char, minimal_solution, language='en'):
    """[noms] des pieces de ce build que le catalogue n'a plus, sans doublon.

    L'ordre est celui des emplacements, pour que deux lectures de la meme
    page disent la meme chose.
    """
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
