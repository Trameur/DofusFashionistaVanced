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

"""The Dofus Touch TemporiX servers, as a mode of a Touch build.

Ankama ran them from 15 September to 13 October 2026 (devblog 1771318,
"TemporiX Temporary Servers"). Two of their rules change what a build reaches:

- no cap on AP, MP, Range or summons. Resistances keep theirs, and an item's
  own AP or MP condition still applies (devblog: "the equipment constraints for
  certain items on the maximum number of AP and MP will not be modified");
- a piece that drops "shiny" (rayonnant) does so with a perfect roll and 1.5
  times its values, rounded up: a shiny Gelano gives 2 AP, a shiny Vulbis 2 MP.

TemporiX is not a separate data source. Ankama's own client reaches a game
server's proxy only through the authenticated login socket, and the TemporiX
items sit in the same live Touch tables as every other item, so the catalogue
the site already reads is the TemporiX one. What the servers compute and never
publish is the shiny roll, which is why it is computed here.
"""

import sqlite3
from copy import copy

from .fashionista_config import get_items_db_path
from .game_versions import get_game_version

#: Bumped whenever the rule below changes, so that a solve stored under the old
#: rule is not handed back as if it were the new one. A TemporiX solve carries
#: it in its options; a classic Touch solve carries False instead (see
#: fashion_action.get_options).
RULE_VERSION = 3

#: What can drop shiny, read in Ankama's client (build/script.js, the Item
#: constructor): canBeShiny = BELT || BOOTS || HAT || CAPE || AMULET || RING ||
#: DOFUS_OR_TROPHY. Weapons, shields, pets and mounts cannot. The devblog's
#: wording suggests shields could; the client and the drop tables say no.
SHINY_TYPES = frozenset(('Hat', 'Cloak', 'Amulet', 'Ring', 'Belt', 'Boots',
                         'Dofus'))

#: Pieces that exist only on the TemporiX servers. They are in the live Touch
#: tables like any other item, so until this mode existed every classic Touch
#: build was offered them, and a plain Touch solve did pick the first two.
TEMPORIX_ONLY_ANKAMA_IDS = {
    # A quest reward, levelled with runes up to rank 1000.
    23841: 'Shield of Infinity',
    # A quest reward: 1 AP, 1 MP, 1 Range.
    23851: 'The Real Ivory Dofus',
    # Its equip condition is the TemporiX criterion Sc=13000&PB!805.
    24053: 'Cocoa Dofus',
}

#: A drop condition that shuts the TemporiX servers out.
_NOT_ON_TEMPORIX = 'Sc!13000'


def version_has_temporix(game_version):
    return bool(getattr(get_game_version(game_version), 'temporix', False))


def is_on(options, game_version):
    """Whether a solve or a page runs under the TemporiX rules."""
    return bool((options or {}).get('temporix')) and version_has_temporix(
        game_version)


def shiny_value(value):
    """1.5 times the value, rounded up, the sign kept.

    Rounded in magnitude: a shiny malus grows like a bonus does. Ankama's
    written recap of the 2 September live: "Si un equipement rayonnant possede
    des malus, sont-ils egalement augmentes ? Oui". The catalogue stores a
    ranged malus at its best roll, the end nearest zero, like a bonus at its
    maximum, and that is the value multiplied here.
    """
    magnitude = (3 * abs(value) + 1) // 2
    return magnitude if value >= 0 else -magnitude


def droppable_item_ids(structure):
    """Ids of the pieces some monster drops where TemporiX lets it.

    Only a drop can be shiny: "each piece of equipment ... will have a chance
    of being dropped in its shiny version" (devblog). A crafted-only piece, a
    quest reward or a merchant's item is never shiny, and 618 of the pieces of
    a shiny-capable type have no drop row at all. The drop table keeps each
    row's conditions, and a TemporiX-only drop reads Sc=13000.
    """
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
    # A trophy shares the Dofus type in the catalogue. Trophies are sold on
    # TemporiX, never dropped.
    if 'Trophy' in flags:
        return False
    # A piece bound to the character is a quest reward: The Real Ivory Dofus
    # is the one players ask about.
    if 'Linked to the character' in flags:
        return False
    return item.id in droppable_item_ids(structure)


def shiny_item(item):
    """A copy of the piece carrying its shiny values; the catalogue row stays."""
    shiny = copy(item)
    shiny.stats = [(stat_id, shiny_value(value)) for stat_id, value in item.stats]
    # A shiny roll is perfect: there is no range left to show.
    shiny.stat_ranges = {}
    shiny.shiny = True
    return shiny


def shiny_items_by_id(structure):
    """{item id: its shiny copy} for every piece that can be shiny.

    Kept on the structure, so it is built once per catalogue and thrown away
    with it. Gelano (#1) is left out: it is the Gelano that carries an MP exo,
    and a shiny piece cannot be forgemaged, so that Gelano is a normal one.
    """
    cached = getattr(structure, '_temporix_shiny_items', None)
    if cached is None:
        exo_gelano = structure.get_item_by_name('Gelano (#1)')
        skipped = {exo_gelano.id} if exo_gelano is not None else set()
        cached = {item.id: shiny_item(item)
                  for item in structure.get_items_list()
                  if item.id not in skipped and can_be_shiny(item, structure)}
        structure._temporix_shiny_items = cached
    return cached


def temporix_only_item_ids(structure):
    """The catalogue rows of the pieces only TemporiX has.

    Empty on every other version: an Ankama id names a different piece in each
    client, and 23841 is not a shield in Dofus 3.
    """
    ids = set()
    if not version_has_temporix(structure.game_version):
        return ids
    for ankama_id in TEMPORIX_ONLY_ANKAMA_IDS:
        item = structure.get_item_by_ankama_id(ankama_id)
        if item is not None:
            ids.add(item.id)
    return ids


def as_worn(item, structure, options, overridden=False):
    """The piece a TemporiX build wears in this slot.

    Its shiny copy when the mode is on and the piece can be shiny, the
    catalogue row otherwise. A piece the player recorded rolls for is one he
    owns and forgemaged, and a shiny piece cannot be forgemaged, so it keeps
    its recorded values instead.
    """
    if (item is None or overridden
            or not is_on(options, structure.game_version)):
        return item
    return shiny_items_by_id(structure).get(item.id, item)
