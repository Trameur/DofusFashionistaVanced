# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Links from a Wakfu page to the same item on the official encyclopedia."""

ORIGIN = 'https://www.wakfu.com'
FALLBACK_LANGUAGE = 'en'
WEAPON_POSITIONS = ('FIRST_WEAPON', 'SECOND_WEAPON')

ARMOR_TYPES = frozenset((103, 119, 120, 132, 133, 134, 136, 138))
ACCESSORY_TYPES = frozenset((646, 849))

SECTION_PATHS = {
    'armor': {'fr': 'fr/mmorpg/encyclopedie/armures', 'en': 'en/mmorpg/encyclopedia/armors',
              'es': 'es/mmorpg/enciclopedia/armaduras', 'pt': 'pt/mmorpg/enciclopedia/armaduras'},
    'weapon': {'fr': 'fr/mmorpg/encyclopedie/armes', 'en': 'en/mmorpg/encyclopedia/weapons',
               'es': 'es/mmorpg/enciclopedia/armas', 'pt': 'pt/mmorpg/enciclopedia/armas'},
    'accessory': {'fr': 'fr/mmorpg/encyclopedie/accessoires',
                  'en': 'en/mmorpg/encyclopedia/accessories',
                  'es': 'es/mmorpg/enciclopedia/accesorios',
                  'pt': 'pt/mmorpg/enciclopedia/acessorios'},
}


def weapon_types(conn):
    """The item types whose position is a weapon hand, read from the database."""
    marks = ','.join('?' * len(WEAPON_POSITIONS))
    return frozenset(row[0] for row in conn.execute(
        'SELECT item_type FROM item_type_position WHERE position IN (%s)' % marks,
        WEAPON_POSITIONS))


def section_of(item_type, weapons):
    """'armor', 'weapon' or 'accessory', or None for a type no official section lists."""
    if item_type in weapons:
        return 'weapon'
    if item_type in ARMOR_TYPES:
        return 'armor'
    if item_type in ACCESSORY_TYPES:
        return 'accessory'
    return None


def item_link(item_id, item_type, language, weapons):
    """The official page of an item in the page language (German links English), or None."""
    section = section_of(item_type, weapons)
    if section is None:
        return None
    paths = SECTION_PATHS[section]
    return '%s/%s/%d' % (ORIGIN, paths.get(language, paths[FALLBACK_LANGUAGE]), item_id)
