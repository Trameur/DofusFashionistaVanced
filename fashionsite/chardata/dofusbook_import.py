# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Read a public DofusBook build from its link."""

import json
import re
import urllib.error
import urllib.request

# Build ids repeat across hosts: the host alone decides the version
HOSTS = {
    'www.dofusbook.net': 'dofus3',
    'dofusbook.net': 'dofus3',
    'retro.dofusbook.net': 'retro',
    'touch.dofusbook.net': 'touch',
}

# Refused: the redirect hides the host, so the version
SHORT_HOSTS = ('d-bk.net', 'www.d-bk.net')

# Dofus-Stuffer fansite: DofusBook stuffer link format, Dofus 3 builds
STUFFER_HOSTS = {
    'dofus-stuffer.is-great.net': 'dofus3',
    'www.dofus-stuffer.is-great.net': 'dofus3',
}

# They answer 403 without a Referer on their own host
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

TIMEOUT = 20

# Floor, not a version check: low level items share ids across versions
MIN_RESOLVED = 0.6

_ID = re.compile(r'/(\d{3,})')


class ImportError_(Exception):
    """Stops an import; reason is a key the caller translates."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# At the start only: a stuffer link's base64 can contain '//'
_SCHEME = re.compile(r'^[a-z][a-z0-9+.-]*://', re.I)

MAX_POINTS = 9999


def _host_and_path(url):
    url = (url or '').strip()
    if not url:
        return None, ''
    if not _SCHEME.match(url):
        url = 'https://' + url
    reste = url.split('//', 1)[1]
    # Host ends at the first '/', '?' or '#': "site.net?stuff=..." has no path
    fin = min([at for at in (reste.find(sep) for sep in '/?#') if at != -1]
              or [len(reste)])
    host, chemin = reste[:fin], reste[fin:]
    if not chemin.startswith('/'):
        chemin = '/' + chemin
    return host.split(':')[0].lower(), chemin


def parse_link(url):
    """(host, build id) for a DofusBook link, or None."""
    host, chemin = _host_and_path(url)
    if host not in HOSTS:
        return None
    # Path only: the query can hold digits, a stuffer link's base64 among them
    trouve = _ID.search(chemin.partition('?')[0].partition('#')[0])
    if not trouve:
        return None
    return host, trouve.group(1)


def is_short_link(url):
    host, _chemin = _host_and_path(url)
    return host in SHORT_HOSTS


def parse_stuffer_link(url):
    """(host, stuff parameter) for a stuffer link, or None."""
    import urllib.parse
    host, chemin = _host_and_path(url)
    if host not in HOSTS and host not in STUFFER_HOSTS:
        return None
    requete = chemin.partition('?')[2].partition('#')[0]
    valeurs = urllib.parse.parse_qs(requete).get('stuff')
    if not valeurs or not valeurs[0].strip():
        return None
    return host, valeurs[0]


def is_stuffer_path(url):
    """Whether the link points at their stuffer page, even with a damaged parameter."""
    host, chemin = _host_and_path(url)
    return (host in HOSTS
            and '/dofus-stuffer/' in chemin.partition('?')[0].partition('#')[0])


def fetch_build(host, build_id, opener=None):
    """Their payload for one public build."""
    # Their API ignores the segment between stuffs and public
    url = 'https://%s/api/stuffs/x/public/%s' % (host, build_id)
    requete = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Referer': 'https://%s/' % host,
        'Accept': 'application/json',
    })
    ouvreur = opener or urllib.request.urlopen
    try:
        with ouvreur(requete, timeout=TIMEOUT) as reponse:
            charge = json.load(reponse)
    except urllib.error.HTTPError as erreur:
        raise ImportError_('not_found' if erreur.code == 404 else 'refused')
    except Exception:
        raise ImportError_('unreachable')
    if not isinstance(charge, dict) or 'items' not in charge:
        raise ImportError_('unreadable')
    return charge


def map_items(payload, game_version):
    """([our item ids], [names we could not place])."""
    from fashionistapulp.structure import get_structure
    structure = get_structure(game_version)
    trouves = []
    manquants = []
    for entree in payload.get('items') or []:
        # `official` is the Ankama id
        ankama = entree.get('official')
        item = (structure.items_dict_ankama.get(ankama)
                if ankama is not None else None)
        if item is None:
            manquants.append(entree.get('name') or str(ankama))
        else:
            trouves.append(item.id)
    return trouves, manquants


# Their base stat codes, in our STATS_NAMES order (base_vi, scroll_vi...)
THEIR_BASE_KEYS = ('vi', 'sa', 'fo', 'in', 'ch', 'ag')


def base_stats(stuff):
    """({our stat: points spent}, {our stat: scrolled}) from stuff.stuffCarac."""
    from fashionistapulp.dofus_constants import STATS_NAMES
    carac = stuff.get('stuffCarac') or {}
    if not isinstance(carac, dict):
        return {}, {}
    points, parchos = {}, {}
    for (nom, _cle), leur in zip(STATS_NAMES, THEIR_BASE_KEYS):
        base = carac.get('base_' + leur)
        parcho = carac.get('scroll_' + leur)
        if isinstance(base, int) and not isinstance(base, bool) and base > 0:
            points[nom] = base
        if isinstance(parcho, int) and not isinstance(parcho, bool) and parcho > 0:
            parchos[nom] = parcho
    return points, parchos


# Their stat codes to our keys; a missing code has no key on our side
FM_CODES = {
    'vi': 'vit', 'sa': 'wis', 'fo': 'str', 'in': 'int', 'ch': 'cha', 'ag': 'agi',
    'pa': 'ap', 'pm': 'mp', 'po': 'range', 'ic': 'summon', 'pp': 'pp',
    'ii': 'init', 'so': 'heals', 'pd': 'pod', 'cc': 'ch', 'ec': 'cf',
    'ta': 'lock', 'fu': 'dodge', 'epa': 'apres', 'epm': 'mpres',
    'rpa': 'apred', 'rpm': 'mpred', 'rv': 'ref', 'pu': 'pow', 'dmg': 'dam',
    'dnf': 'neutdam', 'dtf': 'earthdam', 'dff': 'firedam', 'def': 'waterdam',
    'daf': 'airdam', 'dc': 'cridam', 'dp': 'pshdam', 'pi': 'trapdam',
    'pip': 'trapdamper', 'dm': 'permedam', 'dd': 'perrandam',
    'dw': 'perweadam', 'ds': 'perspedam',
    'rn': 'neutres', 'rt': 'earthres', 'rf': 'fireres', 're': 'waterres',
    'ra': 'airres', 'rnp': 'neutresper', 'rtp': 'earthresper',
    'rfp': 'fireresper', 'rep': 'waterresper', 'rap': 'airresper',
    'rc': 'crires', 'rp': 'pshres', 'rm': 'respermee', 'rd': 'resperran',
    'rw': 'resperwea',
}


def item_rolls(payload, game_version):
    """({item id: [{'key', 'value'}]}, [(item id, code, value) we have no key for])."""
    from fashionistapulp.structure import get_structure
    structure = get_structure(game_version)
    stuff = payload.get('stuff') or {}
    par_emplacement = stuff.get('stuffItem') or {}
    officiel_par_leur_id = {}
    for entree in payload.get('items') or []:
        try:
            officiel_par_leur_id[str(entree.get('id'))] = int(entree.get('official'))
        except (TypeError, ValueError):
            continue
    # fmItems: {their slot code: {stat code: final value of the line}}
    fm = payload.get('fmItems') or {}
    rolls, sans_cle = {}, []
    if not isinstance(fm, dict) or not isinstance(par_emplacement, dict):
        return rolls, sans_cle
    for slot, lignes in fm.items():
        if not isinstance(lignes, dict) or not lignes:
            continue
        leur_id = par_emplacement.get(slot)
        ankama = officiel_par_leur_id.get(str(leur_id)) if leur_id is not None else None
        item = structure.items_dict_ankama.get(ankama) if ankama is not None else None
        for code, valeur in lignes.items():
            if not isinstance(valeur, int) or isinstance(valeur, bool):
                continue
            if item is None:
                continue
            cle = FM_CODES.get(code)
            if cle is None or structure.get_stat_by_key(cle) is None:
                sans_cle.append((item.id, code, valeur))
                continue
            rolls.setdefault(item.id, []).append({'key': cle, 'value': valeur})
    return rolls, sans_cle


def read_build(url, opener=None):
    """Everything the caller needs to offer the player a build, or raise."""
    if is_short_link(url):
        raise ImportError_('short_link')
    stuffer = parse_stuffer_link(url)
    if stuffer is not None:
        return read_stuffer_link(*stuffer)
    if is_stuffer_path(url):
        # Stuffer link with its parameter lost in the copy
        raise ImportError_('bad_link')
    analyse = parse_link(url)
    if analyse is None:
        raise ImportError_('not_a_link')
    host, build_id = analyse
    game_version = HOSTS[host]
    payload = fetch_build(host, build_id, opener=opener)

    items, manquants = map_items(payload, game_version)
    total = len(items) + len(manquants)
    if not total:
        # An unsupported x-lang answers 200 with an empty item list
        raise ImportError_('empty')
    if len(items) / float(total) < MIN_RESOLVED:
        raise ImportError_('wrong_version')

    stuff = payload.get('stuff') or {}
    niveau = stuff.get('character_level')
    points, parchos = base_stats(stuff)
    rolls, sans_cle = item_rolls(payload, game_version)
    return {
        'game_version': game_version,
        'source_host': host,
        'build_id': build_id,
        'name': (stuff.get('name') or '').strip()[:50],
        'level': niveau if isinstance(niveau, int) and 1 <= niveau <= 200 else None,
        'item_ids': items,
        'missing': manquants,
        'base_points': points,
        'base_scrolled': parchos,
        'rolls': rolls,
        'fm_unmapped': sans_cle,
        # Build-wide lines and the weapon element string: no piece holds them
        'fm_global': dict((payload.get('fmGlobal') or {})
                          if isinstance(payload.get('fmGlobal'), dict) else {}),
        'fm_weapon': payload.get('fmWeapon') or None,
        # Their character_class is their own numbering, not Ankama's
        'class_is_unknown': True,
    }


def read_stuffer_link(host, stuff):
    """Same shape as `read_build`, from a link that carries the whole build."""
    from chardata import dofusbook_export
    from fashionistapulp.dofus_constants import STATS_NAMES
    from fashionistapulp.structure import get_structure
    game_version = HOSTS.get(host) or STUFFER_HOSTS[host]
    try:
        lu = dofusbook_export.read_payload(stuff)
    except ValueError:
        raise ImportError_('bad_link')
    if not all(0 <= points <= MAX_POINTS for points in lu['points']):
        raise ImportError_('bad_link')

    structure = get_structure(game_version)
    items, manquants = [], []
    for (_slot, codes), groupe in zip(dofusbook_export.GROUPS, lu['ids']):
        for ankama in groupe[:len(codes)]:
            item = structure.items_dict_ankama.get(ankama)
            if item is None:
                manquants.append(str(ankama))
            else:
                items.append(item.id)
    total = len(items) + len(manquants)
    if not total:
        raise ImportError_('empty')
    if len(items) / float(total) < MIN_RESOLVED:
        raise ImportError_('wrong_version')

    points, parchos = {}, {}
    for (nom, _cle), depense, parcho in zip(STATS_NAMES, lu['points'],
                                            lu['scrolls']):
        if depense > 0:
            points[nom] = depense
        if parcho > 0:
            parchos[nom] = parcho
    niveau = lu['level']
    # All three, off included: a new level 200 build starts with AP and MP exo on
    exos = {option: bool(lu['exos'] & bit) for option, bit in (
        ('ap_exo', dofusbook_export.EXO_AP), ('mp_exo', dofusbook_export.EXO_MP),
        ('range_exo', dofusbook_export.EXO_RANGE))}
    # Their forgemagie is one total per stat for the whole build
    forge = {dofusbook_export.VE[index]: valeur for index, valeur
             in dofusbook_export.global_forge(lu).items()}
    return {
        'game_version': game_version,
        'source_host': host,
        'build_id': None,
        'name': '',
        'level': niveau if 1 <= niveau <= 200 else None,
        'item_ids': items,
        'missing': manquants,
        'base_points': points,
        'base_scrolled': parchos,
        'rolls': {},
        'fm_unmapped': [],
        'fm_global': forge,
        'fm_weapon': None,
        'exo_options': exos,
        # Every scroll is stated, zeros included
        'base_stats_complete': True,
        'class_is_unknown': True,
    }
