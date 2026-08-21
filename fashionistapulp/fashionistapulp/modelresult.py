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

from collections import Counter
import logging
from django.utils.translation import gettext as _

from .dofus_constants import (TYPE_NAMES, TYPE_NAME_TO_SLOT, TYPE_NAME_TO_SLOT_NUMBER, SLOTS,
                             NEUTRAL, DAMAGE_TYPES, BASE_STATS, STAT_KEY_TO_NAME,
                             calculate_damage, SLOT_NAME_TO_TYPE)
from .item_flags import flag_lines
from .spell_text import fold_spell_blocks
from .structure import get_structure, get_current_game_version
from .translation import get_supported_language
from .violation import Violation
from fashionistapulp.dofus_constants import (STAT_NAME_TO_KEY,
                                             get_stat_maximum)

RELEVANT_INPUT = ['options', 'base_stats_by_attr', 'char_level', 'origin']

logger = logging.getLogger(__name__)

class ModelResultMinimal():

    def __init__(self, item_per_slot, input_, stats):
        self.item_per_slot = item_per_slot
        self.input = input_
        self.stats = stats

    @classmethod
    def from_item_id_list(cls, item_id_list, input_, stats):
        structure = get_structure()
        
        # Determine locked slots that were honored. They might not have been if
        # the locked item is now removed, for example.
        locked_slots = {}
        item_id_list_left = list(item_id_list)
        for locked_slot, locked_id in input_['locked_equips'].items():
            for variation in structure.get_items_by_or_id(locked_id):
                if variation.id in item_id_list_left:
                    item_id_list_left.remove(variation.id)
                    locked_slots[locked_slot] = locked_id
                    break
        
        item_per_slot = {}
        open_slots = set(SLOTS)
        for item_id in item_id_list:
            item = structure.get_item_by_id(item_id)
            if item is None:
                logger.warning('Missing item in structure for item_id=%s', item_id)
                continue
            item_type = structure.get_type_name_by_id(item.type)
        
            # Define slot
            slot = None
            for open_slot in open_slots:
                if locked_slots.get(open_slot, None) == item.id:
                    slot = open_slot
                    break
            if slot is None:
                slot = TYPE_NAME_TO_SLOT[item_type]
                slot_number = TYPE_NAME_TO_SLOT_NUMBER[item_type]
                if slot_number > 1:
                    for i in range(1, slot_number + 1):
                        candidate_slot = "%s%d" % (slot, i)
                        if (candidate_slot in open_slots
                            and not locked_slots.get(candidate_slot, None)):
                            slot = candidate_slot
                            break
                        
            item_per_slot[slot] = item.id
            open_slots.remove(slot)
        return cls(item_per_slot, {k: input_[k] for k in input_ if k in RELEVANT_INPUT}, stats)

    @classmethod
    def from_model_result(cls, model_result):
        item_per_slot = {}
        for slot in SLOTS:
            item_found = [i for i in model_result.item_list if i.slot == slot]
            if item_found:
                item_per_slot[slot] = item_found[0].id
            else:
                item_per_slot[slot] = None
                
        input_ = model_result.input
        stats = model_result.get_stats()
        return cls(item_per_slot, {k: input_[k] for k in input_ if k in RELEVANT_INPUT}, stats)
    
    @classmethod
    def generate_empty_solution(cls, input_):
        input_['origin'] = 'from_scratch'
        item_per_slot = {}
        for slot in SLOTS:
            item_per_slot[slot] = None
        return cls(item_per_slot,
                   {k: input_[k] for k in input_ if k in RELEVANT_INPUT},
                   None)
    
    def update_base_stats(self, stats, scrolled):
        #if self.input.get('origin', None) == 'from_scratch':
        self.stats = {}
        for stat in stats:
            self.stats[STAT_NAME_TO_KEY[stat]] = stats[stat]
        
        for stat in scrolled:
            self.input.get('base_stats_by_attr')[stat] = scrolled[stat]

