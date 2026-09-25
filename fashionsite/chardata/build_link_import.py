# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One door for every build site the server can read.

Not read: DofusDB (its API licence needs its author's OK), DofusRoom (its own item ids).
"""

import urllib.parse

from chardata import build_sites, dofusbook_export, dofusbook_import, dofuscreator_import


def _dofusbook_recognises(url):
    if dofusbook_import._host_and_path(url)[0] in dofusbook_import.STUFFER_HOSTS:
        return False
    return (dofusbook_import.parse_stuffer_link(url) is not None
            or dofusbook_import.is_stuffer_path(url)
            or dofusbook_import.parse_link(url) is not None
            or dofusbook_import.is_short_link(url))


def _dofus_stuffer_recognises(url):
    return (dofusbook_import._host_and_path(url)[0] in dofusbook_import.STUFFER_HOSTS
            and dofusbook_import.parse_stuffer_link(url) is not None)


#: (site switch, recognise, read, hosts; a paste is counted under the first)
READERS = (
    (build_sites.DOFUSBOOK, _dofusbook_recognises, dofusbook_import.read_build,
     ('dofusbook.net',)),
    (build_sites.DOFUS_STUFFER, _dofus_stuffer_recognises,
     dofusbook_import.read_build, ('dofus-stuffer.is-great.net',)),
    (build_sites.DOFUSCREATOR,
     lambda url: dofuscreator_import.parse_link(url) is not None,
     dofuscreator_import.read_build, ('dofuscreator.com',)),
)

#: site switch: (name, {game version its links are read as: home page})
PARTNERS = {
    build_sites.DOFUSBOOK: ('DofusBook', {
        version: 'https://%s/' % host
        for version, host in dofusbook_export.HOSTS.items()}),
    # The address their own share links give
    build_sites.DOFUS_STUFFER: ('Dofus-Stuffer', dict.fromkeys(
        set(dofusbook_import.STUFFER_HOSTS.values()),
        'http://www.dofus-stuffer.is-great.net/')),
    build_sites.DOFUSCREATOR: ('DofusCreator', dict.fromkeys(
        set(dofuscreator_import.HOSTS.values()), 'https://dofuscreator.com/')),
}


def _readers():
    return [(reconnait, lit, hotes) for site, reconnait, lit, hotes in READERS
            if build_sites.enabled(site)]


def recognises(url):
    """Whether an enabled reader takes this link (short links count)."""
    return any(reconnait(url) for reconnait, _lit, _hotes in _readers())


def site_of(url):
    """The host a paste of this link is counted under, or None when no enabled reader takes it."""
    for reconnait, _lit, hotes in _readers():
        if reconnait(url):
            return hotes[0]
    return None


def read(url, opener=None):
    """The build behind the link; raises ImportError_, 'not_a_link' when no reader takes it."""
    for reconnait, lit, _hotes in _readers():
        if reconnait(url):
            return lit(url, opener=opener)
    raise dofusbook_import.ImportError_('not_a_link')


def readable_sites():
    """The hosts of the enabled readers, in reader order."""
    return [hote for _r, _l, hotes in _readers() for hote in hotes]


def partner_sites(game_version):
    """[{name, url, host}] per enabled site whose links read as that version, in reader order."""
    partners = []
    for site, _recognise, _read, _hosts in READERS:
        name, homes = PARTNERS[site]
        url = homes.get(game_version)
        if url is None or not build_sites.enabled(site):
            continue
        host = urllib.parse.urlsplit(url).hostname
        partners.append({'name': name, 'url': url,
                         'host': host[4:] if host.startswith('www.') else host})
    return partners
