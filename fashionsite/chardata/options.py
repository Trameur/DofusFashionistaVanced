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
from django.utils.translation import gettext_lazy as _
from fashionistapulp.structure import get_structure

# Dofus option keys in display order, with their (translatable) labels. The icon is
# always chardata/<key>.png. Used to render the allow/forbid dofus grid as a loop
# filtered to what exists in the current game version (instead of hardcoding).
DOFUS_DISPLAY = [
    ('cawwot', _('Cawwot')), ('grofus', _('Grofus')), ('dokoko', _('Dokoko')),
    ('vulbis', _('Vulbis')), ('dolmanax', _('Dolmanax')), ('watchers', _('Watchers')),
    ('kaliptus', _('Kaliptus')), ('dotrich', _('Dotrich')), ('emerald', _('Emerald')),
    ('crimson', _('Crimson')), ('ochre', _('Ochre')), ('turquoise', _('Turquoise')),
    ('cloudy', _('Cloudy')), ('ivory', _('Ivory')), ('ice', _('Ice')),
    ('abyssal', _('Abyssal')), ('lavasmith', _('Lavasmith')),
    ('blackspotted', _('Black Spotted')), ('ebony', _('Ebony')), ('silver', _('Silver')),
    ('sparklingsilver', _('Sparkling Silver')), ('cocoa', _('Cocoa')),
    ('domakuro', _('Domakuro')), ('dorigami', _('Dorigami')),
    ('nightmare', _('Nightmare')), ('sylvan', _('Sylvan')),
]

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
        # These are Dofus 3 dofus names; some don't exist in other versions (Retro).
        if dofus is not None and dofus.level > char.level:
            dofus_for_char[red] = item
    return dofus_for_char


_available_options_cache = {}


def get_available_options(structure=None):
    """Which dofuses, mounts and prysmaradite exist in the current game version, so
    the wizard/options page shows only version-relevant toggles (Retro/Dofus 2 have
    no prysmaradite, fewer dofuses, etc.) instead of hardcoding the Dofus 3 set.
    Cached per version since the item DB is static at runtime."""
    s = structure or get_structure()
    ver = s.game_version
    cached = _available_options_cache.get(ver)
    if cached is not None:
        return cached
    avail = {key for key, name in DOFUS_OPTIONS.items() if s.get_item_by_name(name)}
    prysmaradite = False
    has_trophy = False
    mounts = {'Dragoturkey': False, 'Seemyool': False, 'Rhineetle': False}
    for it in s.get_items_list():
        if getattr(it, 'weird_conditions', {}).get('prysmaradite'):
            prysmaradite = True
        if 'Trophy' in getattr(it, 'flags', ()):
            has_trophy = True
        if it.name:
            for token in mounts:
                if not mounts[token] and token in it.name:
                    mounts[token] = True
    result = {
        'dofuses': [{'key': k, 'label': lbl, 'img': 'chardata/%s.png' % k}
                    for k, lbl in DOFUS_DISPLAY if k in avail],
        'prysmaradite': prysmaradite,
        'trophies': has_trophy,
        'dragoturkey': mounts['Dragoturkey'],
        'seemyool': mounts['Seemyool'],
        'rhineetle': mounts['Rhineetle'],
        'any_mount': any(mounts.values()),
    }
    _available_options_cache[ver] = result
    return result



def get_options(char):
    options = {}
    
    if char.options:
        options = pickle.loads(char.options)
        options['dragoturkey'] = options.get('dragoturkey', True)
        options['seemyool'] = options.get('seemyool', True)
        options['rhineetle'] = options.get('rhineetle', True)
        options['prysmaradite'] = options.get('prysmaradite', char.level >= 200)
    options.setdefault('dofus', True)
    options.setdefault('trophies', True)
    
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

