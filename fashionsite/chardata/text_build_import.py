# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Read a whole build from pasted text: item names, tooltips and rolls."""

import re

from chardata.forgemagie_view import (_closest_pool_entry, _normalized_text,
                                      _search_level, _search_types)
from chardata.inventory_view import _ocr_normalize, _ocr_stat_lexicon
from chardata.stat_range import get_stat_range
from chardata.translation_util import (LOCALIZED_CHARACTER_CLASSES,
                                       localized_stat_name)
from fashionistapulp.dofus_constants import (STATS_NAMES,
                                            TYPE_NAME_TO_SLOT_NUMBER)
from fashionistapulp.game_versions import GAME_VERSIONS, version_keys
from fashionistapulp.model import Model
from fashionistapulp.structure import get_structure

# Shorter lines are a substring of too many names
MIN_LIGNE = 5

MAX_LIGNES = 300

# How many items a build can hold, all slots
MAX_OBJETS = sum(TYPE_NAME_TO_SLOT_NUMBER.values())

# Going over the item's value on these stats is an exo
EXO_STAT_KEYS = Model._EXO_STAT_KEYS


# Languages an item name can come in, tried in this order after the reader's
LANGUES = ('en', 'fr', 'es', 'pt', 'de')


def _pool(structure, language):
    """(fuzzy pool in the reader's language, exact index per language)."""
    # Per language: "robotas" is Bedazzling Boots in one, Roboots in another
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
            # Older "Copy as text" exports wrote the internal name
            interne = _normalized_text(item.name)
            if interne:
                index['_interne'].setdefault(interne, entree)
    return pool, index


def _entree_exacte(requete, index, language):
    """Whole-name match, reader's language first; None if other languages disagree."""
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


def _mots_traduits(msgids):
    """The msgids and their translations in the five languages, longest first."""
    from django.utils.translation import gettext, override
    mots = set()
    for msgid in msgids:
        if not msgid:
            continue
        mots.add(msgid)
        for langue in LANGUES:
            with override(langue):
                mot = gettext(msgid)
                if mot:
                    mots.add(mot)
    # Longest first so a word inside another one does not win
    return sorted(mots, key=len, reverse=True)


# Slot prefix of our own export, "Hat: Creaking Tree Hat", in any language
_PREFIXE_EMPLACEMENT = re.compile(
    r'^(%s)\s*:\s*(.+)$'
    % '|'.join(re.escape(mot)
               for mot in _mots_traduits(sorted(TYPE_NAME_TO_SLOT_NUMBER))),
    re.I)


def _mots_de_niveau():
    """The header's "lvl" word in the five languages."""
    return _mots_traduits(['lvl'])


def _classes_par_nom():
    """{lowercase class name: internal name}, in the five languages."""
    from django.utils.translation import override
    par_nom = {}
    for interne in LOCALIZED_CHARACTER_CLASSES:
        par_nom[interne.lower()] = interne
    for langue in LANGUES:
        with override(langue):
            for interne, nom in LOCALIZED_CHARACTER_CLASSES.items():
                par_nom.setdefault(str(nom).lower(), interne)
    return par_nom


# Export header "My Cra - Cra lvl 200 - Retro", version optional, read from the end
_ENTETE = re.compile(
    r'-\s+(\S+)\s+(?:%s)\s+(\d{1,3})(?:\s+-\s+(\S(?:.*\S)?))?\s*$'
    % '|'.join(re.escape(mot) for mot in _mots_de_niveau()), re.I)

_CLASSE_PAR_NOM = _classes_par_nom()

# Version labels are not translated; experimental versions are never reader-facing
_VERSION_PAR_LIBELLE = {
    GAME_VERSIONS[cle].label.lower(): cle
    for cle in version_keys()
}

# Base stats lines of the export: Points (spent on level up) and Scrolls
_LIGNE_POINTS = re.compile(
    r'^\s*(?:%s)\s*:\s*(\S.*)?$'
    % '|'.join(re.escape(mot) for mot in _mots_traduits(['Points'])), re.I)
_LIGNE_PARCHOS = re.compile(
    r'^\s*(?:%s)\s*:\s*(\S.*)?$'
    % '|'.join(re.escape(mot) for mot in _mots_traduits(['Scrolls'])), re.I)