def model_result_from_minimal(minimal, stat_overrides=None):
    structure = get_structure()
    if hasattr(minimal, 'stats'):
        result = ModelResult(minimal.input, minimal.stats)
    else:
        result = ModelResult(minimal.input)

    for slot, item_id in minimal.item_per_slot.items():
        if item_id is not None and structure.get_item_by_id(item_id):
            result.add_item_at_slot(structure.get_item_by_id(item_id), slot, stat_overrides)
        else:
            if item_id is not None:
                logger.warning('Missing item in structure for slot=%s item_id=%s', slot, item_id)
            result.add_item_at_slot(None, slot)
    open_slots = []
    for slot in result.open_slots:
        open_slots.append(slot)
    for slot in open_slots:
        result.add_item_at_slot(None, slot)
    result.calculate_stats()
    return result

class ModelResult():
    
    def __init__(self, input_, stats=None):
        self.input = input_        
        
        self.items = {}
        for type_name in TYPE_NAMES:
            self.items[type_name] = []
        self.item_list = []
        self.open_slots = set(SLOTS)
        
        self.sets = []
        
        self.stats = stats
                
        self.stats_base = None
        self.stats_gear = None
        self.stats_total = None

    def add_item_at_slot(self, item, slot, stat_overrides=None):
        self._add_result_item_at_slot(slot, ModelResultItem(item, stat_overrides))
        
    def _add_result_item_at_slot(self, slot, result_item):
        result_item.set_slot(slot)
        self.open_slots.remove(slot)
        
        self.items[SLOT_NAME_TO_TYPE[slot]].append(result_item)
        self.item_list.append(result_item)

    def _add_set(self, item_set, number_of_items):
        self.sets.append(ModelResultSet(item_set, number_of_items))
        
    def add_all_sets(self):
        self.sets = []
        structure = get_structure()
        items_of_set = Counter()
        for item in self.item_list:
            if item.item_added:
                items_of_set[item.set] += 1
        for set_number, number_of_items in items_of_set.items():
            if set_number and number_of_items > 1:
                self._add_set(structure.get_set_by_id(set_number), number_of_items)
        
    def get_stats(self):
        return self.stats        
        
    def get_stats_base(self):
        if self.stats_base is None:
            if self.stats:
                self.stats_base = {k: self.stats[k]
                                   + self.input['base_stats_by_attr'][STAT_KEY_TO_NAME[k]]
                                   for k in BASE_STATS}
            else:
                self.stats_base = {k: self.input['base_stats_by_attr'][STAT_KEY_TO_NAME[k]]
                                   for k in BASE_STATS}
        return self.stats_base
        
    def get_stats_gear(self):
        if self.stats_gear is None:
            self.stats_gear = {}
            for stat in get_structure().get_stats_list():
                self.stats_gear[stat.key] = 0
            for result_item in self.item_list:
                if result_item.item_added:
                    for stat_key, stat_value in result_item.stats.items():
                        self.stats_gear[stat_key] += stat_value
            for result_set in self.sets:
                for stat_key, stat_value in result_set.get_bonus().items():
                    self.stats_gear[stat_key] += stat_value
            # One point per stat for the whole build, from the option or from
            # a worn piece that carries one, never from both and never twice.
            worn_exos = set()
            for result_item in self.item_list:
                if result_item.item_added:
                    worn_exos.update(getattr(result_item, 'exo_overrides', {}))
            options = self.input['options']
            if options['ap_exo'] or 'ap' in worn_exos:
                self.stats_gear['ap'] += 1
            if ('range_exo' in options and options['range_exo']) or 'range' in worn_exos:
                self.stats_gear['range'] += 1
            # 'gelano' is not this point: that choice swaps in Gelano (#1),
            # whose own MP is already in the sum above.
            if options['mp_exo'] is True or 'mp' in worn_exos:
                self.stats_gear['mp'] += 1
        return self.stats_gear
        
    def get_stats_total(self): 
        if self.stats_total is None:
            self.stats_total = self.get_stats_gear().copy()
            structure = get_structure()
            main_stats = structure.get_main_stats_list()
            for stat in structure.get_stats_list():
                self.stats_total[stat.key] += self.input['base_stats_by_attr'].get(stat.name, 0)
                if stat in main_stats:
                    if hasattr(self, 'stats') and self.stats is not None:
                        self.stats_total[stat.key] += self.stats.get(stat.key, 0)
            self.stats_total['apres'] += self.stats_total['wis'] // 10
            self.stats_total['mpres'] += self.stats_total['wis'] // 10
            self.stats_total['apred'] += self.stats_total['wis'] // 10
            self.stats_total['mpred'] += self.stats_total['wis'] // 10
            self.stats_total['dodge'] += self.stats_total['agi'] // 10
            self.stats_total['lock'] += self.stats_total['agi'] // 10
            self.stats_total['pp'] += self.stats_total['cha'] // 10
            self.stats_total['pod'] += self.stats_total['str'] * 5
            self.stats_total['init'] += (self.stats_total['str']
                                         + self.stats_total['int']
                                         + self.stats_total['cha']
                                         + self.stats_total['agi'])
            self.stats_total['hp'] = self.stats_total['vit'] + self.input['char_level'] * 5 + 50 + self.stats_total['hp']
            # The gear may add up past the cap; the character reads the cap.
            # Retro has no cap at all, and get_stat_maximum omits the keys
            # there, so nothing is clamped on that version.
            for stat_name, cap in get_stat_maximum(
                    get_current_game_version()).items():
                key = STAT_NAME_TO_KEY.get(stat_name)
                if key in self.stats_total and self.stats_total[key] > cap:
                    self.stats_total[key] = cap
            # Apply active set caps (e.g. 6-piece Cire Momore caps MP/Summon/Range)
            for result_set in self.sets:
                for stat_key, _stat_name, max_cap in result_set.get_max_caps():
                    if stat_key in self.stats_total:
                        self.stats_total[stat_key] = min(self.stats_total[stat_key], max_cap)
        return self.stats_total
        
    def switch_item(self, item, slot, stat_overrides=None):
        result_item = ModelResultItem(item, stat_overrides)
        result_item.set_slot(slot)
        to_remove = None
        for candidate_item in self.item_list:
            if candidate_item.slot == slot:
                to_remove = candidate_item
                break
        self.items[SLOT_NAME_TO_TYPE.get(slot)].remove(to_remove)
        self.items[SLOT_NAME_TO_TYPE.get(slot)].append(result_item)
        self.item_list.remove(to_remove)
        self.item_list.append(result_item)
        s = get_structure()
        if not self._get_repeat_violations(s.get_type_id_by_name(SLOT_NAME_TO_TYPE.get(slot))):
            self.calculate_stats()
        return result_item
    
    def _get_stat_violations(self):
        violations = []
        for item in self.item_list:
            vlist = self._check_items_stat_conditions(item)
            for vio in vlist:
                violations.append(vio)
        return violations
    
