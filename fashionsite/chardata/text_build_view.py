# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Import page: a build from pasted names, tooltips, build links or screenshots."""

import contextlib
import datetime
import hashlib
import logging
import re
import secrets
import urllib.parse

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import Error as DatabaseErrors, transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_post_parameters

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata import (build_link_import, dofusbook_import, dofuscreator_import,
                      fashionista_build)
from chardata.dofusbook_import import ImportError_, MAX_POINTS
from chardata.dofusbook_view import (_classes_for, _place_items,
                                     _preview, _solution_path)
from chardata.lock_forbid import set_stat_overrides
from chardata.middleware import looks_like_a_robot
from chardata.models import CharBaseStats, ImportSourceHit
from chardata.options import get_options, set_options
from chardata.presets import gear_elements
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

# A line that is only an address; a link inside a sentence is text.
_LIEN_AVEC_SCHEME = re.compile(r'^(?:https?://\S+|www\.\S+)$', re.I)

# A bare line's domain shape: a host, optionally followed by a path.
_FORME_HOTE_NU = re.compile(
    r'^(?P<hote>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,})'
    r'(?P<chemin>[/?#]\S*)?$', re.I)

# Every host a reader answers to, lowercase, short links included.
_HOTES_CONNUS = (set(dofusbook_import.HOSTS) | set(dofusbook_import.SHORT_HOSTS)
                 | set(dofusbook_import.STUFFER_HOSTS)
                 | set(dofuscreator_import.HOSTS))


def _ligne_est_un_lien(candidat):
    """A scheme, a host a reader knows, or any host followed by a path."""
    if _LIEN_AVEC_SCHEME.match(candidat):
        return True
    trouve = _FORME_HOTE_NU.match(candidat)
    if not trouve:
        return False
    if trouve.group('hote').lower() in _HOTES_CONNUS:
        return True
    chemin = trouve.group('chemin')
    return bool(chemin) and chemin.startswith('/')


# Tests replace this to stay off the network
read_build = build_link_import.read


def _version(request):
    return getattr(request, 'game_version', None) or get_current_game_version()


def _url_pour_version(cle):
    """This page under another version's prefix, with the reader's language prefix."""
    from django.urls import reverse, NoReverseMatch
    try:
        return reverse('text_build_import' if cle == 'dofus3'
                       else '%s:text_build_import' % cle)
    except NoReverseMatch:
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
        if _ligne_est_un_lien(candidat):
            if build_link_import.recognises(candidat):
                lisibles.append(candidat)
            else:
                illisibles.append(candidat)
        else:
            reste.append(ligne)
    return '\n'.join(reste), lisibles, illisibles


_DNS_MAX_LENGTH = 253

_DOMAIN = re.compile(r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+'
                     r'(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$')

_INTERNAL_TLDS = frozenset((
    'arpa', 'corp', 'example', 'home', 'internal', 'intranet', 'invalid',
    'lan', 'local', 'localdomain', 'localhost', 'private', 'test'))

# Second levels sold under a two-letter country code, as in bbc.co.uk
_SHORT_SECOND_LEVELS = frozenset((
    'ac', 'co', 'com', 'edu', 'gob', 'gov', 'ltd', 'mil', 'ne', 'net',
    'nom', 'or', 'org', 'plc', 'sch'))

UNKNOWN_SITES_PER_DAY = 200

ATTEMPT_SECONDS = 1800

TOKEN_SECONDS = 86400

_TOKEN_SALT = 'chardata.text_build_view.import_count'


def _host_of_link(link):
    """The link's lowercase ASCII host without www., or ''."""
    if not dofusbook_import._SCHEME.match(link):
        link = 'http://' + link
    try:
        host = (urllib.parse.urlsplit(link).hostname or '').rstrip('.')
        host = host.encode('idna').decode('ascii')
    except ValueError:
        return ''
    return host[4:] if host.startswith('www.') else host


def _site_name(link):
    """The site behind a link we cannot read, subdomains dropped, or '' when it has no public name."""
    host = _host_of_link(link)
    if len(host) > _DNS_MAX_LENGTH or not _DOMAIN.match(host):
        return ''
    if host in _HOTES_CONNUS:
        return host
    labels = host.split('.')
    if labels[-1] in _INTERNAL_TLDS:
        return ''
    garde = 3 if (len(labels) > 2 and len(labels[-1]) == 2
                  and labels[-2] in _SHORT_SECOND_LEVELS) else 2
    return '.'.join(labels[-garde:])


def _import_source(lisibles, illisibles, link_failed, from_screenshot):
    """(source, host) of one paste: its first readable link, else its first unknown site, else its text."""
    if lisibles:
        return ('link_failed' if link_failed else 'link',
                build_link_import.site_of(lisibles[0]) or '')
    if illisibles:
        return ('link_unknown',
                next((nom for nom in map(_site_name, illisibles) if nom), ''))
    return ('screenshot' if from_screenshot else 'text', '')


