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

from django.utils.translation import get_language
import re


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


def get_item_link(ankama_type, ankama_id, name, game_version='dofus3'):
    if not ankama_id or not ankama_type:
        return None

    name = name.strip().lower()
    name = name.replace('\'s', '')
    name = name.replace(' ', '-')
    regex = re.compile('[^a-zA-Z-]')
    name = regex.sub('', name)

    lang = (get_language() or 'en').split('-')[0]
    if lang not in BASE_URLS:
        lang = 'en'

    category_map = ANKAMA_TYPE_TO_SITE_CATEGORY.get(lang, ANKAMA_TYPE_TO_SITE_CATEGORY['en'])
    category = category_map.get(ankama_type, 'equipment')
    path = BASE_URLS[lang] % (category, ankama_id, name)
    if game_version not in ('dofus3', 'touch'):
        return f'/{game_version}{path}'
    return path
