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

"""The game versions the site serves, and where their data lives."""


class GameVersion:
    """One playable game, and where its data lives."""

    def __init__(self, key, label, db_file, dump_file, prefix=None,
                 seo_word='', experimental=False, dofus=True,
                 rings_can_double=True, temporix=False,
                 weapon_element_rate=0.85, element_potion_heals=True):
        self.key = key
        self.label = label
        self.db_file = db_file
        self.dump_file = dump_file
        # '' for the default version, which lives at the site root.
        self.prefix = key if prefix is None else prefix
        self.seo_word = seo_word
        # Experimental: built by the pipeline, hidden from readers
        self.experimental = experimental
        # Wakfu is not a Dofus version: other stats, other slots, other rules.
        self.dofus = dofus
        # Two copies of one setless ring: Dofus 2 and 3 yes, Retro no
        self.rings_can_double = rings_can_double
        # TemporiX mode: shiny pieces, no AP, MP, Range or summon cap (temporix.py)
        self.temporix = temporix
        # Weapon element potion: share of a neutral line kept, and if heals turn too
        self.weapon_element_rate = weapon_element_rate
        self.element_potion_heals = element_potion_heals

    def __repr__(self):
        return '<GameVersion %s>' % self.key


GAME_VERSIONS = {
    version.key: version for version in (
        GameVersion('dofus3', 'Dofus 3', 'items.db', 'item_db_dumped.dump',
                    prefix='', seo_word=''),
        GameVersion('beta', 'Beta', 'items_beta.db',
                    'item_db_dumped_beta.dump', seo_word='Beta',
                    weapon_element_rate=1.0, element_potion_heals=False),
        GameVersion('dofus2', 'Dofus 2', 'items_dofus2.db',
                    'item_db_dumped_dofus2.dump', seo_word='2'),
        GameVersion('touch', 'Touch', 'items_touch.db',
                    'item_db_dumped_touch.dump', seo_word='Touch',
                    temporix=True),
        GameVersion('retro', 'Retro', 'items_retro.db',
                    'item_db_dumped_retro.dump', seo_word='Retro',
                    rings_can_double=False),
        # Nothing may link to Wakfu yet; doubled rings unknown there, so one copy
        GameVersion('wakfu', 'Wakfu', 'items_wakfu.db',
                    'item_db_dumped_wakfu.dump', seo_word='Wakfu',
                    experimental=True, dofus=False, rings_can_double=False),
    )
}

DEFAULT_VERSION = 'dofus3'


def get_game_version(key):
    """The version, or KeyError naming what was asked for."""
    try:
        return GAME_VERSIONS[key]
    except KeyError:
        raise KeyError('unknown game version %r, known: %s'
                       % (key, ', '.join(sorted(GAME_VERSIONS))))


def version_keys(include_experimental=False):
    """Every version, in the order pages list them."""
    order = ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu')
    return [key for key in order
            if include_experimental or not GAME_VERSIONS[key].experimental]


def prefixed_reader_versions():
    """Reader-facing versions under a url prefix, all but the default."""
    return [key for key in version_keys() if key != DEFAULT_VERSION]


def dofus_versions():
    """The versions that are Dofus, for rules that assume Dofus."""
    return [key for key in version_keys(include_experimental=True)
            if GAME_VERSIONS[key].dofus]
