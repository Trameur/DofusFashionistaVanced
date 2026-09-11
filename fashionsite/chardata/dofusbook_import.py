# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Read a public DofusBook build from its link.

The endpoint is undocumented and internal to their single page app, so
everything here is what it was measured to do on 2026-09-09, not what it
promises. It answers 403 without a Referer on their own domain and 200 with
one, so the call cannot be made from the reader's browser and goes through us.

The one thing that shapes the whole design: **a build id is not unique across
their hosts**. Measured, id 2558915 is a 404 on www, an 8 item level 21 build
called "Bas Level" on retro, and a 16 item level 170 build called "Feu eau" on
touch. Nothing in the payload says which game it belongs to, so the host is
taken from the link the player pasted and is never guessed.

The catalogue check underneath is a second net and NOT a way to work the
version out. Measured: that Retro build resolves 8 of 8 items under retro,
dofus3 AND touch, because low level items carry the same Ankama id in every
version. The check only catches the other direction, a modern build read as an
old one, where 13 of 16 items simply do not exist yet.

That asymmetry is why d-bk.net short links are refused rather than followed.
Their redirect target could not be verified here, and if a short link to a
Retro build lands on www, the version would be wrong and every item would
still resolve: the import would be silently, plausibly wrong. Asking for the
full link costs the player one click.
"""

import json
import re
import urllib.error
import urllib.request

#: Their host to our game version, and the only thing that decides it.
HOSTS = {
    'www.dofusbook.net': 'dofus3',
    'dofusbook.net': 'dofus3',
    'retro.dofusbook.net': 'retro',
    'touch.dofusbook.net': 'touch',
}

SHORT_HOSTS = ('d-bk.net', 'www.d-bk.net')

#: Their site refuses a request that does not look like it came from their own
#: pages. Measured: 403 with only a browser User-Agent, 200 once a Referer on
#: the same host is added.
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

TIMEOUT = 20

#: Under this share of items resolving in the catalogue we refuse. It is a
#: floor, not a version detector: measured, a Retro build resolves fully under
#: all three versions, while a Dofus 3 build read as Retro resolves 3 of 16.
MIN_RESOLVED = 0.6

_ID = re.compile(r'/(\d{3,})')


class ImportError_(Exception):
    """Anything that stops us handing back a build, with a reason key the
    caller turns into a translated sentence."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _host_and_path(url):
    url = (url or '').strip()
    if not url:
        return None, ''
    if '//' not in url:
        url = 'https://' + url
    reste = url.split('//', 1)[1]
    host, _, chemin = reste.partition('/')
    return host.split(':')[0].lower(), '/' + chemin


def parse_link(url):
    """(host, build id) for a DofusBook link, or None.

    Deliberately permissive about the path: their routes carry a language, a
    slug and sometimes a query, and pinning the exact shape would break the
    day they reorganise it. The first run of at least three digits in the path
    is the build id.
    """
    host, chemin = _host_and_path(url)
    if host not in HOSTS:
        return None
    trouve = _ID.search(chemin)
    if not trouve:
        return None
    return host, trouve.group(1)


def is_short_link(url):
    host, _chemin = _host_and_path(url)
    return host in SHORT_HOSTS


def fetch_build(host, build_id, opener=None):
    """Their payload for one public build.

    The path segment between stuffs and public is ignored by their own API, so
    anything goes there; we send a constant rather than invent a plausible
    one.
    """
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
    """([our item ids], [names we could not place]).

    Their `official` field is the Ankama id, which is what our own catalogue
    is keyed on, so no name matching is involved and nothing is approximate.
    Measured on a real build: 16 of 16 items resolved this way.
    """
    from fashionistapulp.structure import get_structure
    structure = get_structure(game_version)
    trouves = []
    manquants = []
    for entree in payload.get('items') or []:
        ankama = entree.get('official')
        item = (structure.items_dict_ankama.get(ankama)
                if ankama is not None else None)
        if item is None:
            manquants.append(entree.get('name') or str(ankama))
        else:
            trouves.append(item.id)
    return trouves, manquants


#: Their six base characteristics, in the order of our BASE_STATS
#: (['vit', 'wis', 'str', 'int', 'cha', 'agi']): their `st` is
#: ["vi", "sa", "fo", "in", "ch", "ag"], read off their bundle for the
#: export and confirmed on the payload of build 7894460 on 2026-09-11:
#: `stuff.stuffCarac` is {base_vi: 395, ..., scroll_vi: 100, ...}.
THEIR_BASE_KEYS = ('vi', 'sa', 'fo', 'in', 'ch', 'ag')


def base_stats(stuff):
    """({our stat name: points spent}, {our stat name: scrolled}) from
    `stuff.stuffCarac`, empty when the payload has none.

    `base_*` is what the player invested and `scroll_*` the scroll, kept
    apart because the site keeps them apart (CharBaseStats.scrolled_value
    and total_value = both). A value that is not a whole number is dropped
    rather than guessed. Thibaud, 2026-09-11: "l'import de dofusbook ne
    prend pas bien en compte mes stats (base et parcho)"; measured, the
    reader threw this block away.
    """
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


def read_build(url, opener=None):
    """Everything the caller needs to offer the player a build, or raise.

    The version comes from the host, and only from the host. The catalogue
    check below is a floor against nonsense, not a second opinion on the
    version: it cannot tell retro from dofus3 for a low level build, since
    those items exist in both under the same id.
    """
    if is_short_link(url):
        raise ImportError_('short_link')
    analyse = parse_link(url)
    if analyse is None:
        raise ImportError_('not_a_link')
    host, build_id = analyse
    game_version = HOSTS[host]
    payload = fetch_build(host, build_id, opener=opener)

    items, manquants = map_items(payload, game_version)
    total = len(items) + len(manquants)
    if not total:
        # An unsupported x-lang answers 200 with an empty item list, so an
        # empty build is a suspicious answer rather than an empty wardrobe.
        raise ImportError_('empty')
    if len(items) / float(total) < MIN_RESOLVED:
        raise ImportError_('wrong_version')

    stuff = payload.get('stuff') or {}
    niveau = stuff.get('character_level')
    points, parchos = base_stats(stuff)
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
        # Their character_class is their own numbering and NOT Ankama's: build
        # 7894460 is called "Zobal M 200" and carries character_class 12,
        # where 12 is Pandawa in Ankama's order. Nothing in the payload names
        # the class, so it is left for the player to pick rather than guessed.
        'class_is_unknown': True,
    }
