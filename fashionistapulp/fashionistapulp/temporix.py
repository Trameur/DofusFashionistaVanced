# -*- coding: utf-8 -*-

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

"""Dofus Touch TemporiX mode: no AP, MP, Range or summon cap, and shiny pieces."""

import sqlite3
from copy import copy

from .fashionista_config import get_items_db_path
from .game_versions import get_game_version

# Bump when the shiny rules change, stored solves carry it in their options
RULE_VERSION = 3

# canBeShiny in the client's Item constructor: no weapon, shield, pet or mount
SHINY_TYPES = frozenset(('Hat', 'Cloak', 'Amulet', 'Ring', 'Belt', 'Boots',
                         'Dofus'))

# TemporiX only, but in the live Touch tables with everything else
TEMPORIX_ONLY_ANKAMA_IDS = {
    # Quest reward, levelled with runes up to rank 1000
    23841: 'Shield of Infinity',
    # Quest reward: 1 AP, 1 MP, 1 Range
    23851: 'The Real Ivory Dofus',
    # Equip condition Sc=13000&PB!805
    24053: 'Cocoa Dofus',
}

# Drop condition that excludes TemporiX
_NOT_ON_TEMPORIX = 'Sc!13000'


def version_has_temporix(game_version):
    return bool(getattr(get_game_version(game_version), 'temporix', False))


def is_on(options, game_version):
    """Whether a solve or a page runs under the TemporiX rules."""
    return bool((options or {}).get('temporix')) and version_has_temporix(
        game_version)


def shiny_value(value):
    """1.5 times the value rounded up in magnitude: a malus grows too."""
    magnitude = (3 * abs(value) + 1) // 2
    return magnitude if value >= 0 else -magnitude


def droppable_item_ids(structure):
    """Ids of pieces dropped on TemporiX: only a drop can be shiny."""
    cached = getattr(structure, '_temporix_droppable', None)
    if cached is None:
        cached = set()
        connection = sqlite3.connect(get_items_db_path(structure.game_version))
        try:
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name = 'item_drops'").fetchone()
            if table:
                for item_id, conditions in connection.execute(
                        'SELECT item, conditions FROM item_drops'):
                    if _NOT_ON_TEMPORIX not in (conditions or ''):
                        cached.add(item_id)
        finally:
            connection.close()
        structure._temporix_droppable = cached
    return cached


def can_be_shiny(item, structure):
    """Whether Ankama can drop this piece shiny."""
    if structure.get_type_name_by_id(item.type) not in SHINY_TYPES:
        return False
    flags = getattr(item, 'flags', None) or ()
    # Trophies share the Dofus type, and are sold on TemporiX, never dropped
    if 'Trophy' in flags:
        return False
    # Bound to the character means a quest reward
    if 'Linked to the character' in flags:
        return False
    return item.id in droppable_item_ids(structure)


def shiny_item(item):
    """Shiny copy of the piece, the catalogue row is left alone."""
    shiny = copy(item)
    shiny.stats = [(stat_id, shiny_value(value)) for stat_id, value in item.stats]
    # A shiny roll is perfect, no range
    shiny.stat_ranges = {}
    shiny.shiny = True
    return shiny


def shiny_items_by_id(structure):
    """{item id: shiny copy}, cached on the structure."""
    cached = getattr(structure, '_temporix_shiny_items', None)
    if cached is None:
        # Gelano (#1) is the MP exo one, and a shiny piece cannot be forgemaged
        exo_gelano = structure.get_item_by_name('Gelano (#1)')
        skipped = {exo_gelano.id} if exo_gelano is not None else set()
        cached = {item.id: shiny_item(item)
                  for item in structure.get_items_list()
                  if item.id not in skipped and can_be_shiny(item, structure)}
        structure._temporix_shiny_items = cached
    return cached


def temporix_only_item_ids(structure):
    """Ids of the TemporiX-only pieces, empty on other versions."""
    ids = set()
    if not version_has_temporix(structure.game_version):
        return ids
    for ankama_id in TEMPORIX_ONLY_ANKAMA_IDS:
        item = structure.get_item_by_ankama_id(ankama_id)
        if item is not None:
            ids.add(item.id)
    return ids


def as_worn(item, structure, options, overridden=False):
    """Shiny copy when TemporiX is on, a piece with recorded rolls stays as is."""
    if (item is None or overridden
            or not is_on(options, structure.game_version)):
        return item
    return shiny_items_by_id(structure).get(item.id, item)
