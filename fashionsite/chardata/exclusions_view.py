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

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy

import json

from chardata.lock_forbid import get_all_exclusions_with_names, get_all_exclusions_ids, set_exclusions_list_and_check_inclusions
from chardata.util import set_response, get_char_or_raise, HttpResponseJson
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language


TYPE_COLUMNS = [
    [{'id': 'Weapon', 'name': gettext_lazy('Weapon')}, 
     {'id': 'Shield', 'name': gettext_lazy('Shield')},
     {'id': 'Hat', 'name': gettext_lazy('Hat')}, 
     {'id': 'Cloak', 'name': gettext_lazy('Cloak')},
     {'id': 'Pet', 'name': gettext_lazy('Pet')}],
    [{'id': 'Amulet', 'name': gettext_lazy('Amulet')}, 
     {'id': 'Ring', 'name': gettext_lazy('Ring')},
     {'id': 'Boots', 'name': gettext_lazy('Boots')}, 
     {'id': 'Belt', 'name': gettext_lazy('Belt')},
     {'id': 'Dofus', 'name': gettext_lazy('Dofus')}]
]

def exclusions(request, char_id):
    char = get_char_or_raise(request, char_id) 
    s = get_structure()
    language = get_supported_language()
    
    sets_names = s.get_set_names(language)
    sets_names_dicts = {set_name: None for set_name in sets_names}

    all_items = s.get_all_unique_items_ids_with_type()
    all_items_names = s.get_all_unique_items_names_with_ids(language)

    # A few or-item variants (e.g. Gelano) are indexed name -> id with an id that
    # isn't in the forbiddable set, so the page silently did nothing when you
    # forbade them. Remap those to a same-item forbiddable id; the optimizer then
    # forbids the whole or-group. Copy first: all_items_names is a shared cache.
    forbiddable_ids = set(all_items)
    or_name_to_forbiddable = {}
    for item_id in all_items:
        item = s.get_item_by_id(item_id)
        if item is not None:
            or_name_to_forbiddable.setdefault(item.or_name, item_id)
    fixed_items_names = {}
    for name, item_id in all_items_names.items():
        if item_id is not None and item_id not in forbiddable_ids:
            item = s.get_item_by_id(item_id)
            alt = or_name_to_forbiddable.get(item.or_name) if item is not None else None
            fixed_items_names[name] = alt if alt is not None else item_id
        else:
            fixed_items_names[name] = item_id

    all_names = sets_names_dicts.copy()
    all_names.update(fixed_items_names)
    
    complete_sets = s.get_complete_sets_list(language)
    exclusions = get_all_exclusions_with_names(char, language)

    return set_response(request, 
                        'chardata/exclusions.html', 
                        {'char_id': char_id,
                         'advanced': True,
                         'type_columns': TYPE_COLUMNS,
                         'all_items_json': json.dumps(all_items),
                         'all_items_names_json': json.dumps(all_names),
                         'sets_with_items_json': json.dumps(complete_sets),
                         'exclusions': json.dumps(exclusions)}, 
                        char)


def exclusions_post(request, char_id):
    char = get_char_or_raise(request, char_id)
    
    exclusions_string = request.POST.get('exclusions', None)
    if exclusions_string is None:
        raise ValidationError('Exclusions list not received.')
        
    exclusions = json.loads(exclusions_string)
    actual_exclusions = [int(iditem) for iditem in exclusions]
    set_exclusions_list_and_check_inclusions(char, actual_exclusions)
    
    return HttpResponseJson(json.dumps(get_all_exclusions_ids(char)))
