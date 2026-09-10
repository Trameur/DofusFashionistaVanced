# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Reconstituer un build entier a partir de texte colle.

Le lecteur de captures d'ecran, livre plus tot, lit UN objet. Celui-ci lit un
build: le joueur colle ce qu'il a sous la main, une liste de noms ou les
infobulles de ses quinze pieces, et retrouve son equipement ici.

Trois choix, et chacun a une raison mesuree:

**Aucun format impose.** Chaque ligne est essayee contre le catalogue. Une
ligne de stat ne ressemble a aucun nom d'objet, donc elle ne resout rien et
elle est signalee comme ignoree. Coller une liste de noms et coller des
infobulles completes marchent donc tous les deux, sans que le joueur ait a
savoir lequel on attendait.

**Le catalogue n'est parcouru qu'une fois.** L'endpoint de recherche reconstruit
son vivier a chaque appel, ce qui est juste pour une frappe au clavier et
ruineux pour quarante lignes: le rapprochement tolerant compare la ligne a
chacun des milliers de noms.

**Le solveur ne tourne pas.** L'import repose le stuff a l'identique. Comparer,
modifier ou reoptimiser vient apres, et c'est le joueur qui le demande.
"""

from chardata.forgemagie_view import (_closest_pool_entry, _normalized_text,
                                      _search_level, _search_types)
from fashionistapulp.dofus_constants import TYPE_NAME_TO_SLOT_NUMBER
from fashionistapulp.structure import get_structure

#: En dessous, le rapprochement tolerant se tairait de toute facon, et une
#: ligne de deux caracteres est une sous-chaine de trop de noms.
MIN_LIGNE = 5

#: Combien de lignes on accepte de lire. Un build tient en quinze pieces et
#: leurs infobulles; au dela on lit un presse-papiers entier, et chaque ligne
#: coute un parcours du catalogue.
MAX_LIGNES = 300

#: Combien d'objets un build peut recevoir, tous types confondus.
MAX_OBJETS = sum(TYPE_NAME_TO_SLOT_NUMBER.values())


def _pool(structure, language):
    """(nom normalise, objet, nom affiche, type) pour tout le catalogue."""
    niveau = _search_level(structure)
    vus = set()
    pool = []
    for type_name in _search_types(structure, True):
        for item in structure.get_unique_items_by_type_and_level(type_name,
                                                                 niveau):
            if item.id in vus or item.removed:
                continue
            vus.add(item.id)
            nom = structure.get_item_name_in_language(item, language)
            pool.append((_normalized_text(nom), item, nom, type_name))
    return pool


def _entree_exacte(requete, pool):
    """Le nom entier, pas une sous-chaine.

    L'autocompletion accepte une sous-chaine parce qu'elle repond a quelqu'un
    qui TAPE: trois lettres doivent proposer des objets. Ici la ligne est
    collee, donc elle porte le nom complet, et la sous-chaine n'apporte rien
    tout en ouvrant une faute: <<Force>>, le libelle de stat, est contenu dans
    des noms d'objets, et une infobulle collee en entier ferait alors entrer
    un objet que le joueur n'a jamais porte.

    Ce qui rattrape une ligne imparfaite, c'est le rapprochement tolerant de
    l'appelant, borne a trois corrections et a un ecart de deux avec le
    second candidat: il repare une lettre mal lue, il n'invente pas un objet
    a partir d'un mot commun.
    """
    for entree in pool:
        if entree[0] == requete:
            return entree
    return None


def read_items(text, game_version, language):
    """Lire un build dans du texte colle.

    Rend `item_ids` dans l'ordre du texte, `matched` pour l'apercu et
    `ignored` pour les lignes que rien n'a reconnues. Les trois sont montres
    au joueur AVANT qu'on cree quoi que ce soit: une ligne mal prise se voit
    et se retire, elle ne se decouvre pas dans le build.
    """
    structure = get_structure(game_version)
    pool = _pool(structure, language)

    item_ids = []
    matched = []
    ignored = []
    vus = set()
    tronque = False

    lignes = [l.strip() for l in (text or '').splitlines()]
    lignes = [l for l in lignes if l]
    if len(lignes) > MAX_LIGNES:
        lignes = lignes[:MAX_LIGNES]
        tronque = True

    for ligne in lignes:
        requete = _normalized_text(ligne)
        if len(requete) < MIN_LIGNE:
            ignored.append(ligne)
            continue
        entree = _entree_exacte(requete, pool)
        approche = False
        if entree is None:
            entree = _closest_pool_entry(requete, pool)
            approche = entree is not None
        if entree is None:
            ignored.append(ligne)
            continue
        _plain, item, nom, type_name = entree
        if len(item_ids) >= MAX_OBJETS:
            tronque = True
            continue
        # Deux Gelano se collent deux fois et doivent entrer deux fois; c'est
        # la meme LIGNE repetee par un copier-coller maladroit qu'on refuse.
        cle = (item.id, ligne)
        if cle in vus:
            continue
        vus.add(cle)
        item_ids.append(item.id)
        matched.append({
            'line': ligne,
            'name': nom,
            'type_name': type_name,
            'level': item.level,
            'approximate': approche,
        })

    return {
        'item_ids': item_ids,
        'matched': matched,
        'ignored': ignored,
        'truncated': tronque,
        'game_version': game_version,
    }
