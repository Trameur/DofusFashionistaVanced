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

from chardata.lock_forbid import get_all_exclusions_en_names

import pickle
from fashionistapulp.structure import get_structure

DOFUS_OPTIONS = {'ochre': 'Ochre Dofus', 
                 'vulbis': 'Vulbis Dofus',
                 'ice': 'Ice Dofus',
                 'crimson': 'Crimson Dofus', 
                 'dolmanax': 'Dolmanax',
                 'cawwot': 'Cawwot Dofus',
                 'emerald': 'Emerald Dofus',
                 'turquoise': 'Turquoise Dofus',
                 'ivory': 'Ivory Dofus',
                 'watchers': 'Watchers Dofus',
                 'dokoko': 'Dokoko',
                 'cloudy': 'Cloudy Dofus',
                 'dotrich': 'Dotrich',
                 'abyssal': 'Abyssal Dofus',
                 'grofus': 'Grofus',
                 'kaliptus': 'Kaliptus Dofus',
                 'lavasmith': 'Lavasmith Dofus',
                 'blackspotted': 'Black-Spotted Dofus',
                 'ebony': 'Ebony Dofus',
                 'silver': 'Silver Dofus',
                 'sparklingsilver': 'Sparkling Silver Dofus',
                 'cocoa': 'Cocoa Dofus 2',
                 'domakuro': 'Domakuro',
                 'dorigami': 'Dorigami',
                 'nightmare': 'Nightmare Dofus',
                 'sylvan': 'Sylvan Dofus 2',}

def get_dofus_not_for_char(char):
    s = get_structure()
    dofus_for_char = {}
    for (red, item) in DOFUS_OPTIONS.items():
        dofus = s.get_item_by_name(item)
        if dofus.level > char.level:
            dofus_for_char[red] = item
    return dofus_for_char
        

def get_options(char):
    options = {}
    
    if char.options:
        options = pickle.loads(char.options)
        options['dragoturkey'] = options.get('dragoturkey', True)
        options['seemyool'] = options.get('seemyool', True)
        options['rhineetle'] = options.get('rhineetle', True)
        options['prysmaradite'] = options.get('prysmaradite', char.level >= 200)
    options.setdefault('dofus', True)
    
    exclusions = get_all_exclusions_en_names(char)
    dofus_opt = {}
    for (red, item) in DOFUS_OPTIONS.items():
        dofus_opt[red] = item not in exclusions

    options['dofuses'] = dofus_opt
    options['dofusnotforchar'] = get_dofus_not_for_char(char)
    return options

def set_options(char, options):
    assert type(options.get('ap_exo', False)) == bool
    assert type(options.get('range_exo', False)) == bool
    assert options.get('mp_exo') == 'gelano' or type(options.get('mp_exo', False)) == bool
    assert options.get('dofus') == 'lightset' or options.get('dofus') == 'cawwot' or type(options.get('dofus', False)) == bool

    if char.options:
        old_options = pickle.loads(char.options)
        old_options.update(options)
        char.options = pickle.dumps(old_options)
    else:
        char.options = pickle.dumps(options)

    char.save()

