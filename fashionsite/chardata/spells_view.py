# -*- coding: utf-8 -*-

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

from chardata.encoded_char_id import decode_char_id
from chardata.fashion_action import fashion
from chardata.image_store import get_image_url
from chardata.models import Char
from chardata.solution import get_solution
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_localization import get_localized_spell_name
from chardata.util import set_response, get_char_or_raise
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from static_s3.templatetags.static_s3 import static
from django.utils.translation import gettext as _
from fashionistapulp.translation import get_supported_language

from fashionistapulp.dofus_constants import (DAMAGE_TYPES, NEUTRAL)

import jsonpickle

def _spells(request, char, is_guest, char_id, encoded_char_id=None):
    char_class = char.char_class
    
    solution = get_solution(char)
    if solution is None:
        return fashion(request, char_id, True)    

    digests = []
    weapons = solution.items['Weapon']
    if len(weapons) > 0:
        weapon = weapons[0]
        if weapon.item_added:
            web_digest = _create_weapon_web_digest(weapon)
            digests.append(web_digest)
    game_version = getattr(request, 'game_version', 'dofus3')
    spells_by_class = get_damage_spells_for_version(game_version)
    for spell in spells_by_class.get(char_class, []) + spells_by_class.get('default', []):
        web_digest = _create_spell_web_digest(spell, game_version)
        digests.append(web_digest)
    digests_json = jsonpickle.encode(digests, unpicklable=False)
    stats_json = jsonpickle.encode(solution.get_stats_total(), unpicklable=False)
    return set_response(request, 
                        'chardata/spells.html', 
                        {'request': request,
                         'is_guest': is_guest,
                         'encoded_char_id': encoded_char_id,
                         'user': request.user,
                         'digests_json': digests_json,
                         'char_id': char_id,
                         'char_level': char.level,
                         'char_stats_json': stats_json},
                        char)

def _create_weapon_web_digest(weapon):
    web_digest = {}
    if weapon.is_mageable:
        web_digest['type'] = 'weapon'
        web_digest['element_maged'] = weapon.element_maged
    else:
        web_digest['type'] = 'weapon_non_mageable'
    web_digest['name'] = weapon.localized_name
    web_digest['level'] = weapon.level
    # Use the same version-aware icon resolution as the solution page, so the
    # weapon image works for Retro (and Beta/Dofus 2) instead of pointing at a
    # Dofus 3-only path.
    web_digest['image_url'] = static(get_image_url(weapon.type, weapon.name))
    web_digest['hit_number'] = len(weapon.non_crit_hits)
    web_digest['non_crit_dams'] = _convert_weapon_damage(weapon.non_crit_hits)
    web_digest['crit_dams'] = _convert_weapon_damage(weapon.crit_hits)
    NON_DAMAGE_ELEMENTS = {'attracts', 'pushes', 'advances', 'steals_mp'}
    damage_indexes = []
    healing_indexes = []
    effect_indexes = []
    for i, hit_instance in enumerate(weapon.non_crit_hits[NEUTRAL]):
        if hit_instance.element in NON_DAMAGE_ELEMENTS:
            effect_indexes.append(i)
        elif hit_instance.heals:
            healing_indexes.append(i)
        else:
            damage_indexes.append(i)
    aggregates = []
    if damage_indexes:
        aggregates.append(('', damage_indexes))
    if healing_indexes:
        aggregates.append(('', healing_indexes))
    for idx in effect_indexes:
        aggregates.append(('', [idx]))
    web_digest['aggregates'] = convert_aggregates(aggregates)
    
    return web_digest

def _localized_spell_name(name, language, game_version):
    # Retro and Touch spell names live in a version-specific map keyed by the French
    # name (Spell.name); other versions use the shared English-keyed localization.
    version_names = None
    if game_version == 'retro':
        from fashionistapulp.dofus_constants_retro_spells import RETRO_SPELL_NAMES
        version_names = RETRO_SPELL_NAMES
    elif game_version == 'touch':
        from fashionistapulp.dofus_constants_touch_spells import TOUCH_SPELL_NAMES
        version_names = TOUCH_SPELL_NAMES
    if version_names is not None:
        names = version_names.get(name)
        if names:
            lang = (language or 'en').split('-')[0].lower()
            return names.get(lang) or names.get('fr') or name
        return name
    return get_localized_spell_name(name, language)


def _create_spell_web_digest(spell, game_version='dofus3'):
    web_digest = {}
    digest = spell.get_effects_digest()
    current_language = get_supported_language()
    web_digest['type'] = 'spell'
    web_digest['name'] = _localized_spell_name(spell.name, current_language, game_version)
    web_digest['level'] = spell.level_req
    web_digest['stacks'] = spell.stacks
    if game_version == 'beta':
        spell_dir = 'chardata/spells/beta/'
    elif game_version == 'retro':
        spell_dir = 'chardata/spells/retro/'
    elif game_version == 'touch':
        spell_dir = 'chardata/spells/touch/'
    else:
        spell_dir = 'chardata/spells/'
    web_digest['image_url'] = static(spell_dir + spell.name + '.png')
    web_digest['hit_number'] = digest.hit_number
    web_digest['non_crit_dams'] = _convert_spell_damage(digest.non_crit_dams)
    web_digest['crit_dams'] = _convert_spell_damage(digest.crit_dams)
    web_digest['aggregates'] = convert_aggregates(digest.aggregates)
    web_digest['is_linked'] = (
        spell.is_linked[0],
        get_localized_spell_name(spell.is_linked[1], current_language)
    ) if spell.is_linked else None
    web_digest['special'] = spell.special
    web_digest['buff_scaling'] = spell.buff_scaling
    return web_digest

def spells(request, char_id=0):
    char = get_char_or_raise(request, char_id)
    return _spells(request, char, False, char_id)

def spells_linked(request, char_name, encoded_char_id):
    char_id = decode_char_id(encoded_char_id)
    if char_id is None:
        raise ValidationError('Could not decode char id from: string "%s"' % encoded_char_id)

    char = get_object_or_404(Char, pk=char_id)
    if not char.link_shared:
        raise PermissionDenied
    if char.game_version != getattr(request, 'game_version', 'dofus3'):
        raise Http404
    
    return _spells(request, char, True, char_id, encoded_char_id)
    
def _convert_spell_damage(base):
    if len(base[0]) == 0:
        return None
    return base
    
def _convert_weapon_damage(base):
    if base is None:
        return None
    actual_damages = []
    for element in DAMAGE_TYPES:
        actual_damages.append(base[element])
    return actual_damages
    

def convert_aggregates(aggregates):
    if aggregates is None:
        return None
    new_aggr = []
    for tup in aggregates:
        lis = []
        for ele in tup:
            if isinstance(ele, str) and ele != '':
                lis.append(_(ele))
            else:
                lis.append(ele)
        new_aggr.append(lis)
    if new_aggr == []:
        return None
    return new_aggr
