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

from django.conf import settings
from django.utils.translation import gettext as _
import json

from chardata.image_store import get_image_url
from fashionistapulp.dofus_constants import NEUTRAL, STAT_ORDER,\
    SLOT_NAME_TO_TYPE
from fashionistapulp.fashion_util import normalize_name
from fashionistapulp.structure import get_structure
from chardata.stat_icons import get_stat_icon_path
from static_s3.templatetags.static_s3 import static
from .translation_util import LOCALIZED_ELEMENTS, LOCALIZED_WEAPON_TYPES
from chardata.official_site import get_item_link


class SolutionResult:
    
    def __init__(self, model_result, inclusions={}, exclusions=[]):
        self.model_result = model_result
        self.inclusions = inclusions
        self.exclusions_set = set(exclusions)
                   
    def get_params(self):
        r = self.model_result 

        def split_into_columns(items, column_count):
            return [items[index::column_count] for index in range(column_count)]
        
        item_list_ordered = []
        item_list_ordered.extend(r.items['Weapon'])
        item_list_ordered.extend(r.items['Hat'])
        item_list_ordered.extend(r.items['Cloak'])
        item_list_ordered.extend(r.items['Amulet'])
        item_list_ordered.extend(r.items['Ring'])
        item_list_ordered.extend(r.items['Boots'])
        item_list_ordered.extend(r.items['Belt'])
        item_list_ordered.extend(r.items['Shield'])
        item_list_ordered.extend(r.items['Pet'])
        item_columns = split_into_columns(item_list_ordered, 6)
        
        dofus_list = r.items['Dofus']
        dofus_columns = split_into_columns(dofus_list, 6)
        
        item_sections = [item_columns, dofus_columns]
        all_items = item_list_ordered + dofus_list
        item_per_slot = {}
        
        # TODO: Grafting this attribute is a hack.
        item_is_locked = {}
        item_is_forbidden = {}
        item_names = {}
        translated_item_names = {}
        item_violates = {}
        for result_item in all_items:
            evolve_result_item(result_item, r)
            
        for result_item in all_items:
            item_per_slot[result_item.slot] = result_item
            item_is_locked[result_item.slot] = self.is_item_locked(result_item)
            item_is_forbidden[result_item.slot] = self.is_item_forbidden(result_item)
            item_names[result_item.slot] = (result_item.or_name 
                                            if result_item.item_added 
                                            else _(SLOT_NAME_TO_TYPE[result_item.slot]))
            translated_item_names[result_item.slot] = (result_item.localized_name 
                                            if result_item.item_added 
                                            else _(SLOT_NAME_TO_TYPE[result_item.slot]))
            s = get_structure()
            item_violates[result_item.slot] = False
            if result_item.item_added and len(r.get_violations_on_item(result_item)) > 0:
                item_violates[result_item.slot] = True
                
                
        # TODO: Grafting this attribute is a hack.
        for result_set in r.sets:
            stats_from_result_set = sorted(iter(result_set.get_bonus().items()),
                                           key=lambda x: STAT_ORDER[x[0]])
            
            result_set.stats_lines = []
            for stat_key, stat_value in stats_from_result_set:
                stat_name = get_structure().get_stat_by_key(stat_key).name
                result_set.stats_lines.append(AttributeLine(stat_key, stat_value, stat_name))
                           
            # This is a dict to handle cases like Air Bwaks, that can be multiple different
            # items, but we only want to display one.
            result_set.parts = {}
            for result_item in result_set.items:
                if result_item.item_added:
                    item_file = get_image_url(result_item.type, result_item.name)
                    if item_file not in result_set.parts:
                        used_in_set = any([result_item.id == item.id for item in all_items])
                        result_set.parts[item_file] = (normalize_name(result_item.localized_name),
                                                       _(result_item.type),
                                                       used_in_set)

        params = {'item_sections': item_sections,
                  'sets': r.sets,
                  'all_items': all_items,
                  'stats_base_json': json.dumps(r.get_stats_base()),
                  'stats_gear_json': json.dumps(r.get_stats_gear()),
                  'stats_total_json': json.dumps(r.get_stats_total()),
                  'item_names': json.dumps(item_names),
                  'translated_item_names': json.dumps(translated_item_names),
                  'item_is_locked': json.dumps(item_is_locked),
                  'item_is_forbidden': json.dumps(item_is_forbidden),
                  'item_violates': json.dumps(item_violates),
                  'options_json': json.dumps(r.input['options']),
                  'item_per_slot': item_per_slot,
                  'is_generated': (r.input.get('origin', 'generated') == 'generated'),}
        return params

    def is_item_locked(self, result_item):
        if result_item.item_added:
            return self.inclusions.get(result_item.slot, '') == result_item.or_name
        
    def is_item_forbidden(self, result_item):
        if result_item.item_added:
            return result_item.or_name in self.exclusions_set