def _add_one(day, version, source, host, field):
    key = {'day': day, 'source': source, 'host': host, 'game_version': version}
    plus_one = {field: F(field) + 1}
    if ImportSourceHit.objects.filter(**key).update(**plus_one):
        return
    if (source in ('link_unknown', 'api') and host
            and ImportSourceHit.objects.filter(day=day, source=source).count()
            >= UNKNOWN_SITES_PER_DAY):
        key['host'] = ''
        if ImportSourceHit.objects.filter(**key).update(**plus_one):
            return
    row, created = ImportSourceHit.objects.get_or_create(defaults={field: 1}, **key)
    if not created:
        ImportSourceHit.objects.filter(pk=row.pk).update(**plus_one)


def _count_import(day, version, source, field):
    """Add one to `field`, attempts or imported, for (source, host); False when the database refused, never raised."""
    # A savepoint only inside a transaction: in autocommit a lost insert race frees its lock at once
    garde = (transaction.atomic() if transaction.get_connection().in_atomic_block
             else contextlib.nullcontext())
    try:
        with garde:
            _add_one(day, version, source[0], source[1], field)
    except DatabaseErrors:
        logger.warning('import source not counted', exc_info=True)
        return False
    return True


def _paste_key(request, page_version, texte):
    """Visitor, page and paste, hashed; only ever a cache key."""
    visiteur = (request.COOKIES.get(settings.CSRF_COOKIE_NAME)
                or request.session.session_key)
    if not visiteur:
        # A first visit has neither: the CSRF secret this page is about to set
        get_token(request)
        visiteur = request.META.get('CSRF_COOKIE') or ''
    lignes = '\n'.join(ligne.strip() for ligne in texte.splitlines() if ligne.strip())
    return hashlib.sha256('\n'.join((visiteur, page_version, lignes))
                          .encode('utf-8')).hexdigest()


def _count_attempt(request, page_version, texte, version, source):
    """Count the paste unless this visitor sent it lately; the token its confirm step carries, or ''."""
    cle = 'importhit:' + _paste_key(request, page_version, texte)
    today = timezone.localdate()
    trace = {'nonce': secrets.token_hex(8), 'day': today.isoformat()}
    if cache.add(cle, trace, ATTEMPT_SECONDS):
        if not _count_import(today, version, source, 'attempts'):
            cache.delete(cle)
            return ''
    else:
        trace = cache.get(cle)
        if not trace:
            return ''
    return signing.dumps({'n': trace['nonce'], 'd': trace['day'], 'v': version,
                          's': source[0], 'h': source[1]}, salt=_TOKEN_SALT)


def _count_confirmed(jeton):
    """One import for the preview that issued the token, on that preview's day."""
    try:
        lu = signing.loads(jeton, salt=_TOKEN_SALT, max_age=TOKEN_SECONDS)
        day = datetime.date.fromisoformat(lu['d'])
        nonce, version, source = lu['n'], lu['v'], (lu['s'], lu['h'])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return
    # The build came from the item names, not from that site
    if source[0] == 'link_unknown':
        return
    today = timezone.localdate()
    day = min(max(day, today - datetime.timedelta(days=1)), today)
    if cache.add('importdone:' + nonce, True, TOKEN_SECONDS):
        _count_import(day, version, source, 'imported')


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


def _reponse(request, params, formulaire=None):
    """The page, with what every state of it shares."""
    formulaire = request.POST if formulaire is None else formulaire
    params.setdefault('ocr_languages',
                      language_options(get_supported_language()))
    params.setdefault('partner_sites',
                      build_link_import.partner_sites(_version(request)))
    params.setdefault('used_screenshot', bool(params.get('text'))
                      and formulaire.get('used_screenshot') == '1')
    # Only a sent build posts elsewhere; its address carries the build
    if params.get('form_action'):
        params.setdefault('noindex', True)
        params.setdefault('canonical_path', params['form_action'])
        params.setdefault('hreflang_urls', {})
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
    return [_(mot) for option, mot in _EXOS if portees.get(option) is True]


def _pose_les_exos(char, build):
    """Set the link's exo options; call before _place_items, which reads them."""
    portees = build.get('exo_options')
    if portees is None:
        return
    options = get_options(char)
    # Off included: a new level 200 build starts with AP and MP exo on
    for option, _mot in _EXOS:
        valeur = portees.get(option)
        # 'gelano' wears Gelano (#1), whose MP is not an exo
        options[option] = valeur if valeur == 'gelano' else bool(valeur)
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


@sensitive_post_parameters('text')
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
    return _lis(request, texte, version_page, request.POST)


def sent_build(request, texte):
    """The preview of a build another site sent; its forms post to the import page, nothing is created here."""
    version_page = _version(request)
    return _lis(request, texte, version_page, {},
                action=_url_pour_version(version_page))


def _envoi_illisible():
    return _('The site that sent this build sent something we cannot read.')


