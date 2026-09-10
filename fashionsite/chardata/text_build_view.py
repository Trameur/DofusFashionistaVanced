# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page qui reconstitue un build a partir de texte colle.

Meme forme que l'import DofusBook, et pour la meme raison: l'equipement est
montre AVANT que quoi que ce soit soit cree, donc le joueur voit ce qui va
arriver et peut s'en aller. Le solveur ne tourne pas.

Ce que cette page couvre et que le lien DofusBook ne couvre pas: un build prive,
un build lu sur une image, un build recopie d'un forum ou d'un Discord, et un
build qu'on a simplement sous les yeux dans le jeu. Il n'y a rien a publier
ailleurs pour l'amener ici.

Le niveau et la classe sont DEMANDES et non devines. Le texte d'une infobulle
porte le niveau de l'OBJET, jamais celui du personnage, et rien dans une liste
de noms ne nomme une classe. Les deviner reviendrait a inventer les deux
champs dont depend toute la suite.
"""

import logging

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata.dofusbook_view import (_classes_for, _place_items,
                                     _solution_path)
from chardata.lock_forbid import set_stat_overrides
from chardata.models import CharBaseStats
from chardata.text_build_import import MAX_LIGNES, read_items
from chardata.translation_util import localized_stat_name
from chardata.util import set_response, safe_int
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, STATS_NAMES,
                                             max_scroll_for_version)
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.structure import get_current_game_version
from fashionistapulp.translation import get_supported_language

logger = logging.getLogger(__name__)

#: Le texte colle. Trois cents lignes d'infobulles tiennent tres large
#: dedans, et au dela on lit un presse-papiers entier.
MAX_CARACTERES = 40000

NIVEAU_PAR_DEFAUT = 200


def _version(request):
    return getattr(request, 'game_version', None) or get_current_game_version()


def _url_pour_version(cle):
    """La meme page, sous le prefixe de l'autre version.

    Meme regle que `_solution_path`: une version vit sous son prefixe, et
    dofus3 n'en a pas.
    """
    prefixe = '' if cle == 'dofus3' else '/' + cle
    return '%s/import/text/' % prefixe


def _caracteristiques_pour_apercu(lu):
    """[{name, points, scrolled}] pour la liste montree avant la creation."""
    lignes = []
    for nom, _cle in STATS_NAMES:
        points = lu['base_points'].get(nom, 0)
        parchos = lu['base_scrolled'].get(nom, 0)
        if points or parchos:
            lignes.append({'name': localized_stat_name(nom),
                           'points': points, 'scrolled': parchos})
    return lignes


def _ecrit_les_caracteristiques(char, points, parchos):
    """Les points depenses et les parchotages, tels que le site les garde.

    `CharBaseStats.total_value` est la SOMME des deux et `scrolled_value` la
    seconde: c'est `get_stats_and_scrolled` qui refait la soustraction. Ecrire
    les points depenses dans `total_value` rendrait donc un personnage a qui
    il manque exactement ses parchotages.

    `create_build` a deja pose une ligne par caracteristique, donc on met a
    jour plutot que de creer: deux lignes pour la meme stat feraient gagner la
    premiere, en silence.
    """
    if not points and not parchos:
        return
    plafond = max_scroll_for_version(char.game_version)
    for nom, _cle in STATS_NAMES:
        depenses = max(0, points.get(nom, 0))
        parcho = min(max(0, parchos.get(nom, 0)), plafond)
        if not depenses and not parcho:
            continue
        ligne, _neuve = CharBaseStats.objects.get_or_create(
            char=char, stat=nom,
            defaults={'total_value': 0, 'scrolled_value': 0})
        ligne.total_value = depenses + parcho
        ligne.scrolled_value = parcho
        ligne.save()


def text_build(request):
    """GET montre la zone de texte, POST la lit, confirmer cree le build."""
    texte = (request.POST.get('text') or '')[:MAX_CARACTERES]
    version = _version(request)

    if request.method != 'POST' or not texte.strip():
        return set_response(request, 'chardata/text_build.html', {
            'text': '',
            'version_label': get_game_version(version).label,
            'login_problem': is_anon_cant_create(request),
        })

    lu = read_items(texte, version, get_supported_language())

    # Le texte dit de quelle version il vient, et ce n'est pas celle de la
    # page. On ne cherche PAS ses objets dans le mauvais catalogue.
    #
    # Mesure du 10 septembre 2026: 1594 des 6269 noms Retro existent aussi en
    # Dofus 3, et 482 d'entre eux y designent un objet d'un AUTRE NIVEAU
    # (<<Amulet of the Valiant Heart>> passe de 41 a 200). Depuis Touch, 818
    # sur 2618. Le lecteur aurait recu un build plausible qui n'est pas le
    # sien, ce qui est le pire des resultats possibles.
    annoncee = lu['stated_version']
    if annoncee and annoncee != version:
        return set_response(request, 'chardata/text_build.html', {
            'text': texte,
            'version_label': get_game_version(version).label,
            'error': _('This build comes from %(source)s and you are on '
                       '%(here)s. The same name can be a different item in '
                       'each game, so nothing was read.')
                     % {'source': get_game_version(annoncee).label,
                        'here': get_game_version(version).label},
            'other_version_url': _url_pour_version(annoncee),
            'other_version_label': get_game_version(annoncee).label,
            'login_problem': is_anon_cant_create(request),
        })

    if not lu['item_ids']:
        return set_response(request, 'chardata/text_build.html', {
            'text': texte,
            'version_label': get_game_version(version).label,
            'error': _('No item in that text matched our catalogue for this '
                       'version. Check the game version at the top, and that '
                       'the item names are on their own lines.'),
            'ignored': lu['ignored'][:12],
            'login_problem': is_anon_cant_create(request),
        })

    # La classe et le niveau viennent du texte QUAND il les porte, ce qui est
    # le cas d'un build exporte par le site: son entete dit <<Mon Cra - Cra
    # lvl 200>>. C'est une source de premiere main, la notre, donc les
    # pre-remplir n'est pas les deviner. Le choix reste affiche et modifiable.
    char_class = request.POST.get('char_class') or ''
    if not char_class and lu['char_class'] in CHARACTER_CLASSES:
        char_class = lu['char_class']
    niveau = safe_int(request.POST.get('level'),
                      lu['char_level'] or NIVEAU_PAR_DEFAUT)

    if not request.POST.get('confirm') or char_class not in CHARACTER_CLASSES:
        return set_response(request, 'chardata/text_build.html', {
            'text': texte,
            'confirm': True,
            'version_label': get_game_version(version).label,
            'matched': lu['matched'],
            'ignored': lu['ignored'][:12],
            'ignored_total': len(lu['ignored']),
            'truncated': lu['truncated'],
            'max_lines': MAX_LIGNES,
            'refused_rolls': lu['refused_rolls'][:12],
            'level': niveau,
            'char_class': char_class,
            'base_points': _caracteristiques_pour_apercu(lu),
            'classes': _classes_for(version),
            'login_problem': is_anon_cant_create(request),
        })

    char = create_build(request, char_class, niveau, set(), version,
                        name=_('Imported build'))
    _ecrit_les_caracteristiques(char, lu['base_points'], lu['base_scrolled'])
    _place_items(char, lu['item_ids'], origin='pasted_text')
    # Les jets APRES la pose des objets: `_place_items` appelle set_minimal_
    # solution, qui ecrit sur le char, et ecrire les overrides avant se
    # ferait ecraser. Un seul save pour tout le lot, la ou
    # set_item_stat_override en fait un par caracteristique.
    if lu['overrides']:
        set_stat_overrides(char, lu['overrides'])
    logger.info('imported %d items and %d rolled stats from pasted text '
                'into char %s', len(lu['item_ids']),
                sum(len(v) for v in lu['overrides'].values()), char.id)
    return HttpResponseRedirect(_solution_path(char))
