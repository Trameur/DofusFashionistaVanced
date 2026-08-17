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

import logging

from django.conf import settings
from django.utils.translation import gettext as _
import json

logger = logging.getLogger(__name__)

from chardata.image_store import get_image_url
from chardata.item_sources import acquisition_summary, attach_acquisition
from fashionistapulp.dofus_constants import NEUTRAL, STAT_ORDER,\
    SLOT_NAME_TO_TYPE
from fashionistapulp.fashion_util import normalize_name
from fashionistapulp.structure import get_structure, get_current_game_version
from chardata.spell_tips import spell_tip_for
from chardata.transcendence_advice import best_transcendence
from chardata.stat_icons import get_stat_icon_path
from chardata.stat_range import format_stat_range
from chardata.weapon_header import format_weapon_header, format_weapon_hit
from static_s3.templatetags.static_s3 import static
from .translation_util import LOCALIZED_ELEMENTS, LOCALIZED_WEAPON_TYPES
from chardata.official_site import get_item_link, get_set_link


class SolutionResult:

    def __init__(self, model_result, inclusions={}, exclusions=[], empty_slots=[],
                 weights=None):
        self.model_result = model_result
        self.inclusions = inclusions
        self.exclusions_set = set(exclusions)
        self.empty_slots_set = set(empty_slots)
        self.weights = weights
                   
    def get_params(self):
        r = self.model_result 
        
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
        item_columns = [item_list_ordered[::2], item_list_ordered[1::2]]
        
        dofus_list = r.items['Dofus']
        dofus_columns = [dofus_list[::2], dofus_list[1::2]]
        
        item_sections = [item_columns, dofus_columns]
        all_items = item_list_ordered + dofus_list
        item_per_slot = {}
        
        # TODO: Grafting this attribute is a hack.
        item_is_locked = {}
        item_is_forbidden = {}
        item_is_empty_locked = {}
        item_names = {}
        translated_item_names = {}
        item_violates = {}
        item_ids = {}
        for result_item in all_items:
            evolve_result_item(result_item, r)
            attach_transcendence(result_item, self.weights)
        attach_acquisition(all_items)

        for result_item in all_items:
            item_per_slot[result_item.slot] = result_item
            item_is_locked[result_item.slot] = self.is_item_locked(result_item)
            item_is_forbidden[result_item.slot] = self.is_item_forbidden(result_item)
            result_item.is_empty_locked = (not result_item.item_added
                                           and result_item.slot in self.empty_slots_set)
            item_is_empty_locked[result_item.slot] = result_item.is_empty_locked
            item_names[result_item.slot] = (result_item.or_name
                                            if result_item.item_added
                                            else _(SLOT_NAME_TO_TYPE[result_item.slot]))
            translated_item_names[result_item.slot] = (result_item.localized_name
                                            if result_item.item_added
                                            else _(SLOT_NAME_TO_TYPE[result_item.slot]))
            if result_item.item_added and result_item.id is not None:
                item_ids[result_item.slot] = result_item.id
            s = get_structure()
            item_violates[result_item.slot] = False
            if result_item.item_added and len(r.get_violations_on_item(result_item)) > 0:
                item_violates[result_item.slot] = True
                
                
        # TODO: Grafting this attribute is a hack.
        for result_set in r.sets:
            result_set.url = get_set_link(result_set.id, result_set.localized_name,
                                          game_version=get_current_game_version())
            stats_from_result_set = sorted(iter(result_set.get_bonus().items()),
                                           key=lambda x: STAT_ORDER[x[0]])

            result_set.stats_lines = []
            for stat_key, stat_value in stats_from_result_set:
                stat_name = get_structure().get_stat_by_key(stat_key).name
                result_set.stats_lines.append(AttributeLine(stat_key, stat_value, stat_name))

            for stat_key, stat_name, max_value in result_set.get_max_caps():
                result_set.stats_lines.append(CapLine(stat_key, stat_name, max_value))
                           
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
                  'acquisition_summary': acquisition_summary(all_items),
                  'stats_base_json': json.dumps(r.get_stats_base()),
                  'stats_gear_json': json.dumps(r.get_stats_gear()),
                  'stats_total_json': json.dumps(r.get_stats_total()),
                  'item_names': json.dumps(item_names),
                  'translated_item_names': json.dumps(translated_item_names),
                  'item_ids': json.dumps(item_ids),
                  'item_is_locked': json.dumps(item_is_locked),
                  'item_is_forbidden': json.dumps(item_is_forbidden),
                  'item_is_empty_locked': json.dumps(item_is_empty_locked),
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
            logger.debug('No item and no slot for picture.')
        return
    exo_overrides = getattr(result_item, 'exo_overrides', {}) or {}
    base_stats = getattr(result_item, 'base_stats', None)
    merged_stats = dict(result_item.stats)
    for stat_key, override_val in exo_overrides.items():
        merged_stats[stat_key] = override_val
    stats_from_result_item = sorted(iter(merged_stats.items()),
                                    key=lambda x: STAT_ORDER[x[0]])

    result_item.stats_lines = []
    # Absent from solutions pickled before the ranges existed.
    stat_ranges = getattr(result_item, 'stat_ranges', None) or {}
    for stat_key, stat_value in stats_from_result_item:
        stat_name = get_structure().get_stat_by_key(stat_key).name
        line = AttributeLine(stat_key, stat_value, stat_name,
                             stat_ranges.get(stat_key))
        if base_stats is not None and line.formatting == '':
            base_val = base_stats.get(stat_key)
            if base_val is None:
                if stat_value != 0:
                    line.formatting = '#b'
            elif stat_value > base_val:
                line.formatting = '#b'
            elif stat_value < base_val:
                line.formatting = '#o'
        result_item.stats_lines.append(line)
    spell_tooltips = getattr(result_item, 'spell_tooltips', None) or {}
    for extra in result_item.extras:
        if isinstance(extra, tuple):
            text, icon_key = extra
            line = ExtraLine(text)
            line.icon_url = static(icon_key) if icon_key else None
        else:
            line = ExtraLine(extra)
        line.spell_tip = spell_tip_for(line.text, spell_tooltips)
        result_item.stats_lines.append(line)

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
        result_item.condition_lines.append(
            LightSetConditionLine(r, result_item.weird_conditions['light_set']))

    if result_item.weird_conditions['prysmaradite']:
        result_item.condition_lines.append(PrysmaraditeConditionLine(r))

    if hasattr(result_item, 'non_crit_hits'):
        damage_lines = []
        weapon_type_key = result_item.weapon_type
        # Some weapons (magnifying glass, fishing rod...) have no type, so skip
        # the "(type)" prefix for them.
        localized_weapon_type = LOCALIZED_WEAPON_TYPES.get(weapon_type_key)

        header = format_weapon_header(
            get_current_game_version(), localized_weapon_type, result_item.ap,
            result_item.crit_chance, result_item.crit_bonus)
        if header:
            damage_lines.append(header)
        for hit in result_item.non_crit_hits[NEUTRAL]:
            damage_lines.append(format_weapon_hit(get_current_game_version(),
                                                  hit, LOCALIZED_ELEMENTS))
        result_item.damage_text = '<br>'.join(damage_lines)

    result_item.file = static(get_image_url(result_item.type, result_item.name))
    if settings.EXPERIMENTS['ITEM_LINKS']:
        result_item.link = get_item_link(result_item.ankama_type,
                                         result_item.ankama_id,
                                         result_item.localized_name,
                                         game_version=get_current_game_version())