def sent_build_refused(request, code):
    """The import page with the reason a sent build could not be decoded."""
    version_page = _version(request)
    if request.method != 'HEAD' and not looks_like_a_robot(request):
        _count_attempt(request, version_page, code, version_page, ('api', ''))
    return _reponse(request, {
        'text': '',
        'version_label': get_game_version(version_page).label,
        'error': _envoi_illisible(),
        'error_detail': fashionista_build.message(code),
        'form_action': _url_pour_version(version_page),
        'login_problem': is_anon_cant_create(request),
    }, formulaire={})


def _lis(request, texte, version_page, formulaire, action=None):
    """Read a paste; formulaire holds the confirm step's fields, empty for a preview only."""
    from_screenshot = formulaire.get('used_screenshot') == '1'
    counted = request.method != 'HEAD' and not looks_like_a_robot(request)

    # 1. A sent build, or the first readable link, decides the version
    envoye = fashionista_build.looks_sent(texte)
    build = None
    lien_erreur = None
    if envoye:
        reste, lisibles, illisibles = '', [], []
        try:
            build = fashionista_build.read_build(texte, get_supported_language())
        except ImportError_ as erreur:
            lien_erreur = erreur
    else:
        reste, lisibles, illisibles = separe_les_liens(texte)
        if lisibles:
            try:
                build = read_build(lisibles[0])
            except ImportError_ as erreur:
                lien_erreur = erreur

    # The confirm step posts the same text again and is not a new attempt
    jeton = ((formulaire.get('count_token') or '')
             if formulaire.get('confirm') else '')
    if counted and not formulaire.get('confirm'):
        if envoye:
            source = ('api', build['source_host'] if build
                      else getattr(lien_erreur, 'source', ''))
        else:
            source = _import_source(lisibles, illisibles,
                                    lien_erreur is not None, from_screenshot)
        jeton = _count_attempt(
            request, version_page, texte,
            build['game_version'] if build else version_page, source)

    if lien_erreur is not None:
        raisons = _raisons_du_lien()
        return _reponse(request, {
            'text': texte,
            'version_label': get_game_version(version_page).label,
            'error': (_envoi_illisible() if envoye
                      else raisons.get(lien_erreur.reason, raisons['unreadable'])),
            'error_detail': (fashionista_build.message(lien_erreur.reason)
                             if envoye else None),
            'form_action': action,
            'login_problem': is_anon_cant_create(request),
        }, formulaire)
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
            'form_action': action,
            'login_problem': is_anon_cant_create(request),
        }, formulaire)

    # 3. Link items first, then text items, no duplicates
    ids_du_lien = list(build['item_ids']) if build else []
    item_ids = list(ids_du_lien)
    for item_id in lu['item_ids']:
        if item_id not in item_ids:
            item_ids.append(item_id)
    laissees = list(lu['ignored']) + lisibles[1:]

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
            'form_action': action,
            'login_problem': is_anon_cant_create(request),
        }, formulaire)

    # Class and level from the text when it has them (our export's header)
    char_class = formulaire.get('char_class') or ''
    if not char_class and lu['char_class'] in CHARACTER_CLASSES:
        char_class = lu['char_class']
    # DofusCreator links carry a class we can read, DofusBook links do not
    if not char_class and build and build.get('char_class') in CHARACTER_CLASSES:
        char_class = build['char_class']
    niveau_lu = lu['char_level'] or (build['level'] if build else None)
    niveau = safe_int(formulaire.get('level'), niveau_lu or NIVEAU_PAR_DEFAUT)

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
                'version_differs': version != version_page,
                'sent': bool(build.get('sent')),
                'back_url': build.get('back_url'),
                'back_host': build.get('back_host'),
                'wrong_game': build.get('wrong_game') or [],
                'left_out': build.get('left_out') or [],
                'worn_twice': build.get('worn_twice') or []}

    # Rolls: the link's first, the text's on top for the same piece
    overrides = {}
    for source in (overrides_du_lien, lu['overrides']):
        for item_id, par_piece in source.items():
            overrides.setdefault(item_id, {}).update(par_piece)
    refuses = refuses_du_lien + lu['refused_rolls']
    class_ok = char_class in CHARACTER_CLASSES

    if not formulaire.get('confirm') or not class_ok:
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
            'class_error': (_('Choose a class before bringing this build in.')
                            if formulaire.get('confirm') and not class_ok
                            else None),
            'count_token': jeton,
            'form_action': action,
            'login_problem': is_anon_cant_create(request),
        }, formulaire)

    nom = (build['name'] if build and build['name'] else _('Imported build'))
    elements = gear_elements(get_structure(version), item_ids, char_class, niveau, version,
                             overrides)
    char = create_build(request, char_class, niveau, elements, version, name=nom)
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
    if counted:
        _count_confirmed(jeton)
    logger.info('imported %d items (%d from a link) and %d rolled stats '
                'into char %s', len(item_ids), len(ids_du_lien),
                sum(len(v) for v in overrides.values()), char.id)
    return HttpResponseRedirect(_solution_path(char))
