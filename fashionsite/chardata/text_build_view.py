# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page qui reconstitue un build a partir de ce que le lecteur a sous la
main: des noms colles, des infobulles, un lien vers un build public d'un
autre site, des captures d'ecran, ou un melange de tout ca.

Une seule porte. Le 11 septembre 2026 il y en avait deux, dont une nommee
d'apres le site qu'elle lisait, et Thibaud: <<le but c'est que l'import
soit un peu site neutre, genre colle le lien de ton site ou envoie le
screenshot de ton build, et ca essaie d'importer et indique juste quels
items il n'a pas reussi a lire>>. La page essaie donc tout, dans cet ordre:
les lignes qui sont des liens, puis le reste comme du texte, et elle rend
compte piece par piece de ce qu'elle a lu et de ce qu'elle a laisse.

L'equipement est montre AVANT que quoi que ce soit soit cree, donc le
joueur voit ce qui va arriver et peut s'en aller. Le solveur ne tourne pas.

Le niveau et la classe sont DEMANDES et non devines. Le texte d'une infobulle
porte le niveau de l'OBJET, jamais celui du personnage, et rien dans une liste
de noms ne nomme une classe; un lien porte parfois le niveau, jamais la classe
dans une numerotation qui soit celle d'Ankama. Les deviner reviendrait a
inventer les deux champs dont depend toute la suite.
"""

import logging
import re

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata import build_link_import
from chardata.dofusbook_import import ImportError_
from chardata.dofusbook_view import (_classes_for, _place_items,
                                     _preview, _solution_path)
from chardata.lock_forbid import set_stat_overrides
from chardata.models import CharBaseStats
from chardata.screenshot_reader import language_options
from chardata.text_build_import import (MAX_LIGNES, _jets_de_la_piece,
                                        read_items)
from chardata.translation_util import localized_stat_name
from chardata.util import set_response, safe_int
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, STATS_NAMES,
                                             max_scroll_for_version)
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.structure import get_current_game_version, get_structure
from fashionistapulp.translation import get_supported_language

logger = logging.getLogger(__name__)

#: Le texte colle. Trois cents lignes d'infobulles tiennent tres large
#: dedans, et au dela on lit un presse-papiers entier.
MAX_CARACTERES = 40000

NIVEAU_PAR_DEFAUT = 200

#: Une ligne qui n'est qu'une adresse. Un lien au milieu d'une phrase n'est
#: pas un lien colle, c'est du texte.
_LIGNE_LIEN = re.compile(r'^(?:https?://\S+|www\.\S+)$', re.I)

#: La couture que les tests remplacent pour ne jamais toucher le reseau:
#: le registre des lecteurs, un par site que le serveur sait lire.
read_build = build_link_import.read


def _version(request):
    return getattr(request, 'game_version', None) or get_current_game_version()


def _url_pour_version(cle):
    """La meme page, sous le prefixe de l'autre version.

    Meme regle que `_solution_path`: une version vit sous son prefixe, et
    dofus3 n'en a pas.
    """
    prefixe = '' if cle == 'dofus3' else '/' + cle
    return '%s/import/text/' % prefixe


def _raisons_du_lien():
    """Une phrase par refus qu'un lien peut valoir, sans nommer le site: la
    phrase vaut pour n'importe quel site que le serveur saura lire."""
    return {
        'not_a_link': _('We cannot read links from that site yet. Paste the '
                        'item names instead.'),
        'short_link': _('Short d-bk.net links do not say which game the build '
                        'belongs to. Open the link and paste the full address.'),
        'not_found': _('No public build at that link.'),
        'refused': _('That site refused our request.'),
        'unreachable': _('That site could not be reached. Try again later.'),
        'unreadable': _('That site answered something we could not read.'),
        'empty': _('That build came back with no items.'),
        'wrong_version': _('Those items do not exist in that version of the '
                           'game. Check the link.'),
    }


def separe_les_liens(texte):
    """(le texte sans ses lignes de lien, [liens lisibles], [liens que
    personne ne lit]).

    Une ligne de lien vers un site que le serveur sait lire est lue comme un
    build; une ligne de lien vers n'importe quel autre site est rendue au
    lecteur dans une liste a part, pour qu'il sache que ce n'est pas un nom
    d'objet mal ecrit mais un site que le serveur ne lit pas encore.
    """
    reste, lisibles, illisibles = [], [], []
    for ligne in texte.splitlines():
        candidat = ligne.strip()
        if _LIGNE_LIEN.match(candidat):
            if build_link_import.recognises(candidat):
                lisibles.append(candidat)
            else:
                illisibles.append(candidat)
        else:
            reste.append(ligne)
    return '\n'.join(reste), lisibles, illisibles


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


