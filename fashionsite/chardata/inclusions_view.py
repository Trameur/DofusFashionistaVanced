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

import json
import jsonpickle

from chardata.lock_forbid import (get_inclusions_dict,
    set_inclusions_dict_and_check_exclusions,
    get_stat_overrides, set_item_stat_override, remove_item_stat_override)
from chardata.util import set_response, get_char_or_raise, HttpResponseJson, HttpResponseText
from fashionistapulp.dofus_constants import SLOTS, SLOT_NAME_TO_TYPE
from fashionistapulp.structure import get_structure
from chardata.image_store import get_image_url
from chardata.stat_icons import get_stat_icon_path
from static_s3.templatetags.static_s3 import static
from fashionistapulp.translation import get_supported_language
from chardata.themes import get_ajax_loader_URL
from django.utils.translation import gettext as _


def inclusions(request, char_id):
    char = get_char_or_raise(request, char_id)

    structure = get_structure()
    types_list = structure.get_types_list()
    items_by_type = {}
    items_by_type_and_name = {}
    for item_type in types_list:
        items_by_type[item_type] = {}
        items_by_type_and_name[item_type] = {}
    for item_type in items_by_type:
        for item in structure.get_unique_items_by_type_and_level(item_type, char.level):
            item_name = structure.get_item_name_in_language(item, get_supported_language())
            items_by_type[item_type][item.id] = item_name
            items_by_type_and_name[item_type][item_name] = item.id

    images_urls = {}
    for item_slot in SLOT_NAME_TO_TYPE:
        images_urls[item_slot] = static('chardata/%s.png' % SLOT_NAME_TO_TYPE[item_slot])

    inclusions = get_inclusions_dict(char)
    for slot in SLOTS:
        inclusions.setdefault(slot, '')

    # Convert stat_overrides keys to strings for JSON (item_id: {stat_id: value})
    raw_overrides = get_stat_overrides(char)
    stat_overrides_json = {str(item_id): {str(stat_id): val for stat_id, val in stats.items()}
                           for item_id, stats in raw_overrides.items()}

    return set_response(request,
                        'chardata/inclusions.html',
                        {'char_id': char_id,
                         'advanced': True,
                         'types': items_by_type,
                         'types_json': jsonpickle.encode(items_by_type, unpicklable=False),
                         'names_and_types_json': jsonpickle.encode(items_by_type_and_name, unpicklable=False),
                         'inclusions_json': json.dumps(inclusions),
                         'images_json': json.dumps(images_urls),
                         'slot_to_type_json': json.dumps(SLOT_NAME_TO_TYPE),
                         'ajax_loader': json.dumps(get_ajax_loader_URL(request)),
                         'stat_overrides_json': json.dumps(stat_overrides_json)},
                        char)

def get_item_details(request):
    item_id = request.POST.get('item', None)

    info = {}
    if item_id is not None:
        structure = get_structure()
        item = structure.get_item_by_id(int(item_id))
        info['level'] = item.level
        info['file'] = static(get_image_url(structure.get_type_name_by_id(item.type), item.name))
        info['stats'] = []
        for stat_id, value in item.stats:
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            icon_path = get_stat_icon_path(stat.key)
            info['stats'].append({
                'stat_id': stat_id,
                'name': _(stat.name),
                'value': value,
                'icon_url': static(icon_path) if icon_path else None,
            })

    json_response = jsonpickle.encode(info, unpicklable=False)

    return HttpResponseJson(json_response)

def inclusions_post(request, char_id):
    char = get_char_or_raise(request, char_id)

    inclusions = {}
    for slot in SLOTS:
        inclusions[slot] = request.POST.get(slot, '')

    set_inclusions_dict_and_check_exclusions(char, inclusions)

    inclusions = get_inclusions_dict(char)

    for slot in SLOTS:
        inclusions.setdefault(slot, '')

    return HttpResponseJson(json.dumps(inclusions))

def set_item_stat_override_view(request, char_id):
    char = get_char_or_raise(request, char_id)

    item_id = request.POST.get('item_id', None)
    stat_id = request.POST.get('stat_id', None)
    value = request.POST.get('value', None)

    if item_id is None or stat_id is None:
        return HttpResponseText('error')

    item_id = int(item_id)
    stat_id = int(stat_id)

    if value is None or value == '':
        remove_item_stat_override(char, item_id, stat_id)
    else:
        set_item_stat_override(char, item_id, stat_id, int(value))

    return HttpResponseText('ok')