#     def _get_item_shield_violation(self, item_result):
#         violations = []
# 
#         if not item_result.item_added:
#             return violations
#         
#         violates = False
#         if item_result.type == 'Weapon':
#             shield = self.items['Shield'][0]
#             if shield.item_added:
#                 if not item_result.is_one_handed:
#                     violates = True
#                     
#         if item_result.type == 'Shield':
#             weapon = self.items['Weapon'][0]
#             if weapon.item_added:
#                 if not weapon.is_one_handed:
#                     violates = True
#         
#         if violates:
#             violation = Violation()
#             violation.item_name = item_result.localized_name
#             violation.stat_name = _("Can't equip a two handed weapon and a shield.")
#             violation.condition_type = 'shield'
#             violation.is_red = True
#             violation.cant_equip = False
#             violations.append(violation)
#         return violations
    def _create_removed_item_violation(self, item):    
        violation = Violation()
        violation.item_name = item.localized_name
        violation.is_red = True
        violation.condition_type = 'removed'
        return violation
                    
    def _check_items_stat_conditions(self, item_result):  
        violations = []
        s = get_structure()  
        if not item_result.item_added:
            return violations
        if item_result.min_stats_to_equip:
            for stat_key, value in item_result.min_stats_to_equip.items():
                if self.stats_total[stat_key] < value:
                    stat_name = _(s.get_stat_by_key(stat_key).name)
                    violation = Violation()
                    violation.item_name = item_result.localized_name
                    violation.stat_name = stat_name
                    violation.stat_value = value
                    violation.is_red = True
                    violation.condition_type = 'min'
                    violation.cant_equip = False
                    violations.append(violation)
                    
        if item_result.max_stats_to_equip:
            for stat_key, value in item_result.max_stats_to_equip.items():
                if self.stats_total[stat_key] > value:
                    stat_name = _(s.get_stat_by_key(stat_key).name)
                    violation = Violation()
                    violation.item_name = item_result.localized_name
                    violation.stat_name = stat_name
                    violation.stat_value = value
                    violation.is_red = True
                    violation.condition_type = 'max'
                    violation.cant_equip = False
                    violations.append(violation)
        return violations
        
    def _get_repeat_violations(self, item_type_id):
        violations = []
        s = get_structure()
        item_type = s.get_type_name_by_id(item_type_id)
        if len(self.items[item_type]) > 1:
            dict_names = {}
            for item in self.items[item_type]:
                if item.item_added:
                    or_name = s.get_or_item_name(item.name)
                    dict_names.setdefault(or_name, []).append(item.name)
            for (name, occurrences) in dict_names.items():
                if len(occurrences) > 1:
                    item_name = occurrences[0]
                    if (s.get_item_by_name(item_name).type == s.get_type_id_by_name('Dofus')
                        or s.get_item_by_name(item_name).set):
                        violation = Violation()
                        violation.is_red = True
                        violation.item_name = name
                        violation.condition_type = 'repeated'
                        violation.cant_equip = True
                        violations.append(violation)
        return violations

    def _get_min_violations(self, min_stats):
        violations = []
        s = get_structure()
        for stat_key, min_val in min_stats.items():
            if stat_key != 'adv_mins':
                if self.stats_total[stat_key] < min_val:
                    stat_name = _(s.get_stat_by_key(stat_key).name)
                    violation = Violation()
                    violation.item_name = _('project')
                    violation.stat_name = stat_name
                    violation.stat_value = min_val
                    violation.condition_type = 'min_eq'
                    violation.cant_equip = False
                    violations.append(violation)
            else: 
                composite_mins = s.get_adv_mins() 
                for stat in composite_mins:
                    stat_found = stat['key'] in min_val or stat['name'] in min_val
                    if stat_found:
                        required_min = min_val.get(stat['key'], min_val.get(stat['name']))
                        char_stat = 0
                        debug_info = []
                        for attribute in stat['stats']:
                            val = self.stats_total[STAT_NAME_TO_KEY[attribute]]
                            original_val = val
                            if attribute.strip().startswith('%') and attribute.strip().endswith('Resist'):
                                val = min(val, 50)
                                if original_val != val:
                                    debug_info.append(f"{attribute}: {original_val}→{val}")
                            char_stat += val
                        if char_stat < required_min:
                            violation = Violation()
                            violation.item_name = _('project')
                            stat_name = stat['local_name']
                            if debug_info:
                                stat_name += f" (capped: {', '.join(debug_info)})"
                            violation.stat_name = stat_name
                            violation.stat_value = required_min
                            violation.condition_type = 'min_eq'
                            violation.cant_equip = False
                            violations.append(violation)
        return violations

    def _get_removed_item_violations(self):
        violations = []
        for item in self.item_list:
            if item.item_added:  
                if item.removed:
                    violation = Violation()
                    violation.item_name = item.localized_name
                    violation.condition_type = 'removed'
                    violation.is_red = True
                    violation.cant_equip = False
                    violations.append(violation)
        return violations

    def _get_weird_violations(self):
        violations = []

        is_set_light = self.check_if_set_is_light()
        if not is_set_light:
            for item in self.item_list:
                if item.item_added:  
                    if item.weird_conditions['light_set']:
                        cap = item.weird_conditions['light_set']
                        cap = 2 if cap is True else cap
                        violation = Violation()
                        violation.item_name = item.localized_name
                        violation.stat_name = (_("Set bonus < 2") if cap <= 1
                                               else _("Set bonus < 3"))
                        violation.condition_type = 'weird_light_set'
                        violation.is_red = True
                        violation.cant_equip = False
                        violations.append(violation)

        is_prysmaradite = self.check_if_prysmaradite()
        if not is_prysmaradite:
            for item in self.item_list:
                if item.item_added and item.weird_conditions['prysmaradite']:
                    violation = Violation()
                    violation.is_red = True
                    violation.item_name = item.localized_name
                    violation.stat_name = _("Prysmaradite < 1")
                    violation.condition_type = 'weird_prysmaradite'
                    violation.cant_equip = True
                    violations.append(violation)

        return violations
    
