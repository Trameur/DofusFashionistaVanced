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
from fashionistapulp.dofus_constants import (STATS_NAMES,
                                            TYPE_NAME_TO_SLOT_NUMBER)
from fashionistapulp.game_versions import GAME_VERSIONS, version_keys
from fashionistapulp.model import Model
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

#: Les trois stats dont un depassement est un EXO et non une stat
#: ajoutee a la piece. La liste vient du modele et n'est pas recopiee:
#: elle decide de ce qu'on ecrit sur un build, et deux copies qui
#: divergent feraient perdre des exos sans que rien ne rougisse.
EXO_STAT_KEYS = Model._EXO_STAT_KEYS


#: Les langues dans lesquelles un nom d'objet peut arriver, et l'ordre dans
#: lequel on les consulte apres celle du lecteur.
LANGUES = ('en', 'fr', 'es', 'pt', 'de')


def _pool(structure, language):
    """(vivier de la langue du lecteur, index exact par langue).

    Deux structures et pas une, parce que les deux recherches n'ont ni le meme
    cout ni le meme risque.

    **Le vivier** sert au rapprochement TOLERANT, qui compare la ligne a
    chaque entree. Mesure du 10 septembre 2026 sur Dofus 3: une ligne que rien
    ne reconnait coute 9,1 ms contre 3826 entrees, et 45,5 ms si on y met les
    cinq langues. A trois cents lignes collees, c'est treize secondes contre
    trois. Le vivier reste donc dans la langue du lecteur: reparer une lettre
    mal tapee est un service qu'on rend a quelqu'un qui ecrit dans SA langue.

    **L'index exact** est un dictionnaire, donc gratuit, et il porte les cinq
    langues plus le nom interne. C'est lui qui permet de relire un texte
    partage par un joueur d'une autre langue.

    Il est garde PAR LANGUE et non a plat, et ce n'est pas de la prudence
    gratuite: mesure du meme jour, un nom normalise designe deux objets
    DIFFERENTS d'une langue a l'autre 443 fois sur Retro et 215 fois sur
    Touch. <<robotas>> est Bedazzling Boots dans une langue et Roboots dans
    une autre, <<abracapa>> est Treecapa et Treecloak. Un index a plat aurait
    rendu l'un pour l'autre, en silence.
    """
    niveau = _search_level(structure)
    vus = set()
    pool = []
    index = {langue: {} for langue in LANGUES}
    index['_interne'] = {}
    for type_name in _search_types(structure, True):
        for item in structure.get_unique_items_by_type_and_level(type_name,
                                                                 niveau):
            if item.id in vus or item.removed:
                continue
            vus.add(item.id)
            nom = structure.get_item_name_in_language(item, language)
            entree = (_normalized_text(nom), item, nom, type_name)
            pool.append(entree)
            for langue in LANGUES:
                cle = _normalized_text(
                    structure.get_item_name_in_language(item, langue))
                if cle:
                    index[langue].setdefault(cle, entree)
            # Le nom INTERNE: c'est celui que <<Copier en texte>> ecrivait
            # avant qu'il ne passe au nom traduit, donc tous les textes deja
            # partages le portent. Mesure du 10 septembre 2026: il vaut le nom
            # anglais sur 382 chapeaux Dofus 3 sur 382.
            interne = _normalized_text(item.name)
            if interne:
                index['_interne'].setdefault(interne, entree)
    return pool, index