def _reponse(request, params):
    """La page, avec ce que ses entrees partagent.

    Le lecteur de captures vit dans la meme page que la zone de texte et n'est
    qu'une facon d'y ecrire, donc il est disponible sur tous les etats de la
    page: le premier affichage, les refus, et l'apercu. Ajouter la liste
    des langues a un seul d'entre eux l'aurait fait disparaitre des qu'un
    lecteur se trompe de version.
    """
    params.setdefault('ocr_languages',
                      language_options(get_supported_language()))
    # Les sites que le serveur sait lire, sous le champ: une information,
    # pas une enseigne, et elle suit le registre.
    params.setdefault('link_sites', ', '.join(build_link_import.readable_sites()))
    return set_response(request, 'chardata/text_build.html', params)


def _pieces_du_lien(build, structure, version):
    """Les objets d'un lien, dans la forme des objets lus dans le texte, avec
    la forgemagie que le lien porte piece par piece.

    ([pieces], {item id: {stat id: valeur}}, [jets refuses]). Leur identifiant
    Ankama a decide de la piece, rien n'est approximatif. Un jet du lien est
    une valeur FINALE de ligne, exactement ce que nos overrides gardent, et
    il passe par la meme regle qu'un jet colle (`_jets_de_la_piece`):
    applique quand la piece porte la stat, exo pour les PA, PM et portee.
    Une ligne sur une stat que la piece ne porte pas est AJOUTEE et non
    refusee: un lien n'est pas une lecture d'OCR, c'est une forgemagie
    exotique voulue (8 dommages critiques sur un arc qui n'en porte pas,
    mesure sur le build 23227661). Thibaud, 11 septembre 2026: <<l'import
    de dofusbook ne prend pas bien en compte ... les FM sur les items>>;
    mesure, la liste des jets etait vide, pas lue.
    """
    jets_par_piece = build.get('rolls') or {}
    pieces, overrides, refuses = [], {}, []
    for piece in _preview(build):
        item = structure.get_item_by_id(piece['id'])
        appliques, detail = _jets_de_la_piece(
            structure, item, jets_par_piece.get(piece['id']) or [], version,
            lignes_ajoutees=True)
        pieces.append({'name': piece['name'], 'approximate': False,
                       'rolls': detail, 'id': piece['id'],
                       'out_of_range': any(d['out_of_range'] for d in detail)})
        if appliques:
            overrides[piece['id']] = appliques
        for d in detail:
            if not d['applied']:
                refuses.append({'name': piece['name'], 'stat': d['name'],
                                'value': d['value']})
    return pieces, overrides, refuses


def _nom_de_leur_code(structure, code):
    """Leur code de caracteristique, dans les mots du lecteur.

    Un build que nous avons exporte revient avec sa forgemagie dans leur
    `fmGlobal`, en un total par caracteristique: la rendre telle quelle
    donnait <<cc 6>>, qui ne veut rien dire pour qui n'a pas lu leur code.
    Un code que nous ne connaissons pas reste tel quel plutot que d'etre
    tu.
    """
    from chardata.dofusbook_import import FM_CODES
    stat = structure.get_stat_by_key(FM_CODES.get(code) or '')
    if stat is None:
        return code
    return localized_stat_name(stat.name, structure.game_version)


def _forgemagie_laissee(build, structure, langue):
    """Ce que le lien porte en forgemagie et qu'aucune piece d'ici ne peut
    recevoir, en toutes lettres pour l'apercu: les lignes au niveau du
    build (`fmGlobal`, jamais vu rempli sur un vrai build, rendu tel quel
    dans leurs codes) et les lignes d'une piece dont le code n'a pas de
    caracteristique chez nous (`deg` sur un Dofus Tachete Retro, mesure le
    11 septembre 2026). La forgemagie de l'arme est un drapeau a part: c'est
    un changement d'element, que des overrides par caracteristique ne
    savent pas ecrire.
    """
    global_ = []
    for code, valeur in sorted((build.get('fm_global') or {}).items()):
        if not isinstance(valeur, int) or isinstance(valeur, bool):
            continue
        global_.append('%d %s' % (valeur, _nom_de_leur_code(structure, code)))
    sans_cle = []
    for item_id, code, valeur in build.get('fm_unmapped') or []:
        item = structure.get_item_by_id(item_id)
        nom = ((structure.get_item_name_in_language(item, langue) or item.name)
               if item is not None else str(item_id))
        sans_cle.append('%s: %s %d' % (nom, code, valeur))
    return global_, sans_cle