#     def _get_shield_violation(self):
#         violations = []
# 
#         weapon_two_handed = False
#         has_shield = False
#         for item in self.item_list:
#             if item.item_added:
#                 if item.type == 'Shield':
#                     has_shield = True
#                 elif item.type == 'Weapon':
#                     if not item.is_one_handed:
#                         weapon_two_handed = True
#         if weapon_two_handed and has_shield:
#             violation = Violation()
#             violation.item_name = item.localized_name
#             violation.stat_name = _("Can't equip a two handed weapon and a shield.")
#             violation.condition_type = 'shield'
#             violation.is_red = True
#             violation.cant_equip = False
#             violations.append(violation)
#         return violations
    
    def check_if_set_is_light(self):
        is_set_light = (len(self.sets) == 0 or
                        (len(self.sets) == 1 and self.sets[0].number_of_items <= 3) or
                        (len(self.sets) == 2 and self.sets[0].number_of_items <= 2 and self.sets[1].number_of_items <= 2))
        return is_set_light
    
    def check_if_prysmaradite(self):
        prysmaradite_count = sum(1 for item in self.item_list if item.item_added and item.weird_conditions['prysmaradite'])
        return prysmaradite_count <= 1


    def get_all_project_violations(self, item_type_id, min_stats):
        return (self._get_repeat_violations(item_type_id)
                + self._get_stat_violations()
                + self._get_min_violations(min_stats)
                + self._get_weird_violations()
                + self._get_removed_item_violations())
