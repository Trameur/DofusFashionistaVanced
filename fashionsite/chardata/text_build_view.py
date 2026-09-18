# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Import page: a build from pasted names, tooltips, build links or screenshots."""

import logging
import re

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata import build_link_import
from chardata.dofusbook_import import ImportError_, MAX_POINTS
from chardata.dofusbook_view import (_classes_for, _place_items,
                                     _preview, _solution_path)
from chardata.lock_forbid import set_stat_overrides
from chardata.models import CharBaseStats
from chardata.options import get_options, set_options
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

MAX_CARACTERES = 40000

NIVEAU_PAR_DEFAUT = 200

# A line that is only an address; a link inside a sentence is text
_LIGNE_LIEN = re.compile(r'^(?:https?://\S+|www\.\S+)$', re.I)

# Tests replace this to stay off the network
read_build = build_link_import.read


def _version(request):
    return getattr(request, 'game_version', None) or get_current_game_version()


def _url_pour_version(cle):
    """This page under another version's prefix; dofus3 has none."""
    prefixe = '' if cle == 'dofus3' else '/' + cle
    return '%s/import/text/' % prefixe


def _raisons_du_lien():
    """One message per reason a link can be refused, naming no site."""
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
        'bad_link': _('That link is incomplete or damaged. Copy the full '
                      'address again.'),
    }


def separe_les_liens(texte):
    """(text without its link lines, [links we read], [links we do not read])."""
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
    """[{name, points, scrolled}] for the preview."""
    lignes = []
    for nom, _cle in STATS_NAMES:
        points = lu['base_points'].get(nom, 0)
        parchos = lu['base_scrolled'].get(nom, 0)
        if points or parchos:
            lignes.append({'name': localized_stat_name(nom),
                           'points': points, 'scrolled': parchos})
    return lignes


def _ecrit_les_caracteristiques(char, points, parchos, complet=False):
    """Write spent points and scrolls; complet means the source states all six."""
    if not points and not parchos and not complet:
        return
    plafond = max_scroll_for_version(char.game_version, char.level)
    for nom, _cle in STATS_NAMES:
        depenses = min(max(0, points.get(nom, 0)), MAX_POINTS)
        parcho = min(max(0, parchos.get(nom, 0)), plafond)
        if not depenses and not parcho and not complet:
            continue
        # create_build already made one row per stat
        ligne, _neuve = CharBaseStats.objects.get_or_create(
            char=char, stat=nom,
            defaults={'total_value': 0, 'scrolled_value': 0})
        # total_value holds both, scrolled_value the scroll part
        ligne.total_value = depenses + parcho
        ligne.scrolled_value = parcho
        ligne.save()


def _reponse(request, params):
    """The page, with what every state of it shares."""
    params.setdefault('ocr_languages',
                      language_options(get_supported_language()))
    params.setdefault('link_sites', ', '.join(build_link_import.readable_sites()))
    return set_response(request, 'chardata/text_build.html', params)


def _pieces_du_lien(build, structure, version):
    """([pieces], {item id: {stat id: value}}, [refused rolls]) for a link's items."""
    jets_par_piece = build.get('rolls') or {}
    pieces, overrides, refuses = [], {}, []
    for piece in _preview(build):
        item = structure.get_item_by_id(piece['id'])
        # A link line on a stat the piece lacks is an exo, not an OCR misread
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
    """Their stat code in the reader's language, or the code itself when unknown."""
    from chardata.dofusbook_import import FM_CODES
    stat = structure.get_stat_by_key(FM_CODES.get(code) or '')
    if stat is None:
        return code
    return localized_stat_name(stat.name, structure.game_version)


# Exo options a link sets, with the word the page shows
_EXOS = (('ap_exo', 'AP'), ('mp_exo', 'MP'), ('range_exo', 'Range'))


def _exos_du_lien(build):
    """Build-wide exo options the link sets, in the reader's language."""
    portees = build.get('exo_options') or {}
    return [_(mot) for option, mot in _EXOS if portees.get(option)]


def _pose_les_exos(char, build):
    """Set the link's exo options; call before _place_items, which reads them."""
    portees = build.get('exo_options')
    if portees is None:
        return
    options = get_options(char)
    # Off included: a new level 200 build starts with AP and MP exo on
    for option, _mot in _EXOS:
        options[option] = bool(portees.get(option))
    set_options(char, options)


def _forgemagie_laissee(build, structure, langue):
    """Link forgemagie no piece here can take: (build-wide lines, lines with no key)."""
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
    """GET shows the form, POST reads it, confirm creates the build."""
    texte = (request.POST.get('text') or '')[:MAX_CARACTERES]
    version_page = _version(request)

    if request.method != 'POST' or not texte.strip():
        return _reponse(request, {
            'text': '',
            'version_label': get_game_version(version_page).label,
            'login_problem': is_anon_cant_create(request),
        })

    # 1. Links: the first readable one is read and decides the version
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

    # 2. The text, in the link's version or else the page's
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

    # 3. Link items first, then text items, no duplicates
    ids_du_lien = list(build['item_ids']) if build else []
    item_ids = list(ids_du_lien)
    for item_id in lu['item_ids']:
        if item_id not in item_ids:
            item_ids.append(item_id)
    laissees = list(lu['ignored']) + lisibles[1:] + illisibles

    if not item_ids:
        # Only an unreadable link pasted: say so, not "no item"
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

    # Class and level from the text when it has them (our export's header)
    char_class = request.POST.get('char_class') or ''
    if not char_class and lu['char_class'] in CHARACTER_CLASSES:
        char_class = lu['char_class']
    # DofusCreator links carry a class we can read, DofusBook links do not
    if not char_class and build and build.get('char_class') in CHARACTER_CLASSES:
        char_class = build['char_class']
    niveau_lu = lu['char_level'] or (build['level'] if build else None)
    niveau = safe_int(request.POST.get('level'), niveau_lu or NIVEAU_PAR_DEFAUT)

    # Base stats: the link's first, the text's on top
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
        # Pieces whose link forgemagie we do not carry
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
                'exos': _exos_du_lien(build),
                'version_differs': version != version_page}

    # Rolls: the link's first, the text's on top for the same piece
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
    _ecrit_les_caracteristiques(
        char, points, parchos,
        complet=bool(build and build.get('base_stats_complete')))
    if build:
        _pose_les_exos(char, build)
    # Never 'generated': the solver did not produce these items
    _place_items(char, item_ids,
                 origin='dofusbook' if build else 'pasted_text')
    # After _place_items: its set_minimal_solution would overwrite the overrides
    if overrides:
        set_stat_overrides(char, overrides)
    logger.info('imported %d items (%d from a link) and %d rolled stats '
                'into char %s', len(item_ids), len(ids_du_lien),
                sum(len(v) for v in overrides.values()), char.id)
    return HttpResponseRedirect(_solution_path(char))
