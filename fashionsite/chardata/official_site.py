# Copyright (C) 2020 The Dofus Fashionista
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

import re

from django.utils.translation import get_language
from fashionistapulp.fashion_util import strip_accents


BASE_URLS = {
    'en': '/encyclopedia/item/%s/%d-%s/',
    'fr': '/encyclopedia/item/%s/%d-%s/',
    'pt': '/encyclopedia/item/%s/%d-%s/',
    'es': '/encyclopedia/item/%s/%d-%s/',
    'de': '/encyclopedia/item/%s/%d-%s/',
    'it': '/encyclopedia/item/%s/%d-%s/',
}

ANKAMA_TYPE_TO_SITE_CATEGORY = {
    'en': {'pet': 'pet',
           'pets': 'pet',
           'mount': 'mounts',
           'mounts': 'mounts',
           'equipment': 'equipment'},
    'fr': {'pet': 'pet',
           'pets': 'pet',
           'mount': 'mounts',
           'mounts': 'mounts',
           'equipment': 'equipment'},
    'pt': {'pet': 'pet',
           'pets': 'pet',
           'mount': 'mounts',
           'mounts': 'mounts',
           'equipment': 'equipment'},
    'es': {'pet': 'pet',
           'pets': 'pet',
           'mount': 'mounts',
           'mounts': 'mounts',
           'equipment': 'equipment'},
    'de': {'pet': 'pet',
           'pets': 'pet',
           'mount': 'mounts',
           'mounts': 'mounts',
           'equipment': 'equipment'}
}


def _slugify_name(name, fallback):
    slug_source = strip_accents(name or '').strip().lower()
    slug_source = slug_source.replace('\'s', '')
    slug = re.sub(r'[^a-z0-9]+', '-', slug_source).strip('-')
    return slug or fallback


def get_item_link(ankama_type, ankama_id, name, game_version='dofus3'):
    if not ankama_id or not ankama_type:
        return None

    name = _slugify_name(name, 'item')

    lang = (get_language() or 'en').split('-')[0]
    if lang not in BASE_URLS:
        lang = 'en'

    category_map = ANKAMA_TYPE_TO_SITE_CATEGORY.get(lang, ANKAMA_TYPE_TO_SITE_CATEGORY['en'])
    category = category_map.get(ankama_type, 'equipment')
    path = BASE_URLS[lang] % (category, ankama_id, name)
    if game_version != 'dofus3':
        return f'/{game_version}{path}'
    return path


def get_resource_link(subtype, ankama_id, name, game_version='dofus3'):
    if not ankama_id or not subtype:
        return None

    name = _slugify_name(name, 'resource')

    path = '/encyclopedia/resource/%s/%d-%s/' % (subtype, int(ankama_id), name)
    if game_version != 'dofus3':
        return f'/{game_version}{path}'
    return path


def get_monster_link(monster_ankama_id, name, game_version='dofus3'):
    if not monster_ankama_id:
        return None

    name = _slugify_name(name, 'monster')

    path = '/encyclopedia/monster/%d-%s/' % (int(monster_ankama_id), name)
    if game_version != 'dofus3':
        return f'/{game_version}{path}'
    return path


def get_set_link(set_id, name, game_version='dofus3'):
    if not set_id:
        return None

    name = _slugify_name(name, 'set')

    path = '/encyclopedia/set/%d-%s/' % (int(set_id), name)
    if game_version != 'dofus3':
        return f'/{game_version}{path}'
    return path