def evolve_result_item(result_item, r=None):
    if result_item.slot:
        result_item.file = static('chardata/%s.png' % SLOT_NAME_TO_TYPE[result_item.slot])
    if not result_item.item_added:
        if not result_item.file:
            print('No item and no slot for picture.')
        return
    stats_from_result_item = sorted(iter(result_item.stats.items()),
                                    key=lambda x: STAT_ORDER[x[0]])
    
    result_item.stats_lines = []
    for stat_key, stat_value in stats_from_result_item:
        stat_name = get_structure().get_stat_by_key(stat_key).name
        result_item.stats_lines.append(AttributeLine(stat_key, stat_value, stat_name))
    for extra in result_item.extras:
        result_item.stats_lines.append(ExtraLine(extra))

    result_item.condition_lines = []

    if hasattr(result_item, 'min_stats_to_equip'):
        min_from_result_item = sorted(iter(result_item.min_stats_to_equip.items()),
                                      key=lambda x: STAT_ORDER[x[0]])
        for stat_key, stat_value in min_from_result_item:
            stat_name = get_structure().get_stat_by_key(stat_key).name
            result_item.condition_lines.append(MinConditionLine(stat_key, stat_value, stat_name, r))

    if hasattr(result_item, 'max_stats_to_equip'):
        max_from_result_item = sorted(iter(result_item.max_stats_to_equip.items()),
                                      key=lambda x: STAT_ORDER[x[0]])
        for stat_key, stat_value in max_from_result_item:
            stat_name = get_structure().get_stat_by_key(stat_key).name
            result_item.condition_lines.append(MaxConditionLine(stat_key, stat_value, stat_name, r))

    if result_item.weird_conditions['light_set']:
        result_item.condition_lines.append(LightSetConditionLine(r))

    if result_item.weird_conditions['prysmaradite']:
        result_item.condition_lines.append(PrysmaraditeConditionLine(r))

    if hasattr(result_item, 'non_crit_hits'):
        damage_lines = []
        weapon_type_key = result_item.weapon_type
        if weapon_type_key not in LOCALIZED_WEAPON_TYPES:
            # Handle the missing key case
            # e.g., use a default value or log an error
            localized_weapon_type = "Unknown Weapon Type"  # replace with an appropriate default
        else:
            localized_weapon_type = LOCALIZED_WEAPON_TYPES[weapon_type_key]

        if result_item.crit_chance is not None and result_item.crit_bonus is not None:
            damage_lines.append(_('(%(weapon_type)s) AP: %(AP)d / CH: %(crit_chance)d%% (+%(crit_bonus)d)')
                                  % {'weapon_type': localized_weapon_type,
                                     'AP': result_item.ap,
                                     'crit_chance': result_item.crit_chance,
                                     'crit_bonus': result_item.crit_bonus})
        else:
            damage_lines.append(_('(%(weapon_type)s) AP: %(AP)d')
                                  % {'weapon_type': result_item.weapon_type,
                                     'AP': result_item.ap})
        for hit in result_item.non_crit_hits[NEUTRAL]:
            if hit.steals:
                line = _('%(min)d to %(max)d (%(element)s steal)' ) % {'min': hit.min_dam, 
                            'max': hit.max_dam,
                            'element': LOCALIZED_ELEMENTS[hit.element]}
            elif hit.heals:
                if hasattr(hit, 'element') and hit.element in LOCALIZED_ELEMENTS:
                    line = _('%(min)d to %(max)d %(element)s heals' ) % {
                        'min': hit.min_dam,
                        'max': hit.max_dam,
                        'element': LOCALIZED_ELEMENTS[hit.element]
                    }
                else:
                    line = _('%(min)d to %(max)d (HP restored)' ) % {'min': hit.min_dam,
                                'max': hit.max_dam}
            elif hasattr(hit, 'element') and hit.element == 'pushes':
                if hit.min_dam == hit.max_dam:
                    line = _('Pushes %(cells)d cells') % {'cells': hit.min_dam}
                else:
                    line = _('Pushes %(min)d to %(max)d cells') % {'min': hit.min_dam, 'max': hit.max_dam}
            elif hasattr(hit, 'element') and hit.element == 'attracts':
                if hit.min_dam == hit.max_dam:
                    line = _('Attracts %(cells)d cells') % {'cells': hit.min_dam}
                else:
                    line = _('Attracts %(min)d to %(max)d cells') % {'min': hit.min_dam, 'max': hit.max_dam}
            elif hasattr(hit, 'element') and hit.element == 'steals' and not hit.steals:
                if hit.min_dam == hit.max_dam:
                    line = _('Steals %(kamas)d kamas') % {'kamas': hit.min_dam}
                else:
                    line = _('Steals %(min)d to %(max)d kamas') % {'min': hit.min_dam, 'max': hit.max_dam}
            else:
                line = _('%(min)d to %(max)d (%(element)s)' ) % {'min': hit.min_dam, 
                            'max': hit.max_dam,
                            'element': LOCALIZED_ELEMENTS.get(getattr(hit, 'element', None), 'DefaultElement')}
            damage_lines.append(line)
        result_item.damage_text = '<br>'.join(damage_lines)

    result_item.file = static(get_image_url(result_item.type, result_item.name))
    if settings.EXPERIMENTS['ITEM_LINKS']:
        result_item.link = get_item_link(result_item.ankama_type,
                                         result_item.ankama_id,
                                         result_item.localized_name)

