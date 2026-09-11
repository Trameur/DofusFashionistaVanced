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

Depuis le 11 septembre 2026 elle repare une seconde chose: les montures que
notre fournisseur de donnees a RENUMEROTEES. La Dragodinde Amande avait
l'ankama 1 en novembre 2025 et porte aujourd'hui un numero au-dela de 33000;
le catalogue les a toujours, sous d'autres nombres. 222 des 264 objets qui
paraissaient disparus se retrouvent ainsi, par leur nom anglais exact et leur
type, sans une seule ambiguite.

Seul Dofus 3 est couvert. Les autres versions avaient leur propre
numerotation, et le comptage n'a trouve qu'un seul build Touch ecarte: il n'y
a pas de population a reparer ailleurs.
"""

import json
import os

_CHEMIN = os.path.join(os.path.dirname(__file__), 'legacy_item_ids.json')
_TABLES = None

#: L'espace d'identifiants des montures, le meme que `modelresult`.
_MOUNT_ID_OFFSET = 1000000

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
    """L'objet d'aujourd'hui qui porte le nom de cette monture d'hier.

    Notre fournisseur de donnees a RENUMEROTE les montures: la Dragodinde
    Amande avait l'ankama 1 en novembre 2025 et porte aujourd'hui un numero
    au-dela de 33000. Le catalogue les a toujours, sous d'autres nombres.

    L'appariement se fait sur le nom anglais EXACT et le meme type, et
    seulement quand un seul objet repond: 222 des 264 disparus s'y
    retrouvent, zero ambiguite, et les 42 qui restent sont les versions
    sauvages, que la source ne liste plus. Un appariement par nom est plus
    faible qu'un appariement par numero, donc il ne sert qu'a REPARER: si
    l'objet trouve ne convient pas a l'emplacement, rien n'est fait.

    L'identifiant stocke peut etre l'ankama nu ou decale de l'espace des
    montures, selon le jour ou le build a ete enregistre.
    """
    table = _renumerotes().get(game_version or '')
    if not table or not isinstance(item_id, int):
        return None
    for candidat in (item_id, item_id - _MOUNT_ID_OFFSET):
        trouve = table.get(str(candidat))
        if trouve is not None:
            return trouve
    return None


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
        autre = None
        ankama = ankama_id_of_legacy(game_version, item_id)
        if ankama is not None:
            autre = structure.items_dict_ankama.get(ankama)
        if not _fits(structure, slot, autre):
            # Seconde chance: une monture que la source a renumerotee, que
            # notre catalogue a toujours sous un autre nombre.
            neuf = renumbered_item_id(game_version, item_id)
            autre = structure.get_item_by_id(neuf) if neuf is not None else None
        if not _fits(structure, slot, autre):
            continue
        corrige[slot] = autre.id
        change = True
    return corrige if change else None


def _reslot_mismatched(structure, par_slot):
    """Repose une piece dont le type ne va pas avec son emplacement, quand un
    emplacement du sien est libre.

    Sans cela la page l'affiche sous le mauvais nom: mesure du 11 septembre
    2026 sur de vrais builds partages, une cape annoncee comme un anneau, un
    bouclier comme une arme, une amulette comme un Dofus. La page dit alors
    quelque chose de faux a chaque visiteur.

    On ne deplace jamais une piece qui va bien, et on ne prend jamais la
    place d'une autre: s'il n'y a pas d'emplacement libre du bon type, la
    piece reste ou elle est. L'ordre de parcours est fixe, pour que deux
    lectures de la meme page rangent pareil.
    """
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
    change = corrige is not None
    corrige = dict(corrige if change else par_slot)
    # Puis les pieces qui, une fois retrouvees ou non, restent rangees sous
    # un type qui n'est pas le leur.
    if _reslot_mismatched(structure, corrige):
        change = True
    if not change:
        return False
    minimal_solution.item_per_slot = corrige
    return True
