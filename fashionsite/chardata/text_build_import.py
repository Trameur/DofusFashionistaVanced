# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Reconstituer un build entier a partir de texte colle.

Le lecteur de captures d'ecran, livre plus tot, lit UN objet. Celui-ci lit un
build: le joueur colle ce qu'il a sous la main, une liste de noms ou les
infobulles de ses quinze pieces, et retrouve son equipement ici.

Trois choix, et chacun a une raison mesuree:

**Aucun format impose.** Chaque ligne est d'abord lue comme un jet, puis, si
elle n'en est pas un, cherchee dans le catalogue. Coller une liste de noms et
coller des infobulles completes marchent donc tous les deux, sans que le joueur
ait a savoir lequel on attendait, et dans le second cas **ses vrais jets
arrivent avec ses objets**: un import qui repose le stuff <<a l'identique>> et
jetterait les jets ne reposerait pas le meme stuff.

**Le catalogue n'est parcouru qu'une fois.** L'endpoint de recherche reconstruit
son vivier a chaque appel, ce qui est juste pour une frappe au clavier et
ruineux pour quarante lignes: le rapprochement tolerant compare la ligne a
chacun des milliers de noms.

**Le solveur ne tourne pas.** L'import repose le stuff a l'identique. Comparer,
modifier ou reoptimiser vient apres, et c'est le joueur qui le demande.
"""

import re

from chardata.forgemagie_view import (_closest_pool_entry, _normalized_text,
                                      _search_level, _search_types)
from chardata.inventory_view import _ocr_normalize, _ocr_stat_lexicon
from chardata.stat_range import get_stat_range
from chardata.translation_util import localized_stat_name
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


#: Une ligne de stat, exactement comme la page de l'inventaire la lit.
#:
#: Ce motif et les regles qui suivent sont le jumeau Python de `parseStatLine`,
#: qui vit dans un gabarit et tourne dans le navigateur. Les deux sont tenus a
#: la meme table de cas par un test qui fait passer les MEMES lignes dans les
#: deux implementations, l'une sous node, l'autre ici: dupliquer une regle sans
#: ce test, c'est se garantir deux comportements dans six mois.
_PLAGE = re.compile(r'\d\s*(?:a|à|to|bis)\s*\d', re.I)
_LIGNE_DE_STAT = re.compile(r'^[^0-9+\-]*?([+\-]?\s*\d[\d\s.,]*)\s*(%?)\s*(.+)$')


def _lit_ligne_de_stat(ligne, lexique):
    """{'key', 'value'} ou None si personne ne peut lire cette ligne.

    La regle qui a coute le plus cher est celle des groupes de chiffres.
    L'icone de la stat est souvent lue comme un chiffre, donc <<4 50 Force>>
    vaut bien 50. Mais joindre les groupes des qu'il y en a trois ou plus
    INVENTAIT un nombre: le separateur d'une fourchette mal lu faisait sortir
    476 de <<57 a 76 Force>> et 4560 de <<3 4 5 60 Force>>. Une ligne que
    personne ne peut lire doit revenir illisible, jamais plausible.
    """
    if _PLAGE.search(ligne):
        return None
    m = _LIGNE_DE_STAT.match(ligne)
    if not m:
        return None
    signe = -1 if '-' in m.group(1) else 1
    groupes = [g for g in re.split(r'[\s.,]+',
                                   re.sub(r'[+\-]', ' ', m.group(1)).strip())
               if g]
    if len(groupes) == 1:
        chiffres = groupes[0]
    elif all(len(g) == 3 for g in groupes[1:]):
        chiffres = ''.join(groupes)
    elif len(groupes) == 2:
        chiffres = groupes[1]
    else:
        return None
    valeur = signe * int(chiffres)
    if valeur == 0:
        return None
    etiquette = _ocr_normalize(m.group(3))
    if m.group(2) == '%':
        cle = lexique.get('% ' + etiquette) or lexique.get(etiquette)
    else:
        cle = lexique.get(etiquette) or lexique.get('% ' + etiquette)
    return {'key': cle, 'value': valeur} if cle else None


def _langue_du_texte(lignes, structure, langue):
    """La langue dont le lexique reconnait le plus de lignes.

    Le lecteur peut tres bien jouer en francais et lire le site en anglais.
    A egalite, sa langue gagne, comme dans la page de l'inventaire.
    """
    lexiques = _ocr_stat_lexicon(structure)
    meilleure = langue if langue in lexiques else 'en'

    def score(code):
        lexique = lexiques.get(code) or {}
        return sum(1 for l in lignes if _lit_ligne_de_stat(l, lexique))

    meilleur = score(meilleure)
    for code in sorted(lexiques):
        if code == meilleure:
            continue
        autre = score(code)
        if autre > meilleur:
            meilleur, meilleure = autre, code
    return meilleure, lexiques.get(meilleure) or {}


def _jets_de_la_piece(structure, item, jets, game_version):
    """Ce qu'on applique a la piece, et ce qu'on refuse d'y appliquer.

    **Un jet sur une stat que l'objet ne porte pas n'est PAS applique.** Le
    modele, lui, l'ajouterait: `Model._apply_stat_overrides` ajoute la stat a
    la piece quand elle n'y figure pas. Une ligne mal lue ferait donc naitre
    sur l'objet une caracteristique qu'il n'a jamais eue, et le solveur
    optimiserait autour. C'est exactement ce que le site promet de ne jamais
    faire.

    Un jet HORS FOURCHETTE, lui, est applique et signale. La forgemagie pousse
    legitimement un jet au-dessus de son maximum et peut en sacrifier un sous
    son minimum: seul le joueur sait, et le refuser serait faux.
    """
    portees = dict(item.stats or ())
    appliques = {}
    lignes = []
    for jet in jets:
        stat = structure.get_stat_by_key(jet['key'])
        if stat is None:
            continue
        # Le nom de la stat dans la langue du lecteur ET dans les mots de
        # SA version: `stat.name` est le libelle interne, et l'afficher tel
        # quel mettait <<Vitality>> et <<MP>> sur une page francaise.
        detail = {'key': jet['key'], 'value': jet['value'],
                  'name': localized_stat_name(stat.name, game_version),
                  'applied': False, 'out_of_range': False,
                  'low': None, 'high': None}
        if stat.id not in portees:
            lignes.append(detail)
            continue
        plage = get_stat_range(item, stat.id)
        if plage is not None:
            bas, haut = plage
            detail['low'], detail['high'] = bas, haut
            detail['out_of_range'] = not (bas <= jet['value'] <= haut)
        detail['applied'] = True
        appliques[stat.id] = jet['value']
        lignes.append(detail)
    return appliques, lignes


def read_items(text, game_version, language):
    """Lire un build dans du texte colle.

    Rend `item_ids` dans l'ordre du texte, `matched` pour l'apercu et
    `ignored` pour les lignes que rien n'a reconnues. Les trois sont montres
    au joueur AVANT qu'on cree quoi que ce soit: une ligne mal prise se voit
    et se retire, elle ne se decouvre pas dans le build.
    """
    structure = get_structure(game_version)

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

    # La langue se lit sur les JETS, avant de toucher au catalogue: la
    # detection n'a besoin que des lexiques. Le vivier de noms est ensuite
    # construit dans cette langue-la et non dans celle de l'interface, si bien
    # qu'un lecteur qui joue en francais et lit le site en anglais colle ses
    # infobulles francaises et retrouve ses objets. Sans jet dans le texte,
    # aucun signal: sa langue d'interface gagne, ce qui est le comportement
    # d'avant.
    langue_lue, lexique = _langue_du_texte(lignes, structure, language)
    pool = _pool(structure, langue_lue)

    #: La piece a laquelle les lignes de stats suivantes appartiennent. Une
    #: infobulle donne le nom puis ses jets, donc un nom reconnu ouvre une
    #: piece et tout ce qui suit lui revient jusqu'au nom suivant.
    courante = None
    jets_orphelins = 0

    for ligne in lignes:
        # Les stats d'abord: une ligne de jet n'est pas un candidat au nom, et
        # la tester ici evite de la soumettre au catalogue pour rien.
        jet = _lit_ligne_de_stat(ligne, lexique)
        if jet is not None:
            if courante is None:
                jets_orphelins += 1
                ignored.append(ligne)
            else:
                courante['jets_lus'].append(jet)
            continue

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
            courante = None
            continue
        # Deux Gelano se collent deux fois et doivent entrer deux fois; c'est
        # la meme LIGNE repetee par un copier-coller maladroit qu'on refuse.
        cle = (item.id, ligne)
        if cle in vus:
            courante = None
            continue
        vus.add(cle)
        item_ids.append(item.id)
        courante = {
            'line': ligne,
            'name': nom,
            'type_name': type_name,
            'level': item.level,
            'approximate': approche,
            'item': item,
            'jets_lus': [],
        }
        matched.append(courante)

    # Les jets, une fois qu'on sait a quelle piece ils reviennent.
    overrides = {}
    refuses = []
    for piece in matched:
        appliques, detail = _jets_de_la_piece(structure, piece['item'],
                                              piece['jets_lus'], game_version)
        piece['rolls'] = detail
        piece['out_of_range'] = any(d['out_of_range'] for d in detail)
        if appliques:
            overrides[piece['item'].id] = appliques
        for d in detail:
            if not d['applied']:
                refuses.append({'name': piece['name'], 'stat': d['name'],
                                'value': d['value']})
        del piece['item']
        del piece['jets_lus']

    return {
        'item_ids': item_ids,
        'matched': matched,
        'ignored': ignored,
        'truncated': tronque,
        'game_version': game_version,
        'stat_language': langue_lue,
        'overrides': overrides,
        'refused_rolls': refuses,
        'orphan_rolls': jets_orphelins,
    }