class AttributeLine:
    
    def __init__(self, stat_key, stat_value, stat_name):
        # Round stat value to nearest integer to avoid floating-point precision issues
        rounded_value = int(round(stat_value))
        self.text = ('%d%s%s'
                     % (rounded_value,
                        '' if stat_name.startswith('%') else ' ',
                        _(stat_name)))
        self.formatting = '#r' if stat_value < 0 else ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None

class ExtraLine:
    
    def __init__(self, line):
        self.text = line
        self.formatting = ''

class MinConditionLine:
    
    def __init__(self, stat_key, stat_value, stat_name, model_result):
        self.text = ('%s > %d'
                     % (_(stat_name),
                        stat_value - 1))
        self.formatting = ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None
        if model_result:
            s = get_structure()
            stat = s.get_stat_by_name(stat_name)
            if model_result.stats_total[stat.key] < stat_value:
                self.formatting = '#r'

class MaxConditionLine:
    
    def __init__(self, stat_key, stat_value, stat_name, model_result):
        self.text = ('%s < %d'
                     % (_(stat_name),
                        stat_value + 1))
        self.formatting = ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None
        if model_result:
            s = get_structure()
            stat = s.get_stat_by_name(stat_name)
            if model_result.stats_total[stat.key] > stat_value:
                self.formatting = '#r'

class LightSetConditionLine:

    def __init__(self, model_result):
        self.text = _('Set bonus < 3')
        self.formatting = ''
        if model_result:
            if not model_result.check_if_set_is_light():
                self.formatting = '#r'

class PrysmaraditeConditionLine:

    def __init__(self, model_result):
        self.text = _('Prysmaradite < 1')
        self.formatting = ''
        if model_result:
            if not model_result.check_if_prysmaradite():
                self.formatting = '#r'
