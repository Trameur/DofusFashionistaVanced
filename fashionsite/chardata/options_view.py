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

from chardata.lock_forbid import add_items_to_exclusions, remove_items_from_exclusions
from chardata.options import get_options, set_options, DOFUS_OPTIONS,\
    get_dofus_not_for_char
from chardata.util import set_response, get_char_or_raise, HttpResponseJson
from fashionistapulp.structure import get_structure
from chardata.views import forbidden


def options(request, char_id):
    char = get_char_or_raise(request, char_id)

    options = get_options(char)
    
    return set_response(request, 
                        'chardata/options.html', 
                        {'advanced': True,
                         'options': json.dumps(options),
                         'char_id': char_id},
                        char)

def options_post(request, char_id):
    char = get_char_or_raise(request, char_id)
    
    options = parse_options_post(request)
    set_options(char, options)
    
    too_high = get_dofus_not_for_char(char)
    forbidden_dofus = []
    allowed_dofus = []
    for (red, item) in DOFUS_OPTIONS.items():
        if red not in too_high:
            forbidden = request.POST.get(red) is None
            structure = get_structure()
            item_id = structure.get_item_by_name(item).id
            if forbidden:
                forbidden_dofus.append(int(item_id))
            else:
                allowed_dofus.append(int(item_id))
    add_items_to_exclusions(char, forbidden_dofus)
    remove_items_from_exclusions(char, allowed_dofus)
    
    return HttpResponseJson(json.dumps(get_options(char)))

def parse_options_post(request):
    options = {}
    options['ap_exo'] = (request.POST.get('ap_exo', 'no') == 'yes')
    if 'range_exo' in request.POST:
        options['range_exo'] = (request.POST.get('range_exo', 'no') == 'yes')
#     if 'shields' in request.POST:
#         options['shields'] = (request.POST.get('shields', 'no') == 'yes')
    
    options['dragoturkey'] = request.POST.get('dragoturkey', None) == 'on'
    options['seemyool'] = request.POST.get('seemyool', None) == 'on'
    options['rhineetle'] = request.POST.get('rhineetle', None) == 'on'
    options['prysmaradite'] = request.POST.get('prysmaradite', None) == 'on'
        
    if 'dofus' in request.POST:
        dofus_trophy = request.POST.get('dofus', 'no')   
        if dofus_trophy == 'lightset':
            options['dofus'] = dofus_trophy
        elif dofus_trophy == 'cawwot':
            options['dofus'] = dofus_trophy
        else:
            options['dofus'] = (dofus_trophy == 'yes')

    mp_exo = request.POST.get('mp_exo', 'no')   
    if mp_exo == 'gelano':
        options['mp_exo'] = mp_exo
    else:
        options['mp_exo'] = (mp_exo == 'yes')

    return options