#                + self._get_shield_violation())
    
    def get_violations_on_item(self, item):
        violations = []
        if item.removed:
            violations.append(self._create_removed_item_violation(item))
        for vio in self._check_items_stat_conditions(item):
            violations.append(vio)
        if item.weird_conditions['light_set']:
            if not self.check_if_set_is_light():
                cap = item.weird_conditions['light_set']
                cap = 2 if cap is True else cap
                violation = Violation()
                violation.item_name = item.localized_name
                violation.stat_name = (_("Set bonus < 2") if cap <= 1
                                       else _("Set bonus < 3"))
                violation.condition_type = 'weird_light_set'
                violation.is_red = True
                violation.cant_equip = False
                violations.append(violation)
        if item.weird_conditions['prysmaradite']:
            if not self.check_if_prysmaradite():
                violation = Violation()
                violation.item_name = item.localized_name
                violation.stat_name = _("Prysmaradite < 1")
                violation.condition_type = 'weird_prysmaradite'
                violation.is_red = True
                violation.cant_equip = True
                violations.append(violation)
        item_type_id = get_structure().get_type_id_by_name(item.type)
        repeat = self._get_repeat_violations(item_type_id)
        for vio in repeat:
            if vio.item_name == item.name:
                violations.append(vio)
#        shield = self._get_item_shield_violation(item)
#         for vio in shield:
#             if vio.item_name == item.name:
#                 violations.append(vio)
        return violations
    
    def calculate_stats(self):
        self.sets = []
        self.stats_gear = None
        self.stats_total = None
        
        self.add_all_sets()
        self.get_stats_gear()
        self.get_stats_total()
        if self.items['Weapon'] and self.items['Weapon'][0].item_added:
            self.items['Weapon'][0].mage_weapon_smartly(self.get_stats_total())


