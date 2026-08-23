# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""The one place that knows which games this site serves.

Until now the list of versions was written out by hand wherever it was needed,
in dozens of places, none of them derived from any other. Two of those copies
answered an unknown version by quietly handing back Dofus 3's item database,
which is the worst possible answer: a page that looks right and is another
game's data.

Everything here is a fact about the version itself, not about how a page shows
it: the databases it reads, the url prefix it lives under, and whether it is
finished enough to be shown. Anything that is really a presentation choice
stays in the site.

Adding a game means adding an entry here and then giving it data. It does not
mean editing this file for every feature.
"""


class GameVersion:
    """One playable game, and where its data lives."""

    def __init__(self, key, label, db_file, dump_file, prefix=None,
                 seo_word='', experimental=False, dofus=True):
        self.key = key
        self.label = label
        self.db_file = db_file
        self.dump_file = dump_file
        # '' for the default version, which lives at the site root.
        self.prefix = key if prefix is None else prefix
        self.seo_word = seo_word
        # An experimental version is real everywhere the data pipeline is
        # concerned and invisible everywhere a reader could reach it.
        self.experimental = experimental
        # Wakfu is not a Dofus version: other stats, other slots, other rules.
        # Nothing that assumes Dofus should read a version with this false.
        self.dofus = dofus

    def __repr__(self):
        return '<GameVersion %s>' % self.key


GAME_VERSIONS = {
    version.key: version for version in (
        GameVersion('dofus3', 'Dofus 3', 'items.db', 'item_db_dumped.dump',
                    prefix='', seo_word=''),
        GameVersion('beta', 'Beta', 'items_beta.db',
                    'item_db_dumped_beta.dump', seo_word='Beta'),
        GameVersion('dofus2', 'Dofus 2', 'items_dofus2.db',
                    'item_db_dumped_dofus2.dump', seo_word='2'),
        GameVersion('touch', 'Touch', 'items_touch.db',
                    'item_db_dumped_touch.dump', seo_word='Touch'),
        GameVersion('retro', 'Retro', 'items_retro.db',
                    'item_db_dumped_retro.dump', seo_word='Retro'),
        # Wakfu has no data yet and nothing may link to it. It is declared here
        # so the pipeline that builds its data has somewhere to write, and so
        # that every guard which walks the versions can see it coming.
        GameVersion('wakfu', 'Wakfu', 'items_wakfu.db',
                    'item_db_dumped_wakfu.dump', seo_word='Wakfu',
                    experimental=True, dofus=False),
    )
}

DEFAULT_VERSION = 'dofus3'


def get_game_version(key):
    """The version, or KeyError naming what was asked for.

    Deliberately not `.get(key, dofus3)`: a typo used to serve Dofus 3 data
    under another game's name, silently.
    """
    try:
        return GAME_VERSIONS[key]
    except KeyError:
        raise KeyError('unknown game version %r, known: %s'
                       % (key, ', '.join(sorted(GAME_VERSIONS))))


def version_keys(include_experimental=False):
    """Every version, oldest surface first, in the order pages list them."""
    order = ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu')
    return [key for key in order
            if include_experimental or not GAME_VERSIONS[key].experimental]


def dofus_versions():
    """The versions that are Dofus, for rules that assume Dofus."""
    return [key for key in version_keys(include_experimental=True)
            if GAME_VERSIONS[key].dofus]
