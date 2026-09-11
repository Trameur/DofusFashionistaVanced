# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Les pieces que la migration de novembre 2025 a laissees derriere.

Le 5 novembre 2025, entre les commits `02f18465a` et `71e9ba059`, les
identifiants internes du catalogue sont passes d'un compteur sequentiel
(1, 2, 3...) a l'identifiant Ankama de chaque objet. Une migration a ete
ecrite le jour meme et elle est saine: `id_mapping.json`, encore a la racine
du depot, ne change le type d'aucun objet.

Elle ne portait que **3519 des 3782 objets** que le catalogue avait ce
jour-la. Les 263 autres sont restes dans l'ancienne numerotation au fond des
builds enregistres, et un petit nombre y designe aujourd'hui, par pur hasard,
un objet qui n'a rien a voir. Mesure du 11 septembre 2026 sur la copie de
production, en vrai:

- le build 133534 porte <<Hozuki Lampulet>>, une amulette, dans son
  emplacement d'arme: l'ancien 2396 etait l'Arc d'Archonte;
- le build 135608 porte deux paires de bottes dans ses emplacements
  d'amulette et de ceinture: les anciens 1623 et 1624 etaient l'Amulette et
  la Ceinture de Grute.

`legacy_item_ids.json` porte la table COMPLETE du 4 novembre 2025, les 3782
objets, lue sur le dump de ce jour-la. La traduction n'est appliquee que
lorsqu'elle repare: un identifiant qui convient deja a son emplacement n'est
jamais touche, et un identifiant traduit qui ne conviendrait pas davantage
est laisse tel quel. Rien n'est reecrit dans la base
([[no-retrofit-user-builds]]): la reparation vit le temps d'une lecture.

Mesure de ce qu'elle rend: **152 builds partages redeviennent entiers** et
364 autres s'ameliorent, sur les 1476 que la galerie ecartait.

Seul Dofus 3 est couvert. Les autres versions avaient leur propre
numerotation, et le comptage n'a trouve qu'un seul build Touch ecarte: il n'y
a pas de population a reparer ailleurs.
"""

import json
import os

_CHEMIN = os.path.join(os.path.dirname(__file__), 'legacy_item_ids.json')
_TABLES = None


def _tables():
    global _TABLES
    if _TABLES is None:
        with open(_CHEMIN, encoding='utf-8') as fichier:
            _TABLES = json.load(fichier)
    return _TABLES


def ankama_id_of_legacy(game_version, item_id):
    """L'identifiant Ankama que portait cet ancien numero, ou None."""
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
    """{emplacement: identifiant} corrige, ou None si rien n'etait a corriger.

    La regle tient en une phrase: on ne touche a un emplacement que si ce
    qu'il porte ne lui convient pas ET si l'ancienne numerotation y met
    quelque chose qui lui convient. Une piece qui va bien n'est jamais
    deplacee, et une traduction qui n'arrange rien n'est jamais faite.
    """
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
        ankama = ankama_id_of_legacy(game_version, item_id)
        if ankama is None:
            continue
        autre = structure.items_dict_ankama.get(ankama)
        if not _fits(structure, slot, autre):
            continue
        corrige[slot] = autre.id
        change = True
    return corrige if change else None


def repair_minimal_solution(char, minimal_solution):
    """Pose la reparation sur une solution stockee, en memoire seulement."""
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
    if corrige is None:
        return False
    minimal_solution.item_per_slot = corrige
    return True
