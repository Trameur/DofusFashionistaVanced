# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One door for every build site the server knows how to read.

The import page hands each pasted line here. A reader is a pair
(recognise, read): the first whose `recognise` says yes reads the link, and
the list of hosts is what the page prints under its field, so adding a site
is adding a line here and nothing on the page.

What is NOT here, and why (2026-09-11):

- DofusDB: readable in one GET (api.dofusdb.fr/stuffs/<id>, Ankama ids,
  base stats, scrolls, class), and the reason it is still not read changed
  on 2026-09-11. The old one was the advert clause of their licence, and it
  no longer applies: the site carries no adverts and will carry none. Their
  licence (LPNC-IA 1.0, printed in every response's X-License header and
  served in full at the API root, read again that day) has two other
  conditions that do:

  - 3.2 asks that any derived Project be distributed "sous les mêmes termes
    que la présente licence ou sous une licence compatible". This site is
    LGPL, which grants commercial use; a licence that forbids it is not
    compatible with that, and relicensing the site is not a reader.
  - 4.2 forbids integrating the API "dans un pipeline automatisé piloté par
    l'IA sans intervention humaine significative", and excludes any Project
    whose code or logic was produced in majority by AI tools. The work on
    this repository runs as an autonomous loop, so writing this reader here
    would breach that clause in the act of writing it.

  Both are questions for their author, not code to write.
- DofusRoom: item ids are theirs, not Ankama's; the only join is name plus
  level plus icon id, through POST endpoints, with no published terms.
"""

from chardata import build_sites, dofusbook_import, dofuscreator_import


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


#: (site switch, recognise, read, hosts the page names). A reader whose site
#: is not enabled (build_sites.py) is not there at all: its links read as
#: those of any site the server does not know.
READERS = (
    (build_sites.DOFUSBOOK, _dofusbook_recognises, dofusbook_import.read_build,
     ('dofusbook.net',)),
    (build_sites.DOFUS_STUFFER, _dofus_stuffer_recognises,
     dofusbook_import.read_build, ('dofus-stuffer.is-great.net',)),
    (build_sites.DOFUSCREATOR,
     lambda url: dofuscreator_import.parse_link(url) is not None,
     dofuscreator_import.read_build, ('dofuscreator.com',)),
)


def _readers():
    return [(reconnait, lit, hotes) for site, reconnait, lit, hotes in READERS
            if build_sites.enabled(site)]


def recognises(url):
    """Whether some reader takes this link (a short link counts: its reader
    is the one that explains why it is refused)."""
    return any(reconnait(url) for reconnait, _lit, _hotes in _readers())


def read(url, opener=None):
    """The build behind the link, from the first reader that takes it.
    Raises dofusbook_import.ImportError_ with a reason key, or `not_a_link`
    when no reader takes it."""
    for reconnait, lit, _hotes in _readers():
        if reconnait(url):
            return lit(url, opener=opener)
    raise dofusbook_import.ImportError_('not_a_link')


def readable_sites():
    """The hosts the page names, in reader order."""
    return [hote for _r, _l, hotes in _readers() for hote in hotes]