def _entree_exacte(requete, index, language):
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

    **La langue du lecteur passe en premier, et un desaccord fait taire.** Un
    meme nom normalise designe deux objets differents d'une langue a l'autre
    443 fois sur Retro (<<robotas>>: Bedazzling Boots ou Roboots). Quand la
    langue du lecteur ne tranche pas et que les autres se contredisent, on ne
    choisit pas: rendre un objet plausible pris pour un autre est pire que
    rendre une ligne non reconnue, que le joueur voit et corrige.
    """
    trouve = index.get(language, {}).get(requete)
    if trouve is not None:
        return trouve
    candidats = []
    for autre in LANGUES + ('_interne',):
        if autre == language:
            continue
        entree = index.get(autre, {}).get(requete)
        if entree is not None:
            candidats.append(entree)
    if not candidats:
        return None
    premier = candidats[0]
    if any(c[1].id != premier[1].id for c in candidats):
        return None
    return premier


#: Ce que le bouton <<Copier en texte>> du site ecrit, et que le site ne
#: savait pas relire.
#:
#: Mesure du 10 septembre 2026: colle tel quel, un build exporte par le site
#: rendait **zero objet reconnu**, les six lignes toutes ignorees. L'export
#: prefixe chaque piece de son emplacement (<<Hat: Creaking Tree Hat>>), et
#: l'import comparait la ligne entiere a un nom d'objet. Le rapprochement
#: tolerant ne pouvait pas rattraper: retirer <<Hat: >> coute cinq corrections
#: quand le plafond est a trois.
#:
#: Les emplacements sont ecrits en anglais interne par l'export, quelle que
#: soit la langue du lecteur, donc la liste vient de la meme table que lui.
_PREFIXE_EMPLACEMENT = re.compile(
    r'^(%s)\s*:\s*(.+)$' % '|'.join(sorted(TYPE_NAME_TO_SLOT_NUMBER)), re.I)

#: L'entete de l'export: <<Mon Cra - Cra lvl 200 - Retro>>. Le titre est libre
#: et peut contenir des tirets, donc on ancre sur la fin.
#:
#: La version est FACULTATIVE dans le motif, et ce n'est pas une commodite:
#: tous les textes exportes avant qu'on l'ajoute n'en ont pas, et une simple
#: liste de noms tapee a la main non plus. Absente, elle veut dire <<la version
#: de la page>>, qui est le comportement d'avant.
#: Le nom du build, s'il est la, COMMENCE et se termine sur un caractere
#: qui n'est pas un espace. Mesure: avec `(.*\S)` seul, le `\s+` qui precede
#: et le `.*` pouvaient tous deux prendre les espaces, et une ligne de 40 000
#: espaces apres le tiret coutait 8 secondes; avec `\S` en tete, chaque
#: partage echoue au premier caractere (py/polynomial-redos).
_ENTETE = re.compile(
    r'-\s+(\S+)\s+lvl\s+(\d{1,3})(?:\s+-\s+(\S(?:.*\S)?))?\s*$', re.I)

#: Le libelle de chaque version vers sa cle. Les libelles viennent du registre
#: et ne sont pas traduits, donc ils traversent les cinq langues.
_VERSION_PAR_LIBELLE = {
    GAME_VERSIONS[cle].label.lower(): cle
    for cle in version_keys(include_experimental=True)
}

#: Les deux lignes de caracteristiques de base que l'export ajoute.
#: <<Points:>> sont les points depenses en montant, <<Scrolls:>> les
#: parchotages. Le site garde les deux separement (`total_value` est leur
#: somme, `scrolled_value` la seconde), donc les melanger ferait revenir un
#: personnage different de celui qui est parti.
#: Apres le deux-points, le reste commence par un non-espace ou est vide:
#: `\s*` et `(.+)` pouvaient tous deux prendre les espaces, et le moteur
#: essayait chaque partage (py/polynomial-redos).
_LIGNE_POINTS = re.compile(r'^\s*points\s*:\s*(\S.*)?$', re.I)
_LIGNE_PARCHOS = re.compile(r'^\s*scrolls\s*:\s*(\S.*)?$', re.I)
#: Un nom de caracteristique est des mots separes par des espaces et se
#: termine sur une lettre: l'espace avant le nombre n'appartient qu'au
#: `\s+` qui suit. La classe `[A-Za-z ]+?` contenait l'espace et le
#: moteur pouvait le donner aux deux (py/polynomial-redos).
#:
#: Applique avec `match` sur le morceau depouille, pas avec `search`: une
#: recherche repart de chaque position, et sur <<a a a a...>> (20 000 mots
#: sans nombre) chaque depart refaisait tout le recul, 11,8 secondes
#: mesurees. Le site ecrit lui-meme <<Vitality 101 / Strength 50>>, le nom
#: est en tete de chaque morceau.
_UNE_CARACTERISTIQUE = re.compile(
    r'([A-Za-zÀ-ɏ]+(?: +[A-Za-zÀ-ɏ]+)*)\s+(\d{1,4})')


def _lit_caracteristiques(reste):
    """{nom interne: valeur} depuis <<Vitality 101 / Strength 50>>."""
    trouve = {}
    connus = {nom.lower(): nom for nom, _cle in STATS_NAMES}
    for morceau in reste.split('/'):
        m = _UNE_CARACTERISTIQUE.match(morceau.strip())
        if not m:
            continue
        nom = connus.get(_ocr_normalize(m.group(1)))
        if nom is None:
            continue
        trouve[nom] = int(m.group(2))
    return trouve


#: Une ligne de stat, exactement comme la page de l'inventaire la lit.
#:
#: Ce motif et les regles qui suivent sont le jumeau Python de `parseStatLine`,
#: qui vit dans un gabarit et tourne dans le navigateur. Les deux sont tenus a
#: la meme table de cas par un test qui fait passer les MEMES lignes dans les
#: deux implementations, l'une sous node, l'autre ici: dupliquer une regle sans
#: ce test, c'est se garantir deux comportements dans six mois.
_PLAGE = re.compile(r'\d\s*(?:a|à|to|bis)\s*\d', re.I)
#: Meme langage que le `parseStatLine` du gabarit, ecrit sans partage
#: ambigu (py/polynomial-redos): les espaces apres un signe n'existent
#: qu'apres un signe, les espaces DANS le nombre ne sont pris que s'ils
#: precedent un chiffre, un point ou une virgule, et il n'y a qu'un seul
#: `\s*` devant le libelle. Groupes: signe, nombre, pourcent, libelle.
_LIGNE_DE_STAT = re.compile(
    r'^[^0-9+\-]*?(?:([+\-])\s*)?(\d(?:[\d.,]|\s+(?=[\d.,]))*)'
    r'(?:\s*(%))?\s*(.+)$')


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
    signe = -1 if m.group(1) == '-' else 1
    groupes = [g for g in re.split(r'[\s.,]+', m.group(2).strip()) if g]
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
    etiquette = _ocr_normalize(m.group(4))
    if m.group(3) == '%':
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


def _jets_de_la_piece(structure, item, jets, game_version,
                      lignes_ajoutees=False):
    """Ce qu'on applique a la piece, et ce qu'on refuse d'y appliquer.

    **Un jet sur une stat que l'objet ne porte pas n'est PAS applique**, sauf
    pour les PA, les PM et la portee. Le modele ajoute la stat a la piece
    quand elle n'y figure pas (`Model._apply_stat_overrides`), donc une ligne
    mal lue ferait naitre sur l'objet une caracteristique qu'il n'a jamais eue
    et le solveur optimiserait autour.

    Les trois exceptions ne sont pas une tolerance, c'est le mecanisme des
    EXOS. Pour `ap`, `mp` et `range`, le modele n'ajoute rien a la piece: il
    la note porteuse d'exo (`_exo_carriers`) et `create_exo_constraints`
    ecrit alors `exo <= option + pieces porteuses portees`. Refuser ces
    lignes-la faisait donc perdre en silence l'exo que le joueur avait colle,
    et l'exo est ce qui distingue un build fini d'un build presque fini.

    Le nombre d'exos n'est pas plafonne ici: la contrainte n'a qu'une variable
    par stat, donc deux pieces porteuses ne donnent toujours qu'un point. La
    regle <<un point par stat pour tout le build>> est tenue par le modele,
    pas par cette lecture.

    Un jet HORS FOURCHETTE, lui, est applique et signale. La forgemagie pousse
    legitimement un jet au-dessus de son maximum et peut en sacrifier un sous
    son minimum: seul le joueur sait, et le refuser serait faux.

    `lignes_ajoutees`: pour une lecture STRUCTUREE (le lien d'un site de
    builds, jamais du texte), une ligne sur une stat que l'objet ne porte
    pas n'est pas une erreur de lecture mais une forgemagie exotique voulue
    par le joueur, et leur client l'ajoute a la piece comme le fait notre
    modele. Mesure sur le build DofusBook 23227661 le 11 septembre 2026,
    recoupe avec leur propre table d'effets: 8 dommages critiques sur un
    arc qui n'en porte pas, 2 coups critiques sur des bottes, 20 dommages
    sur un Dofus Tachete (le bonus conditionnel de son sort, que le joueur
    a modele en ligne). Refuser ces lignes rendait un build sans ses exos,
    ce que Thibaud a nomme le jour meme. Elles sont appliquees et marquees
    exo, sans fourchette puisqu'il n'y a pas de jet de catalogue derriere.
    """
    portees = dict(item.stats or ())
    appliques = {}
    lignes = []
    for jet in jets:
        stat = structure.get_stat_by_key(jet['key'])
        if stat is None:
            continue
        exo = ((jet['key'] in EXO_STAT_KEYS
                and jet['value'] > portees.get(stat.id, 0))
               or (lignes_ajoutees and stat.id not in portees))
        # Le nom de la stat dans la langue du lecteur ET dans les mots de
        # SA version: `stat.name` est le libelle interne, et l'afficher tel
        # quel mettait <<Vitality>> et <<MP>> sur une page francaise.
        detail = {'key': jet['key'], 'value': jet['value'],
                  'name': localized_stat_name(stat.name, game_version),
                  'applied': False, 'out_of_range': False, 'exo': exo,
                  'low': None, 'high': None}
        if stat.id not in portees and not exo:
            lignes.append(detail)
            continue
        if stat.id not in portees:
            # Un exo pur: la piece ne porte pas la stat et le modele ne la lui
            # ajoutera pas. Pas de fourchette a verifier non plus, il n'y a
            # pas de jet de catalogue derriere.
            detail['applied'] = True
            appliques[stat.id] = jet['value']
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
    pool, index = _pool(structure, langue_lue)

    #: La piece a laquelle les lignes de stats suivantes appartiennent. Une
    #: infobulle donne le nom puis ses jets, donc un nom reconnu ouvre une
    #: piece et tout ce qui suit lui revient jusqu'au nom suivant.
    courante = None
    jets_orphelins = 0

    char_class = None
    char_level = None
    version_lue = None
    points = {}
    parchos = {}

    for ligne in lignes:
        # Les lignes que le site ecrit lui-meme, en premier: elles portent des
        # chiffres et se feraient prendre pour des jets.
        m = _LIGNE_POINTS.match(ligne)
        if m:
            points.update(_lit_caracteristiques(m.group(1) or ''))
            continue
        m = _LIGNE_PARCHOS.match(ligne)
        if m:
            parchos.update(_lit_caracteristiques(m.group(1) or ''))
            continue
        m = _ENTETE.search(ligne)
        if m and char_class is None:
            char_class, char_level = m.group(1), int(m.group(2))
            if m.group(3):
                version_lue = _VERSION_PAR_LIBELLE.get(
                    m.group(3).strip().lower())
            continue

        # Les stats ensuite: une ligne de jet n'est pas un candidat au nom, et
        # la tester ici evite de la soumettre au catalogue pour rien.
        jet = _lit_ligne_de_stat(ligne, lexique)
        if jet is not None:
            if courante is None:
                jets_orphelins += 1
                ignored.append(ligne)
            else:
                courante['jets_lus'].append(jet)
            continue

        # <<Hat: Creaking Tree Hat>> est ce que l'export du site ecrit. Sans
        # cette ligne, le site ne relisait pas son propre export.
        emplacement = _PREFIXE_EMPLACEMENT.match(ligne)
        if emplacement:
            ligne = emplacement.group(2).strip()

        requete = _normalized_text(ligne)
        if len(requete) < MIN_LIGNE:
            ignored.append(ligne)
            continue
        entree = _entree_exacte(requete, index, langue_lue)
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
        'char_class': char_class,
        # La version que le TEXTE annonce, ou None s'il n'en annonce aucune.
        # L'appelant compare avec la sienne: ce n'est pas a la lecture de
        # decider ce qu'on fait d'un desaccord.
        'stated_version': version_lue,
        'char_level': char_level,
        'base_points': points,
        'base_scrolled': parchos,
        'overrides': overrides,
        'refused_rolls': refuses,
        'orphan_rolls': jets_orphelins,
    }