class ModelResultItem():

    def __init__(self, item, stat_overrides=None):
        # Legacy pickles can be missing the newer weapon fields.
        self.is_mageable = False
        if item:
            structure = get_structure()
            self.item_added = True
            self.id = item.id
            self.name = item.name
            self.or_name = (item.or_name if item.or_name else item.name)
            self.type = structure.get_type_name_by_id(item.type)
            self.level = item.level
            self.set = item.set
            self.ankama_id = item.ankama_id
            self.ankama_type = item.ankama_type
            or_item = structure.get_or_item_by_name(item.name)
            if or_item:
                any_or_item = or_item[0]
                self.removed = any_or_item.removed
            else:
                self.removed = item.removed
#            self.is_one_handed = item.is_one_handed
            self.slot = None
            if get_supported_language() in item.localized_names:
                self.localized_name = item.localized_names[get_supported_language()]
            else:
                self.localized_name = or_item[0].localized_names[get_supported_language()]
            # Several set pieces share a name (the four retro wedding rings, one
            # per elemental set).
            self.localized_set_name = None
            if item.set is not None:
                item_set = structure.get_set_by_id(item.set)
                if item_set is not None:
                    self.localized_set_name = (
                        item_set.localized_names.get(get_supported_language())
                        or item_set.name)

            self.weird_conditions = item.weird_conditions
    
            self.stats = {}
            self.base_stats = {}
            # An item can list the same stat twice (retro Minotot Sceptre:
            # 6% + 6% Water Resist); in game the two lines stack.
            self.stat_ranges = {}
            item_ranges = getattr(item, 'stat_ranges', {}) or {}
            for stat_id, stat_value in item.stats:
                stat = structure.get_stat_by_id(stat_id)
                self.stats[stat.key] = self.stats.get(stat.key, 0) + stat_value
                self.base_stats[stat.key] = self.base_stats.get(stat.key, 0) + stat_value
                low, high = item_ranges.get(stat_id, (stat_value, stat_value))
                previous_low, previous_high = self.stat_ranges.get(stat.key, (0, 0))
                self.stat_ranges[stat.key] = (previous_low + low, previous_high + high)
            self.stat_ranges = {key: bounds
                                for key, bounds in self.stat_ranges.items()
                                if bounds[0] != bounds[1]}

            _EXO_KEYS = {'ap', 'mp', 'range'}
            self.exo_overrides = {}
            if stat_overrides and item.id in stat_overrides:
                for stat_id, override_val in stat_overrides[item.id].items():
                    stat = structure.get_stat_by_id(stat_id)
                    if stat:
                        if stat.key in _EXO_KEYS and override_val > self.stats.get(stat.key, 0):
                            # get_stats_gear() already adds the exo +1 from the
                            # ap_exo/mp_exo/range_exo options.
                            self.exo_overrides[stat.key] = override_val
                        else:
                            self.stats[stat.key] = override_val

            self.min_stats_to_equip = {}
            for stat_id, stat_value in item.min_stats_to_equip:
                self.min_stats_to_equip[structure.get_stat_by_id(stat_id).key] = stat_value
            self.max_stats_to_equip = {}
            for stat_id, stat_value in item.max_stats_to_equip:
                self.max_stats_to_equip[structure.get_stat_by_id(stat_id).key] = stat_value
            
    
            localized_extras = item.localized_extras.get(get_supported_language())
            if localized_extras is None:
                localized_extras = ['[!] ' + line for line in item.localized_extras.get('en', [])]
            translated_flags = flag_lines(getattr(item, 'flags', []))
            localized_extras, folded = fold_spell_blocks(localized_extras)
            self.extras = translated_flags + [(line, None) for line in localized_extras]
            # An extra line names a spell without saying what it does.
            self.spell_tooltips = dict(
                getattr(item, 'spell_tooltips', {}).get(get_supported_language()) or {},
                **folded)
    
            if self.type == 'Weapon':
                # Retro and Touch let several weapons share a name, so match on
                # the item first.
                weapon = (structure.get_weapon_for_item(item)
                          or structure.get_weapon_by_name(self.name))
                if weapon is not None:
                    self.is_mageable = weapon.is_mageable
                    self.non_crit_hits = weapon.non_crit_hits
                    self.crit_hits = weapon.crit_hits
                    self.crit_bonus = weapon.crit_bonus
                    self.crit_chance = weapon.crit_chance_percent
                    self.ap = weapon.ap
                    self.uses_per_turn = weapon.uses_per_turn
                    weapon_type = structure.get_weapon_type_by_id(weapon.weapon_type)
                    self.weapon_type = weapon_type.name if weapon_type is not None else "DefaultName"
                else:
                    logger.warning('Missing weapon metadata for item_id=%s item_name=%s', self.id, self.name)
        else:
            self.name = 'NoItem'
            self.id = None
            self.localized_name = None
            self.item_added = False
            # evolve_result_item reads .slot and .file even for an empty slot
            self.slot = None
            self.file = None
            
    def set_slot(self, slot):
        self.slot = slot
        if not self.localized_name:
            self.localized_name = _(SLOT_NAME_TO_TYPE[slot])
        
    def mage_weapon_smartly(self, char_stats):
        if getattr(self, 'is_mageable', False):
            calculated_damage = {}
            for element in DAMAGE_TYPES:
                calculated_damage[element] = calculate_damage(self.non_crit_hits[element],
                                                              char_stats, critical_hit=False, is_spell=False)
                
            if any([hit.heals for hit in self.non_crit_hits[NEUTRAL]]):
                lowest_dam = 999999
                element_chosen = None
                for element, damage in calculated_damage.items():
                    total_average_dam = sum([d.average() for d in damage])
                    if total_average_dam < lowest_dam:
                        lowest_dam = total_average_dam
                        element_chosen = element
                self.element_maged = element_chosen
            else:
                highest_dam = -999999
                element_chosen = None
                for element, damage in calculated_damage.items():
                    total_average_dam = sum([d.average() for d in damage])
                    if total_average_dam > highest_dam:
                        highest_dam = total_average_dam
                        element_chosen = element
                self.element_maged = element_chosen
            
            

class ModelResultSet():

    def __init__(self, item_set, number_of_items):
        structure = get_structure()
        self.id = item_set.id
        self.name = item_set.name
        self.total_number_of_items = structure.get_number_of_items_in_set_by_id(item_set.id)
        self.number_of_items = number_of_items
        self.bonus_per_num_items = item_set.bonus_per_num_items
        self.raw_max_caps = item_set.max_caps  # list of (num_items, stat_id, max_value)
        self.items = []
        for item_id in item_set.items:
            item = structure.get_item_by_id(item_id)
            self.items.append(ModelResultItem(item))
        self.localized_name = item_set.localized_names[get_supported_language()]

    def get_bonus(self):
        # Many Retro sets define no bonus for a given piece count: wearing that
        # many pieces grants nothing, it is not an error.
        return self.bonus_per_num_items.get(self.number_of_items, {})

    def get_max_caps(self):
        structure = get_structure()
        caps = []
        for num_items, stat_id, max_value in self.raw_max_caps:
            if num_items == self.number_of_items:
                stat = structure.get_stat_by_id(stat_id)
                if stat:
                    caps.append((stat.key, stat.name, max_value))
        return caps


class ModelResultStat():
    
    def __init__(self, stat, value):
        self.stat = stat
        self.value = value
