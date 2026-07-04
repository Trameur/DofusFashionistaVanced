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
import pickle

from chardata.inventory_solver import get_inventory_mode
from chardata.lock_forbid import add_items_to_exclusions, remove_items_from_exclusions
from chardata.options import get_options, set_options, DOFUS_OPTIONS,\
    get_dofus_not_for_char, get_available_options
from chardata.util import safe_int, set_response, get_char_or_raise, HttpResponseJson
from fashionistapulp.structure import get_structure
from chardata.views import forbidden


def _inventory_folders_for(request, char):
    """Folders the project owner can restrict the solver to (own chars only)."""
    if not request.user.is_authenticated or char.owner != request.user:
        return []
    from chardata.inventory_view import get_user_folders
    return [{'id': folder.id, 'name': folder.name,
             'count': folder.items.count()}
            for folder in get_user_folders(request.user, char.game_version)]


def parse_inventory_options(request, char, options):
    """Read the item-source choice posted by the options page or the wizard
    into `options`. No-op when the form did not include the controls."""
    if ('inventory_mode' not in request.POST
            and 'inventory_folder' not in request.POST):
        return
    mode = request.POST.get('inventory_mode', 'all')
    if mode not in ('all', 'mixed', 'only'):
        mode = 'all'
    folder_id = safe_int(request.POST.get('inventory_folder'), None)
    if folder_id is not None:
        from chardata.models import InventoryFolder
        owned = (request.user.is_authenticated and
                 InventoryFolder.objects.filter(
                     id=folder_id, user=request.user,
                     game_version=char.game_version).exists())
        if not owned:
            folder_id = None
    if folder_id is None:
        mode = 'all'
    options['inventory_mode'] = mode
    options['inventory_folder'] = folder_id


def inventory_source_context(request, char):
    """Template context for the shared item-source widget."""
    options = {}
    if char.options:
        options = pickle.loads(char.options)
    return {
        'inventory_folders': _inventory_folders_for(request, char),
        'inventory_mode': get_inventory_mode(options),
        'selected_inventory_folder': options.get('inventory_folder'),
    }


def options(request, char_id):
    char = get_char_or_raise(request, char_id)

    options = get_options(char)

    context = {'advanced': True,
               'options': json.dumps(options),
               'version_options': get_available_options(),
               'char_id': char_id}
    context.update(inventory_source_context(request, char))
    return set_response(request,
                        'chardata/options.html',
                        context,
                        char)

def options_post(request, char_id):
    char = get_char_or_raise(request, char_id)

    options = parse_options_post(request)
    parse_inventory_options(request, char, options)
    set_options(char, options)
    
    too_high = get_dofus_not_for_char(char)
    forbidden_dofus = []
    allowed_dofus = []
    structure = get_structure()
    for (red, item) in DOFUS_OPTIONS.items():
        if red not in too_high:
            forbidden = request.POST.get(red) is None
            dofus = structure.get_item_by_name(item)
            if dofus is None:
                continue  # dofus not in this version (Retro/Dofus 2)
            if forbidden:
                forbidden_dofus.append(int(dofus.id))
            else:
                allowed_dofus.append(int(dofus.id))
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
    options['trophies'] = request.POST.get('trophies', None) == 'on'
        
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

