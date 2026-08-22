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
from chardata.char_blobs import read_char_blob
from django.utils.functional import lazy
from django.utils.translation import gettext_lazy as _
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language

# Display order. The icon is always chardata/<key>.png; the English label is kept
# so _dofus_label can tell a real translation from an untranslated string.
DOFUS_DISPLAY = [
    ('cawwot', 'Cawwot', _('Cawwot')),
    ('grofus', 'Grofus', _('Grofus')),
    ('dokoko', 'Dokoko', _('Dokoko')),
    ('vulbis', 'Vulbis', _('Vulbis')),
    ('dolmanax', 'Dolmanax', _('Dolmanax')),
    ('watchers', 'Watchers', _('Watchers')),
    ('kaliptus', 'Kaliptus', _('Kaliptus')),
    ('dotrich', 'Dotrich', _('Dotrich')),
    ('emerald', 'Emerald', _('Emerald')),
    ('crimson', 'Crimson', _('Crimson')),
    ('ochre', 'Ochre', _('Ochre')),
    ('turquoise', 'Turquoise', _('Turquoise')),
    ('cloudy', 'Cloudy', _('Cloudy')),
    ('ivory', 'Ivory', _('Ivory')),
    ('ice', 'Ice', _('Ice')),
    ('abyssal', 'Abyssal', _('Abyssal')),
    ('lavasmith', 'Lavasmith', _('Lavasmith')),
    ('blackspotted', 'Black Spotted', _('Black Spotted')),
    ('ebony', 'Ebony', _('Ebony')),
    ('silver', 'Silver', _('Silver')),
    ('sparklingsilver', 'Sparkling Silver', _('Sparkling Silver')),
    ('cocoa', 'Cocoa', _('Cocoa')),
    ('domakuro', 'Domakuro', _('Domakuro')),
    ('dorigami', 'Dorigami', _('Dorigami')),
    ('nightmare', 'Nightmare', _('Nightmare')),
    ('sylvan', 'Sylvan', _('Sylvan')),
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


def _dofus_label(key, english, translated):
    """The short label, or the dofus's name in the player's language from the game
    data when the catalog has no translation."""
    text = str(translated)
    language = get_supported_language()
    # In English the label IS the source text, never a missing translation.
    if text != english or language == 'en':
        return text
    item_name = DOFUS_OPTIONS.get(key)
    if not item_name:
        return english
    item = get_structure().get_item_by_name(item_name)
    if item is None:
        return english
    localized = item.localized_names.get(language)
    if not localized:
        return english
    # Some languages keep the English word in the full name ("Dofus Vulbis").
    if english.lower() in localized.lower():
        return english
    return localized


# Labels are cached per game version, not per language, so they must stay lazy.
_lazy_dofus_label = lazy(_dofus_label, str)

_available_options_cache = {}


def get_available_options(structure=None):
    """Which dofuses, mounts and prysmaradite exist in the current game version."""
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
        # The slot, not the name alone: Dofus 2 has a Rhineetle Helmet and no
        # Rhineetle to ride, and it was offering the mount because of the hat.
        if it.name and s.get_type_name_by_id(it.type) == 'Pet':
            for token in mounts:
                if not mounts[token] and token in it.name:
                    mounts[token] = True
    result = {
        'dofuses': [{'key': k, 'label': _lazy_dofus_label(k, english, lbl),
                     'img': 'chardata/%s.png' % k}
                    for k, english, lbl in DOFUS_DISPLAY if k in avail],
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
    options = read_char_blob(char.options, {}, 'options', char)
    # keyed on the stored column, not on what it read back: a char whose
    # options blob is unreadable still needs these four defaults.
    if char.options:
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
        old_options = read_char_blob(char.options, {}, 'options', char)
        old_options.update(options)
        char.options = pickle.dumps(old_options)
    else:
        char.options = pickle.dumps(options)

    char.save()

