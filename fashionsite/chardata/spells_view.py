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
from chardata.image_store import get_image_url, list_static_dir
from chardata.models import Char
from chardata.solution import get_solution
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_localization import get_localized_spell_name
from chardata.util import set_response, get_char_or_raise
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from static_s3.templatetags.static_s3 import static
from django.utils.translation import gettext as _
from fashionistapulp.translation import get_supported_language

from fashionistapulp.dofus_constants import (DAMAGE_TYPES, NEUTRAL,
                                             NON_ELEMENTAL_HIT_TYPES)

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
        if weapon.item_added and hasattr(weapon, 'non_crit_hits'):
            web_digest = _create_weapon_web_digest(weapon)
            digests.append(web_digest)
    game_version = getattr(request, 'game_version', 'dofus3')
    spells_by_class = get_damage_spells_for_version(game_version)
    class_spells = spells_by_class.get(char_class, [])
    for spell in class_spells + spells_by_class.get('default', []):
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
                         # The page must call a hit type non-elemental exactly
                         # where the damage formula does.
                         'non_elemental_hits_json': jsonpickle.encode(
                             list(NON_ELEMENTAL_HIT_TYPES), unpicklable=False),
                         'char_id': char_id,
                         'char_level': char.level,
                         'char_stats_json': stats_json,
                         'best_combo': _best_combo(char, solution, game_version),
                         'no_class_spells': len(class_spells) == 0},
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
    web_digest['image_url'] = static(get_image_url(weapon.type, weapon.name))
    web_digest['hit_number'] = len(weapon.non_crit_hits)
    web_digest['non_crit_dams'] = _convert_weapon_damage(weapon.non_crit_hits)
    web_digest['crit_dams'] = _convert_weapon_damage(weapon.crit_hits)
    damage_indexes = []
    healing_indexes = []
    effect_indexes = []
    for i, hit_instance in enumerate(weapon.non_crit_hits[NEUTRAL]):
        if hit_instance.element in NON_ELEMENTAL_HIT_TYPES:
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


_dofus2_spell_icons = None


def _dofus2_spell_icon_names():
    """The spells Dofus 2 keeps its own icon for; the rest come from the
    Dofus 3 folder."""
    global _dofus2_spell_icons
    if _dofus2_spell_icons is None:
        _dofus2_spell_icons = frozenset(
            name[:-4] for name in list_static_dir('chardata/spells/dofus2')
            if name.endswith('.png'))
    return _dofus2_spell_icons


def _spell_image_url(spell_name, game_version):
    if game_version in ('beta', 'retro', 'touch'):
        spell_dir = 'chardata/spells/%s/' % game_version
    elif game_version == 'dofus2' and spell_name in _dofus2_spell_icon_names():
        spell_dir = 'chardata/spells/dofus2/'
    else:
        spell_dir = 'chardata/spells/'
    return static(spell_dir + spell_name + '.png')


def _weapon_castable(solution):
    """The equipped weapon as one more thing the turn can spend its AP on."""
    from chardata.spell_combo import WeaponCastable
    weapons = (getattr(solution, 'items', None) or {}).get('Weapon') or []
    if not weapons:
        return None
    weapon = weapons[0]
    if not weapon.item_added or not hasattr(weapon, 'non_crit_hits'):
        return None
    if not getattr(weapon, 'ap', 0):
        return None
    castable = WeaponCastable(weapon)
    return castable if castable.alternatives else None


def _best_combo(char, solution, game_version, buff_state=None, levels=None):
    """Best cast order for one turn, or None when there is nothing to say."""
    from chardata.spell_combo import (best_turn, buffs_in_force,
                                      castable_spells, combat_ap,
                                      stacks_in_force)
    stats = dict(solution.get_stats_total())
    for stat, delta in buffs_in_force(char.char_class, char.level,
                                      game_version, buff_state,
                                      levels).items():
        stats[stat] = stats.get(stat, 0) + delta
    ap = combat_ap(stats.get('ap'), game_version)
    spells = castable_spells(char.char_class, char.level, game_version,
                             levels=levels)
    weapon = _weapon_castable(solution)
    if weapon is not None:
        spells = spells + [weapon]
    if not ap or not spells:
        return None
    standing = stacks_in_force(char.char_class, char.level, game_version,
                               buff_state)
    total, order = best_turn(stats, spells, ap, standing=standing,
                             game_version=game_version)
    if not order:
        return None
    language = get_supported_language()
    by_name = {spell.name: spell for spell in spells}
    casts = []
    running = 0
    for name, damage in order:
        running += damage
        castable = by_name[name]
        if castable.is_spell:
            shown_name = _localized_spell_name(name, language, game_version)
            image_url = _spell_image_url(name, game_version)
        else:
            shown_name = castable.weapon.localized_name
            image_url = static(get_image_url(castable.weapon.type,
                                             castable.weapon.name))
        casts.append({'name': shown_name,
                      'image_url': image_url,
                      'ap': castable.cost,
                      'damage': int(round(damage)),
                      'running': int(round(running))})
    return {'casts': casts,
            'total': int(round(total)),
            'ap_used': sum(cast['ap'] for cast in casts),
            'ap_available': ap}


def _create_spell_web_digest(spell, game_version='dofus3'):
    web_digest = {}
    digest = spell.get_effects_digest()
    current_language = get_supported_language()
    web_digest['type'] = 'spell'
    web_digest['name'] = _localized_spell_name(spell.name, current_language, game_version)
    # 'name' is translated; the combo endpoint matches on the untranslated name.
    web_digest['canonical'] = spell.name
    web_digest['level'] = spell.level_req
    web_digest['stacks'] = spell.stacks
    web_digest['image_url'] = _spell_image_url(spell.name, game_version)
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

def best_combo_json(request, char_id=0):
    import json
    from django.http import JsonResponse
    char = get_char_or_raise(request, char_id)
    return _best_combo_response(request, char)


def best_combo_linked_json(request, encoded_char_id):
    char_id = decode_char_id(encoded_char_id)
    if char_id is None:
        raise Http404('Could not decode char id: %s' % encoded_char_id)
    char = get_object_or_404(Char, pk=char_id)
    if not char.link_shared:
        raise PermissionDenied
    return _best_combo_response(request, char)


def _best_combo_response(request, char):
    import json
    from django.http import JsonResponse
    solution = get_solution(char)
    if solution is None:
        return JsonResponse({'best_combo': None})
    def posted(key):
        try:
            value = json.loads(request.POST.get(key) or '{}')
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    game_version = getattr(request, 'game_version', 'dofus3')
    return JsonResponse({'best_combo': _best_combo(
        char, solution, game_version, posted('buff_state'),
        posted('spell_levels'))})


def spells(request, char_id=0):
    char = get_char_or_raise(request, char_id)
    return _spells(request, char, False, char_id)

def spells_linked(request, char_name, encoded_char_id):
    char_id = decode_char_id(encoded_char_id)
    if char_id is None:
        raise Http404('Could not decode char id: %s' % encoded_char_id)

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