def text_build(request):
    """GET montre la zone, POST lit ce qu'elle contient, confirmer cree."""
    texte = (request.POST.get('text') or '')[:MAX_CARACTERES]
    version_page = _version(request)

    if request.method != 'POST' or not texte.strip():
        return _reponse(request, {
            'text': '',
            'version_label': get_game_version(version_page).label,
            'login_problem': is_anon_cant_create(request),
        })

    # 1. Les liens. Le premier lisible est lu comme un build; il decide de la
    # version, parce qu'un hote ne ment pas sur la version alors qu'un nom
    # d'objet peut exister dans plusieurs (voir plus bas). Les autres liens
    # lisibles sont rendus dans la liste des lignes laissees.
    reste, lisibles, illisibles = separe_les_liens(texte)
    build = None
    if lisibles:
        try:
            build = read_build(lisibles[0])
        except ImportError_ as erreur:
            raisons = _raisons_du_lien()
            return _reponse(request, {
                'text': texte,
                'version_label': get_game_version(version_page).label,
                'error': raisons.get(erreur.reason, raisons['unreadable']),
                'login_problem': is_anon_cant_create(request),
            })
    version = build['game_version'] if build else version_page

    # 2. Le texte, dans la version du lien s'il y en a un, sinon celle de la
    # page. Un texte qui dit lui-meme venir d'une autre version n'est pas
    # cherche dans le mauvais catalogue.
    #
    # Mesure du 10 septembre 2026: 1594 des 6269 noms Retro existent aussi en
    # Dofus 3, et 482 d'entre eux y designent un objet d'un AUTRE NIVEAU
    # (<<Amulet of the Valiant Heart>> passe de 41 a 200). Depuis Touch, 818
    # sur 2618. Le lecteur aurait recu un build plausible qui n'est pas le
    # sien, ce qui est le pire des resultats possibles.
    lu = read_items(reste, version, get_supported_language())
    annoncee = lu['stated_version']
    if annoncee and annoncee != version:
        return _reponse(request, {
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

    # 3. Ce que les deux entrees ont donne, dans l'ordre: le lien d'abord,
    # puis le texte, sans doublon.
    ids_du_lien = list(build['item_ids']) if build else []
    item_ids = list(ids_du_lien)
    for item_id in lu['item_ids']:
        if item_id not in item_ids:
            item_ids.append(item_id)
    laissees = list(lu['ignored']) + lisibles[1:] + illisibles

    if not item_ids:
        # Un lecteur qui n'a colle qu'un lien d'un site que le serveur ne
        # lit pas doit l'entendre en ces mots, pas en <<aucun objet>>.
        if illisibles and not lu['ignored']:
            erreur = _raisons_du_lien()['not_a_link']
        else:
            erreur = _('No item in that text matched our catalogue for this '
                       'version. Check the game version at the top, and that '
                       'the item names are on their own lines.')
        return _reponse(request, {
            'text': texte,
            'version_label': get_game_version(version).label,
            'error': erreur,
            'ignored': laissees[:12],
            'unreadable_links': illisibles[:12],
            'login_problem': is_anon_cant_create(request),
        })

    # La classe et le niveau viennent du texte QUAND il les porte, ce qui est
    # le cas d'un build exporte par le site: son entete dit <<Mon Cra - Cra
    # lvl 200>>. Un lien porte parfois le niveau. Ce sont des sources de
    # premiere main, donc les pre-remplir n'est pas les deviner. Le choix
    # reste affiche et modifiable.
    char_class = request.POST.get('char_class') or ''
    if not char_class and lu['char_class'] in CHARACTER_CLASSES:
        char_class = lu['char_class']
    # Un lien qui nomme la classe dans une numerotation que l'on sait
    # lire (DofusCreator, pas DofusBook) la pre-remplit; le choix reste.
    if not char_class and build and build.get('char_class') in CHARACTER_CLASSES:
        char_class = build['char_class']
    niveau_lu = lu['char_level'] or (build['level'] if build else None)
    niveau = safe_int(request.POST.get('level'), niveau_lu or NIVEAU_PAR_DEFAUT)

    # Les caracteristiques: celles du lien d'abord (leur stuffCarac porte les
    # points investis et les parchotages), celles du texte par-dessus quand
    # il en porte (une ligne Points: ou Scrolls: collee est un choix
    # explicite du lecteur). Thibaud, 11 septembre 2026: l'import d'un lien
    # jetait ses stats de base et ses parchotages.
    points = dict(build.get('base_points') or {}) if build else {}
    points.update(lu['base_points'])
    parchos = dict(build.get('base_scrolled') or {}) if build else {}
    parchos.update(lu['base_scrolled'])
    caracteristiques = dict(lu, base_points=points, base_scrolled=parchos)

    lien = None
    pieces_du_lien, overrides_du_lien, refuses_du_lien = [], {}, []
    if build:
        structure = get_structure(version)
        langue = get_supported_language()
        pieces_du_lien, overrides_du_lien, refuses_du_lien = _pieces_du_lien(
            build, structure, version)
        # Les pieces dont la forgemagie du lien reste derriere, nommees
        # dans la langue du lecteur: un build qui arrive sans ses exos
        # doit le dire avant, pas le laisser decouvrir.
        sans_fm = []
        for item_id in build.get('fm_not_carried') or []:
            item = structure.get_item_by_id(item_id)
            if item is not None:
                sans_fm.append(structure.get_item_name_in_language(item, langue)
                               or item.name)
        fm_global, fm_sans_cle = _forgemagie_laissee(build, structure, langue)
        lien = {'name': build['name'],
                'version_label': get_game_version(version).label,
                'level': build['level'],
                'missing': build['missing'],
                'fm_not_carried': sans_fm,
                'fm_global': fm_global,
                'fm_weapon': bool(build.get('fm_weapon')),
                'fm_unmapped': fm_sans_cle,
                'version_differs': version != version_page}

    # Les jets, meme regle que les caracteristiques: ceux du lien d'abord,
    # ceux du texte par-dessus pour la meme piece, puisqu'une ligne collee
    # est un choix explicite du lecteur.
    overrides = {}
    for source in (overrides_du_lien, lu['overrides']):
        for item_id, par_piece in source.items():
            overrides.setdefault(item_id, {}).update(par_piece)
    refuses = refuses_du_lien + lu['refused_rolls']

    if not request.POST.get('confirm') or char_class not in CHARACTER_CLASSES:
        return _reponse(request, {
            'text': texte,
            'confirm': True,
            'version_label': get_game_version(version).label,
            'link': lien,
            'matched': pieces_du_lien + lu['matched'],
            'ignored': laissees[:12],
            'ignored_total': len(laissees),
            'unreadable_links': illisibles[:12],
            'truncated': lu['truncated'],
            'max_lines': MAX_LIGNES,
            'refused_rolls': refuses[:12],
            'level': niveau,
            'char_class': char_class,
            'base_points': _caracteristiques_pour_apercu(caracteristiques),
            'classes': _classes_for(version),
            'login_problem': is_anon_cant_create(request),
        })

    nom = (build['name'] if build and build['name'] else _('Imported build'))
    char = create_build(request, char_class, niveau, set(), version, name=nom)
    _ecrit_les_caracteristiques(char, points, parchos)
    # `origin` distingue dans la ligne stockee un build venu d'un lien d'un
    # build colle en texte; ni l'un ni l'autre n'est <<generated>>, donc la
    # page ne dira jamais que le solveur a produit ce qu'il n'a pas vu.
    _place_items(char, item_ids,
                 origin='dofusbook' if build else 'pasted_text')
    # Les jets APRES la pose des objets: `_place_items` appelle set_minimal_
    # solution, qui ecrit sur le char, et ecrire les overrides avant se
    # ferait ecraser. Un seul save pour tout le lot, la ou
    # set_item_stat_override en fait un par caracteristique.
    if overrides:
        set_stat_overrides(char, overrides)
    logger.info('imported %d items (%d from a link) and %d rolled stats '
                'into char %s', len(item_ids), len(ids_du_lien),
                sum(len(v) for v in overrides.values()), char.id)
    return HttpResponseRedirect(_solution_path(char))