# "Vitality 101". Use match, not search: search backtracks from every position
_UNE_CARACTERISTIQUE = re.compile(
    r'([A-Za-zÀ-ɏ]+(?: +[A-Za-zÀ-ɏ]+)*)\s+(\d{1,4})')


def _caracteristiques_par_nom():
    """{normalised stat name: internal name}, in the five languages."""
    from django.utils.translation import override
    par_nom = {}
    for nom, _cle in STATS_NAMES:
        par_nom[_ocr_normalize(nom)] = nom
    for langue in LANGUES:
        with override(langue):
            for nom, _cle in STATS_NAMES:
                par_nom.setdefault(_ocr_normalize(localized_stat_name(nom)),
                                   nom)
    return par_nom


_CARACTERISTIQUE_PAR_NOM = _caracteristiques_par_nom()


def _lit_caracteristiques(reste):
    """{internal name: value} from "Vitality 101 / Strength 50"."""
    trouve = {}
    connus = _CARACTERISTIQUE_PAR_NOM
    for morceau in reste.split('/'):
        m = _UNE_CARACTERISTIQUE.match(morceau.strip())
        if not m:
            continue
        nom = connus.get(_ocr_normalize(m.group(1)))
        if nom is None:
            continue
        trouve[nom] = int(m.group(2))
    return trouve


# Python copy of parseStatLine in the inventory template, keep both in sync
_PLAGE = re.compile(r'\d\s*(?:a|à|to|bis)\s*\d', re.I)
# Groups: sign, number, percent, label
_LIGNE_DE_STAT = re.compile(
    r'^[^0-9+\-]*?(?:([+\-])\s*)?(\d(?:[\d.,]|\s+(?=[\d.,]))*)'
    r'(?:\s*(%))?\s*(.+)$')


def _lit_ligne_de_stat(ligne, lexique):
    """{'key', 'value'}, or None when the line cannot be read."""
    if _PLAGE.search(ligne):
        return None
    m = _LIGNE_DE_STAT.match(ligne)
    if not m:
        return None
    signe = -1 if m.group(1) == '-' else 1
    groupes = [g for g in re.split(r'[\s.,]+', m.group(2).strip()) if g]
    # The stat icon often reads as a digit: "4 50 Force" is 50
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
    """Language whose lexicon reads the most lines, the reader's on a tie."""
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
    """(applied {stat id: value}, detail per roll line)."""
    # A stat the item lacks is refused unless exo or lignes_ajoutees (site links)
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
        detail = {'key': jet['key'], 'value': jet['value'],
                  'name': localized_stat_name(stat.name, game_version),
                  'applied': False, 'out_of_range': False, 'exo': exo,
                  'low': None, 'high': None}
        if stat.id not in portees and not exo:
            lignes.append(detail)
            continue
        if stat.id not in portees:
            # Pure exo, no catalogue range to check
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
    """Read a build from pasted text."""
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

    # The game language can differ from the site one, guess it from the rolls
    langue_lue, lexique = _langue_du_texte(lignes, structure, language)
    pool, index = _pool(structure, langue_lue)

    # Item the next roll lines belong to, until the next item name
    courante = None
    jets_orphelins = 0

    char_class = None
    char_level = None
    version_lue = None
    points = {}
    parchos = {}

    for ligne in lignes:
        # Our own export lines first, their numbers look like rolls
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
            # Internal class name, the view checks CHARACTER_CLASSES
            char_class = _CLASSE_PAR_NOM.get(m.group(1).lower(), m.group(1))
            char_level = int(m.group(2))
            if m.group(3):
                version_lue = _VERSION_PAR_LIBELLE.get(
                    m.group(3).strip().lower())
            continue

        jet = _lit_ligne_de_stat(ligne, lexique)
        if jet is not None:
            if courante is None:
                jets_orphelins += 1
                ignored.append(ligne)
            else:
                courante['jets_lus'].append(jet)
            continue

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
        # Two Gelanos are two items, only the exact same line is a duplicate
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
        # Version named in the text header, or None
        'stated_version': version_lue,
        'char_level': char_level,
        'base_points': points,
        'base_scrolled': parchos,
        'overrides': overrides,
        'refused_rolls': refuses,
        'orphan_rolls': jets_orphelins,
    }
