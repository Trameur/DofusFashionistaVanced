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

from chardata.min_stats import get_min_stats, set_min_stats, convert_dict_index_name_to_key
from chardata.util import safe_int, get_char_or_raise, HttpResponseJson
from chardata.weights_minimums import _get_stat_icon_url, _get_adv_stat_icon_urls  # noqa: F401
from fashionistapulp.structure import get_structure
from django.views.decorators.http import require_POST


def min_stats(request, char_id):
    from chardata.stats_weights_view import weights_and_minimums_page
    return weights_and_minimums_page(request, get_char_or_raise(request, char_id), 'minimums')


@require_POST
def min_stats_post(request, char_id):
    char = get_char_or_raise(request, char_id)
    structure = get_structure()

    minimum_values = {}
    
    adv_stats = structure.get_adv_mins()
    adv_stat_keys = set([stat['key'] for stat in adv_stats])
    
    for stat in get_structure().get_stats_list():
        field_name = 'min_%s' % stat.key
        if stat.key in adv_stat_keys:
            continue
        if field_name in request.POST:
            minimum = safe_int(request.POST.get(field_name, ''))
            if minimum is not None:
                minimum_values[stat.name] = minimum

    if 'min_hp' in request.POST:
        minimum = safe_int(request.POST.get('min_hp'))
        if minimum is not None:
            minimum_values['HP'] = minimum

    minimum_values['adv_mins'] = {}
    for stat in adv_stats:
        field_name = 'min_%s' % stat['key']
        if field_name in request.POST:
            minimum = safe_int(request.POST.get(field_name, ''))
            if minimum is not None:
                minimum_values['adv_mins'][stat['name']] = minimum
    
    set_min_stats(char, minimum_values)        
    
    return HttpResponseJson(json.dumps(_get_initial_data(char)))
    
def _get_initial_data(char):
    mins = get_min_stats(char)
    mins = convert_dict_index_name_to_key(mins)
    structure = get_structure()
        
    for stat in get_structure().get_stats_list():
        if stat.key not in mins:
            mins[stat.key] = ''
    if 'hp' not in mins:
        mins['hp'] = ''
    adv_mins = structure.get_adv_mins()
    if 'adv_mins' not in mins:
        mins['adv_mins'] = {}
    for stat in adv_mins:
        if stat['key'] not in mins['adv_mins']:
            mins['adv_mins'][stat['key']] = ''
    
    return {'minimum_stats': mins}