def attach_transcendence(result_item, weights):
    result_item.transcendence = None
    if not result_item.item_added or not weights:
        return
    rune = best_transcendence(get_current_game_version(),
                              getattr(result_item, 'stats', None) or {}, weights,
                              result_item.type)
    if rune is None:
        return
    # Ankama names its runes in French in every client.
    result_item.transcendence = '%s: +%d %s' % (
        rune['name_fr'], rune['bonus'],
        _(get_structure().get_stat_by_key(rune['stat_key']).name))


class AttributeLine:
    
    def __init__(self, stat_key, stat_value, stat_name, stat_range=None):
        # Round stat value to nearest integer to avoid floating-point precision issues
        rounded_value = int(round(stat_value))
        self.text = ('%d%s%s'
                     % (rounded_value,
                        '' if stat_name.startswith('%') else ' ',
                        _(stat_name)))
        self.range_text = format_stat_range(*stat_range) if stat_range else None
        self.formatting = '#r' if stat_value < 0 else ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None

class ExtraLine:

    def __init__(self, line):
        self.text = line
        self.formatting = ''
        self.icon_url = None
        self.spell_tip = None

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

    def __init__(self, model_result, cap=2):
        # cap = max weighted set-bonuses the trophy allows: dofus3/beta "< 3"
        # -> 2, touch "< 2" -> 1.
        cap = 2 if cap is True else cap
        self.text = _('Set bonus < 2') if cap <= 1 else _('Set bonus < 3')
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


class CapLine:

    def __init__(self, stat_key, stat_name, max_value):
        self.text = _('Max. %(stat)s %(value)d') % {'stat': _(stat_name), 'value': max_value}
        self.formatting = '#r'
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None
