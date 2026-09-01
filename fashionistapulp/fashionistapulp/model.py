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

import hashlib
import json
import logging
from copy import deepcopy

from .game_versions import get_game_version
from .dofus_constants import TYPE_NAME_TO_SLOT_NUMBER, SLOT_NAME_TO_TYPE, get_stat_maximum, get_soft_caps_for, tier_widths_after_scroll, scrolls_push_cost_curve
from .lpproblem import LpProblem2
from .modelresult import ModelResultMinimal
import pulp
from .restrictions import Restrictions
from .structure import get_structure

from collections import Counter

logger = logging.getLogger(__name__)


class Model:

    def __init__(self, stat_overrides=None):
        self.create_structure()

        if stat_overrides:
            self._apply_stat_overrides(stat_overrides)

        self.problem = LpProblem2()
        self.restrictions = Restrictions()
        self.item_count = len(self.items_list)

        self.create_variables()
        self.create_constraints()

    _EXO_STAT_KEYS = {'ap', 'mp', 'range'}

    def _apply_stat_overrides(self, stat_overrides):
        # The piece keeps its catalogue AP, MP and Range: the extra point is an
        # exo, and an exo is worth one point for the whole build, so it is a
        # variable of its own rather than part of the piece. Remember which
        # pieces carry one, they are what makes that point available.
        self._exo_carriers = {key: set() for key in self._EXO_STAT_KEYS}
        for item_id, item_overrides in stat_overrides.items():
            for stat_id, recorded in item_overrides.items():
                stat = self.structure.get_stat_by_id(stat_id)
                if not stat or stat.key not in self._EXO_STAT_KEYS:
                    continue
                catalogue = 0
                for other_id, value in self.structure.get_item_by_id(
                        item_id).stats if self.structure.get_item_by_id(
                            item_id) else ():
                    if other_id == stat_id:
                        catalogue = value
                if recorded > catalogue:
                    self._exo_carriers[stat.key].add(item_id)

        new_items_list = []
        for item in self.items_list:
            item_overrides = stat_overrides.get(item.id)
            if item_overrides:
                item = deepcopy(item)
                new_stats = []
                seen_stat_ids = set()
                for stat_id, value in item.stats:
                    if stat_id in item_overrides:
                        stat = self.structure.get_stat_by_id(stat_id)
                        if stat and stat.key in self._EXO_STAT_KEYS:
                            new_stats.append((stat_id, min(item_overrides[stat_id], value)))
                        else:
                            new_stats.append((stat_id, item_overrides[stat_id]))
                        seen_stat_ids.add(stat_id)
                    else:
                        new_stats.append((stat_id, value))
                for stat_id, value in item_overrides.items():
                    if stat_id not in seen_stat_ids:
                        stat = self.structure.get_stat_by_id(stat_id)
                        if stat and stat.key in self._EXO_STAT_KEYS:
                            pass  # new AP/MP/Range stat = exo, handled by modify_stat_total_constraints
                        else:
                            new_stats.append((stat_id, value))
                item.stats = new_stats
            new_items_list.append(item)
        self.items_list = new_items_list
        
    def create_structure(self):
        self.structure = get_structure()
        self.stat_maximum = get_stat_maximum(
            getattr(self.structure, 'game_version', 'dofus3'))
        self.items_list = self.structure.get_available_items_list()
        self.sets_list = self.structure.get_sets_list()
        self.stats_list = self.structure.get_stats_list()
        self.main_stats_list = self.structure.get_main_stats_list()

    def create_variables(self):
        self.create_item_number_variables()
        self.create_item_presence_variables()
        self.create_set_variables()
        self.create_stat_total_variables()
        self.create_stat_points_variables()
        self.create_light_set_variables()
        self.create_prysmaradite_variables()
        self.create_capped_resistance_variables()
    
    def create_capped_resistance_variables(self):
        adv_mins = self.structure.get_adv_mins()
        for stat in adv_mins:
            is_percent_resist_sum = all(stat_name.strip().startswith('%') and stat_name.strip().endswith('Resist') 
                                      for stat_name in stat['stats'])
            if is_percent_resist_sum:
                for stat_name in stat['stats']:
                    stat_obj = self.structure.get_stat_by_name(stat_name)
                    var_id = f"capped_{stat_obj.key}"
                    self.problem.setup_variable('capped_resist', var_id, 0, 50)
    
    def create_item_number_variables(self):
        # Dofus 2/3 allow two copies of a setless ring; Retro 1.29 never allows the same ring twice.
        # The rule comes from the version registry rather than from the type's
        # displayed name: 'Ring' is also what Wakfu calls one of its own types,
        # so a name test would have handed Wakfu a Dofus rule the moment its
        # items were filed under their real names.
        rings_can_double = get_game_version(self.structure.game_version).rings_can_double
        for item in self.items_list:
            doublable = (rings_can_double
                         and self.structure.get_type_name_by_id(item.type) == 'Ring'
                         and item.set is None)
            max_number = 2 if doublable else 1
            self.problem.setup_variable('x', item.id, 0, max_number)
    
    def create_item_presence_variables(self):
        for item in self.items_list:
            self.problem.setup_variable('p', item.id, 0,  1)
    
    def create_set_variables(self):
        self.set_count = len(self.sets_list)     
     
        for item_set in self.sets_list:
            self.problem.setup_variable('s', item_set.id, 0, 9)
            for slot_number in range(0, 10):
                self.problem.setup_variable('ss', '%d_%d' % (item_set.id, slot_number), 0, 1)    

    def create_stat_total_variables(self):
        self.stat_count = len(self.stats_list)

        # A set cap can sit below the character's base (6-piece Cire Momore caps MP at 2, base is 3),
        # so a capped stat needs an overage variable.
        self._capped_stat_ids = set()
        for item_set in self.sets_list:
            if not item_set.max_caps:
                continue
            for num_items, stat_id, max_value in item_set.max_caps:
                stat = self.structure.get_stat_by_id(stat_id)
                if stat and stat.name in self.stat_maximum:
                    self._capped_stat_ids.add(stat_id)

        for stat in self.stats_list:
            if stat.name in self.stat_maximum:
                self.problem.setup_variable('stat', stat.id, None, self.stat_maximum[stat.name])
                # What the gear actually adds up to, which the cap does not
                # limit: 13 AP of gear is equippable and the sheet reads 12.
                self.problem.setup_variable('total', stat.id, None, None)
                # 1 when the total is over the cap, so the stat sits at the cap.
                self.problem.setup_variable('capped', stat.id, 0, 1)
            else:
                self.problem.setup_variable('stat', stat.id, None, None)

        for stat_id in self._capped_stat_ids:
            stat = self.structure.get_stat_by_id(stat_id)
            if stat and stat.name in self.stat_maximum:
                self.problem.setup_variable('overage', stat_id, 0, self.stat_maximum[stat.name])

        # One exo point per stat for the whole build, wherever it comes from.
        for stat in self.stats_list:
            if stat.key in self._EXO_STAT_KEYS:
                self.problem.setup_variable('exo', stat.id, 0, 1)

    def create_stat_points_variables(self):
        self.stat_count = len(self.stats_list)
        
        for stat in self.main_stats_list:
            for i in range(0, 6):
                self.problem.setup_variable('stat_point', 'statpoint_%d_%d' % (i, stat.id), 0, None)  
            for i in range(0, 5):  
                self.problem.setup_variable('stat_point_max', 'statpointmax_%d_%d' % (i, stat.id), 0, 1)  
    
    def create_light_set_variables(self):
        self.problem.setup_variable('ytrophy', 1, 0,  1)
        self.problem.setup_variable('ytrophy', 2, 0,  1)
        self.problem.setup_variable('trophies', 1, 0,  1)

    def create_prysmaradite_variables(self):
        self.problem.setup_variable('prysmaradite', 1, 0,  1)
        
        
    def add_weird_item_weights_to_objective_funcion(self, objective_values, level):
        # These weights name Dofus 3 items; other versions don't ship them and the lookups return None.
        if getattr(self.structure, 'game_version', 'dofus3') not in ('dofus3', 'beta'):
            return

        combat_stats = ('dam', 'hp', 'ap', 'mp', 'ch', 'permedam', 'perrandam',
                        'str', 'int', 'agi', 'pow', 'heals', 'trocadeur')
        if not any(objective_values.get(s, 0) for s in combat_stats):
            return

        #Crimson Dofus
        #Deep Crimson: When attacked, the bearer gains 1% final damage for 2 turns (stackable 10 times).
        crimson_dofus_new_stat_weight = objective_values.get('permedam', 0) * 7 + objective_values.get('perrandam', 0) * 7
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Crimson Dofus').id, 
                               crimson_dofus_new_stat_weight)
        
        #Adding more weight to Emerald Dofus equivalent to 0.5 * level HP
        #At the end of the turn, gives 100% of the owner's level in shield points for each adjacent enemy.\nSummons are not counted.
        emerald_dofus_new_stat_weight = objective_values.get('hp', 0) * 0.5 * level
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Emerald Dofus').id, 
                               emerald_dofus_new_stat_weight)
        
        #Adding more weight to Turquoise Dofus equivalent to 5 CH
        #For each Critical Hit inflicted, the final damage is increased by 1% for 3 turns. Can be stacked 10 times.
        turq_dofus_new_stat_weight = objective_values.get('ch', 0) * 5   
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Turquoise Dofus').id, 
                               turq_dofus_new_stat_weight)
        
        #adding random stats to dofusteuse 75 per stat average
        #Increases one elemental characteristic per game turn: 300 to Chance, then 300 to Strength, then 300 to Agility, and then 300 to Intelligence.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Dofusteuse').id, 
                               objective_values.get('agi', 0) * 75)
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Dofusteuse').id, 
                               objective_values.get('cha', 0) * 75)
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Dofusteuse').id, 
                               objective_values.get('int', 0) * 75)
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Dofusteuse').id, 
                               objective_values.get('str', 0) * 75)
        
        #Adding more weight to Cawwot Dofus equivalent to 12.5 MP Loss Res + 12.5 AP Loss Res
        #Gives 25 AP Parry if an AP penalty is suffered, or 25 MP Parry if an MP penalty is suffered. \nThe two effects last 1 turn and do not stack.
        cawwot_dofus_new_stat_weight = objective_values.get('apres', 0) * 12.5 + objective_values.get('mpres', 0) * 12.5
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Cawwot Dofus').id, 
                               cawwot_dofus_new_stat_weight)
        
        #Adding more weight to Vulbis Dofus equivalent to 5% damage + 10 lock
        #Increases damage inflicted by 10% for 1 turn if the bearer has suffered no damage from enemies since the last turn.\nOtherwise, gives 20 Lock.
        vulbis_dofus_new_stat_weight = objective_values.get('permedam', 0) * 5 + objective_values.get('perrandam', 0) * 5 + objective_values.get('lock', 0) * 10
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Vulbis Dofus').id, 
                               vulbis_dofus_new_stat_weight)
        
        #Adding more weight to Black-Spotted Dofus
        #If the bearer inflicts damage during their turn, they and their allies carrying the Dorigami gain 20 damage for 1 turn.\n\nIf the bearer does not inflict damage, they and their allies carrying the Domakuro gain 150% of their respective levels in shield for 1 turn.
        black_spotted_dofus_new_stat_weight = objective_values.get('dam', 0) * 10 + objective_values.get('hp', 0) * 150 * level / 200 / 2
        self.problem.add_to_of('p',
                                 self.structure.get_item_by_name('Black-Spotted Dofus').id,
                                 black_spotted_dofus_new_stat_weight)
        
        #Ebony Dofus
        #Ebony Black: When the bearer attacks in close combat during their turn, they gain 1% ranged damage for 3 turns (stackable 10 times).\nWhen they attack from long range, they gain 1% close-combat damage for 3 turns (stackable 10 times).\nTriggering both effects during the turn allows the next attack to apply a 16 poison in its element for 2 turns (stackable 2 times, once every 2 turns).
        ebony_dofus_new_stat_weight = objective_values.get('permedam', 0) * 5 + objective_values.get('perrandam', 0) * 5 + objective_values.get('pow', 0) * 16 * level / 200
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Ebony Dofus').id, 
                               ebony_dofus_new_stat_weight)
        
        #Adding more weight to Ivory Dofus equivalent to 10% res distance and melee
        #The bearer reduces damage from one out of five attacks by 50%. The reduction is lost if this one is sacrificed.
        ivory_dofus_new_stat_weight = objective_values.get('respermee', 0) * 10 + objective_values.get('resperran', 0) * 10
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name('Ivory Dofus').id,
                                ivory_dofus_new_stat_weight)
        
        #Adding more weight to Ochre Dofus equivalent to 0.2 AP + 16 Dodge
        #Gives 1 AP for 1 turn if the bearer has suffered no damage from enemies since the last turn.\nOtherwise, gives 20 Dodge.
        ochre_dofus_new_stat_weight = objective_values.get('ap', 0) * 0.2 + objective_values.get('dodge', 0) * 16
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Ochre Dofus').id, 
                               ochre_dofus_new_stat_weight)
        
        #Cloudy Dofus
        #On odd turns, the bearer gains 20% final damage but loses 10% final healing.\nOn even turns, the bearer gains 20% final healing but loses 10% final damage.
        cloudy_dofus_new_stat_weight = objective_values.get('permedam', 0) * 5 + objective_values.get('perrandam', 0) * 5 + objective_values.get('heals', 0) * 5
        self.problem.add_to_of('p',
                                 self.structure.get_item_by_name('Cloudy Dofus').id,
                                 cloudy_dofus_new_stat_weight)
        
        #TODO: find better way to add weight to Watchers Dofus
        #Adding more weight to Watchers Dofus equivalent to 10 heals
        #At the end of the turn, returns 7% HP to aligned allies. 
        watchers_dofus_new_stat_weight = (objective_values.get('heals', 0) * 10 + 2500) * level / 200.0
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Watchers Dofus').id, 
                               watchers_dofus_new_stat_weight)
        
        #Adding more weight to Dokoko
        #Every 3 turns starting on turn 3, returns 10% of their maximum health points.
        dokoko_new_stat_weight = objective_values.get('hp', 0) * (4500.0 * 10 / 100) * (1/3) * level / 200
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name('Dokoko').id,
                                dokoko_new_stat_weight)
        
        #Abyssal Dofus
        #At the start of each turn, if there are no enemies in close combat, gives 1 MP. Otherwise, gives 1 AP.
        abyssal_dofus_new_stat_weight = objective_values.get('ap', 0) * 2.5 + objective_values.get('mp', 0) * 2.5
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Abyssal Dofus').id, 
                               abyssal_dofus_new_stat_weight)
        
        #Adding more weight to Lavasmith Dofus
        #Applies 100% of level as shield points to its bearer, 1 time max per turn for pushback damage and 1 time for each type of movement: \n- pushback damage\n- pushback / attraction\n- place switching / teleportation / Eliotrope portal\n- carried by a Pandawa\n\nThe effect can only be triggered by enemies.
        lavasmith_dofus_new_stat_weight = objective_values.get('hp', 0) * 100 * level / 200
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name('Lavasmith Dofus').id,
                                lavasmith_dofus_new_stat_weight)
        
        #Adding more weight to Silver Dofus equivalent to some HP
        #As soon as the bearer falls below 20% of their health points, the Dofus's effect is triggered.\nAt the start of their next turn: heals 20% HP (once per fight).
        #Formula: expected life at lvl 200: 4500 - get 20% of that. 
        #Multiply by 0.2, since you wont get the bonus too often
        #Correct for level
        silver_dofus_new_stat_weight = objective_values.get('hp', 0) * (4500.0 * 20 / 100) * 0.2 * level / 200
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Silver Dofus').id, 
                               silver_dofus_new_stat_weight)
        
        #Adding more weight to Sparkling Silver Dofus equivalent to some HP
        #As soon as the bearer falls below 20% of their health points, the Dofus's effect is triggered.\nAt the start of their next turn: heals 30% HP and gives 20% final damage for 1 turn (once per fight).
        
        #Formula: expected life at lvl 200: 4500 - get 40% of that. 
        # Add 30% power to simulate final damage
        # Multiply by 0.2, since you wont get the bonus too often
        # Correct for level
        sparkling_silver_dofus_new_stat_weight_hp = objective_values.get('hp', 0) * (4500.0 * 30 / 100) * 0.2 * level / 200
        sparkling_silver_dofus_new_stat_weight_pow = objective_values.get('respermee', 0) * 20 * 0.2 + objective_values.get('resperran', 0) * 20 * 0.2
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Sparkling Silver Dofus').id, 
                               sparkling_silver_dofus_new_stat_weight_hp)
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Sparkling Silver Dofus').id, 
                               sparkling_silver_dofus_new_stat_weight_pow)
        
        #TODO: find better way to add weight to Crocobur
        #Adding more weight to Crocobur equivalent to 200 HP * meleeness
        #At the start of each turn, the bearer inflicts damage on themself in their best attack element to steal health from adjacent entities at the end of the caster's turn.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Crocobur 3").id, 
                               objective_values.get('hp', 0) * level / 2 + objective_values.get('perrandam', 0) * level / 200)
        
        #Buhorado Feather
        #When the bearer lands a critical hit, they gain 10 Pushback Damage for 3 turns (stackable 10 times).
        buhorado_feather_new_stat_weight = objective_values.get('pshdam', 0) * 45 * objective_values.get('ch', 0) / 100
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Buhorado Feather").id, 
                               buhorado_feather_new_stat_weight)
        
        #Adding more weight to Fallanster's Rectitude equivalent to 2% HP
        #If the bearer ends their turn with a line of sight to at least one opponent, they earn a 10% damage suffered reduction for 1 turn as long as they haven't been pushed, attracted, carried, teleported or transposed.
        fallanster_new_stat_weight = objective_values.get('respermee', 0) * 8 + objective_values.get('resperran', 0) * 8
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Fallanster's Rectitude").id, 
                               fallanster_new_stat_weight)
        
        #Adding more weight to Death-Defying equivalent to 2.5% res distance and melee
        #Damage suffered by the bearer is increased by 15% whenever they have more than 50% HP, but damage suffered is reduced by 20% whenever they have less than 50% HP.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Death-Defying").id, 
                               objective_values.get('respermee', 0) * 2.5 + objective_values.get('resperran', 0) * 2.5)
        
        #Adding more weight to Bram Worldbeard's Crown equivalent to 7.5% weapon damage
        #When the bearer suffers an AP, MP or Range removal, they gain 3% weapon damage for 2 turns, stackable 5 times.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Bram Worldbeard's Crown").id, 
                               objective_values.get('perweadam', 0) * 7.5)
        
        #Adding more weight to Ganymede's Diadem equivalent to 1 AP
        #The bearer gains 2 AP on even turns and loses 1 AP on odd turns.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Ganymede's Diadem").id, 
                               objective_values.get('ap', 0))
        
        #Adding more weight to Rykke Errel's Bravery equivalent to 400 hp and -10% ranged damage
        #For each distance attack suffered, the bearer gains shield and loses ranged damage for 1 turn; stackable up to 5 times maximum. The damage penalty and shield values vary according to the distance between the bearer and their attacker.
        #Will consider 3 distance attacks each turn
        distance_attacks = 3
        rikke_new_stat_weight = objective_values.get('hp', 0) * 200 * distance_attacks - objective_values.get('perrandam', 0) * 5 * distance_attacks
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Rykke Errel's Bravery").id, 
                               rikke_new_stat_weight)
        
        #Adding more weight to Jahash Jurgen's Nobility equivalent to 1.5% resists (1-2 hits on each element)
        #When the bearer suffers damage in an element, they gain 3% resistance in that element for 2 turns, stackable 5 times.
        resists_to_consider = 1.5
        jahash_new_stat_weight = (objective_values.get('neutresper', 0) * resists_to_consider
                                  + objective_values.get('airresper', 0) * resists_to_consider
                                  + objective_values.get('earthresper', 0) * resists_to_consider
                                  + objective_values.get('fireresper', 0) * resists_to_consider
                                  + objective_values.get('waterresper', 0) * resists_to_consider)
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Jahash Jurgen's Nobility").id, 
                               jahash_new_stat_weight)
        
        #Adding more weight to Thousand-League Boots equivalent to 1 MP
        #The bearer gains 2 MP on odd turns and loses 1 MP on even turns.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Thousand-League Boots').id, 
                               objective_values.get('mp', 0))
        
        #Adding more weight to Kicked Ass Boots equivalent to 30 Dodge and 50 Pushback Damage
        #At the start of each turn, the bearer pushes entities in close combat back 2 cells.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Kicked Ass Boots").id, 
                               objective_values.get('dodge', 0) * 30 + objective_values.get('pshdam', 0) * 50)
        
        #Adding more weight to Dodge's Audacity equivalent to 50 dodge, 5% critical hits and 40 pushback damage
        #At the start of each turn, the caster randomly teleports to an adjacent cell. If the move is impossible, they earn a +10% chance of critical hits and +80 Pushback Damage for 1 turn.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Dodge's Audacity").id, 
                               objective_values.get('dodge', 0) * 50 + objective_values.get('ch', 0) * 5 + objective_values.get('pshdam', 0) * 40)
        
        #Adding more weight to Lady Jhessica's Courage equivalent to 25 Lock
        #At end of their turn, the bearer removes 100 Dodge from adjacent enemies for 1 turn.
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name("Lady Jhessica's Courage").id, 
                               objective_values.get('lock', 0) * 50)
        
        #Adding more weight to Cocoa Dofus
        #Each ranged attack suffered while you are in close combat with an enemy grants a chocolate mark.\n\nThese marks are consumed at the end of your turn; each one gives 25% of your level in shield for 1 turn.
        cocoa_dofus_new_stat_weight = objective_values.get('hp', 0) * 50 * level / 200
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Cocoa Dofus 2").id,
                                cocoa_dofus_new_stat_weight)
        
        #Adding more weight to Prytekt
        #The bearer gains 550% of their level in shield points on the first turn, 200% on the second turn and 100% on the third.
        prytekt_new_stat_weight = objective_values.get('hp', 0) * ((0.7*550+0.85*200+100)/4) * level / 200
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prytekt-O-Mat").id,
                                prytekt_new_stat_weight)
        #Shiny Prytekt
        #The bearer gains 150% of their level in shield points on the first turn, 450% on the second turn and 150% on the third.
        shiny_prytekt_new_stat_weight = objective_values.get('hp', 0) * ((0.7*150+0.85*450+150)/4) * level / 200
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Shiny Prytekt").id,
                                shiny_prytekt_new_stat_weight)

        #Iridescent Prytekt
        #The bearer gains 100% of their level in shield points on the first turn, 200% on the second turn and 350% on the third.
        iridescent_prytekt_new_stat_weight = objective_values.get('hp', 0) * ((0.7*100+0.85*200+350)/4) * level / 200
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Iridescent Prytekt").id,
                                iridescent_prytekt_new_stat_weight)

        #Pryssure
        #The bearer gains 1 AP for 3 turns but inflicts -10% damage.
        pryssure_new_stat_weight = objective_values.get('ap', 0) * 0.75 - objective_values.get('permedam', 0) * 7.5 - objective_values.get('perrandam', 0) * 7.5     
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Pryssure-O-Mat").id,
                                pryssure_new_stat_weight)

        #Shiny Pryssure
        #The bearer gains 2 AP for 2 turns but inflicts -35% damage.
        shiny_pryssure_new_stat_weight = objective_values.get('ap', 0) * 1 - objective_values.get('permedam', 0) * 17.5 - objective_values.get('perrandam', 0) * 17.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Shiny Pryssure").id,
                                shiny_pryssure_new_stat_weight)


        #Iridescent Pryssure
        #The bearer gains 4 AP for 1 turn but inflicts -50% damage.
        iridescent_pryssure_new_stat_weight = objective_values.get('ap', 0) * 1 - objective_values.get('permedam', 0) * 12.5 - objective_values.get('perrandam', 0) * 12.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Iridescent Pryssure").id,
                                iridescent_pryssure_new_stat_weight)

        #Surpryz
        #The bearer gains 100% Critical on the first turn, 35% on the second turn and 15% on the third turn.
        surpryz_new_stat_weight = objective_values.get('ch', 0) * 20
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Surpryz").id,
                                surpryz_new_stat_weight)

        #Prynyang
        #The bearer sacrifices 10% resistance to gain 10% final damage on the first turn, then gains 3% final damage and resistance on the second turn, and sacrifices 10% final damage to gain 10% resistance on the third turn.
        prynyang_new_stat_weight = (objective_values.get('permedam', 0) * 5 + objective_values.get('perrandam', 0) * 5 + 
                                    objective_values.get('respermee', 0) * 4 + objective_values.get('resperran', 0) * 4)
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prynyang").id,
                                prynyang_new_stat_weight)

        #Prycapture
        #The bearer gains 1 MP (2 turns) per enemy more than 15 cells away.
        prycapture_new_stat_weight = objective_values.get('mp', 0) * 0.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prycapture").id,
                                prycapture_new_stat_weight)

        #Prygenerate
        #Heals 15% of enemy damage suffered until the end of the third turn.
        prygenerate_new_stat_weight = objective_values.get('hp', 0) * 0.15 * 3 * level
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prygenerate").id,
                                prygenerate_new_stat_weight)

        #Prysipitate
        #The bearer gains +2 AP for their first round.
        prysipitate_new_stat_weight = objective_values.get('ap', 0) * 0.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prysipitate-O-Mat").id,
                                prysipitate_new_stat_weight)

        #Shiny Prysipitate
        #The bearer gains +3 AP for their first round but also loses 2 MP.
        shiny_prysipitate_new_stat_weight = objective_values.get('ap', 0) * 0.75 - objective_values.get('mp', 0) * 0.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Shiny Prysipitate").id,
                                shiny_prysipitate_new_stat_weight)

        #Iridescent Prysipitate
        #The bearer gains +4 AP for their first round but also loses 4 MP.
        iridescent_prysipitate_new_stat_weight = objective_values.get('ap', 0) * 1 - objective_values.get('mp', 0) * 1
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Iridescent Prysipitate").id,
                                iridescent_prysipitate_new_stat_weight)

        #Spryritual
        #The bearer gains 250 AP Parry on the first turn, then 50 AP Parry on the second turn.
        spryritual_new_stat_weight = objective_values.get('apres', 0) * 100
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Spryritual").id,
                                spryritual_new_stat_weight)

        #Prysical
        #The bearer gains 250 MP Parry on the first turn, then 50 MP Parry on the second turn.
        prysical_new_stat_weight = objective_values.get('mpres', 0) * 100
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prysical").id,
                                prysical_new_stat_weight)

        #Caraprys
        #At the end of their first turn, the bearer reduces damage by 5% (3 turns) for each enemy (excluding summons) in their line of sight.
        caraprys_new_stat_weight = objective_values.get('respermee', 0) * 7.5 + objective_values.get('resperran', 0) * 7.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Caraprys").id,
                                caraprys_new_stat_weight)

        #TODO: find better way to add weight to Disaprys
        #Disaprys
        #The bearer becomes invisible (1 turn) at the start of their first round.
        disaprys_new_stat_weight = objective_values.get('hp', 0) * 0.5 * level
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Disaprys").id,
                                disaprys_new_stat_weight)

        #TODO: find better way to add weight to Prywitchment
        #Prywitchment
        #Reduces the duration of active effects on the bearer by 4 at the start of their first round.
        prywitchment_new_stat_weight = objective_values.get('hp', 0) * 0.5 * level
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prywitchment").id,
                                prywitchment_new_stat_weight)

        #Pryshield
        #The bearer gains 200% of their level in shield (infinite) for each opponent (excluding summons) that plays before them.
        pryshield_new_stat_weight = objective_values.get('hp', 0) * 2 * level * 1.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Pryshield").id,
                                pryshield_new_stat_weight)

        #Pryximity
        #The bearer gains 2% close-combat damage for 3 turns for each enemy fighter within 3 cells or less of the bearer at the start of their first turn.
        pryximity_new_stat_weight = objective_values.get('permedam', 0) * 2 * 2 * 0.5
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Pryximity").id,
                                pryximity_new_stat_weight)

        #Prymune
        #The bearer reduces all types of damage suffered by 80% on the first turn.
        prymune_new_stat_weight = (objective_values.get('respermee', 0) + objective_values.get('resperran', 0)) * 80 * 0.18
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Prymune").id,
                                prymune_new_stat_weight)

        #Gravprysy
        #The bearer gains the Gravity state as long as they have not suffered any damage. If they suffer damage, the duration of the state changes to 1 turn.
        gravprysy_new_stat_weight = objective_values.get('dodge', 0) * 50 + objective_values.get('lock', 0) * 50
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Gravprysy").id,
                                gravprysy_new_stat_weight)

        #War's Halbaxe
        #If the bearer is in close contact with an enemy at the start of their turn, they gain 20 MP Reduction for 1 turn; if not, they gain 30 Lock. When the bearer kills an opponent (excluding summons) with direct damage, they gain 1 MP until the end of the fight, stackable max. 3 times.
        wars_halbaxe_new_stat_weight = objective_values.get('mpres', 0) * 10 + objective_values.get('lock', 0) * 15 + objective_values.get('mp', 0) * 0.25
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("War's Halbaxe").id,
                                wars_halbaxe_new_stat_weight)

        #TODO: find better way to add weight to Corruption Pestilence
        #Corruption Pestilence
        #When the caster returns to 100% HP via healing or a health steal, they apply a start-of-turn poison in their best element on entities two cells away or less. The poison lasts 2 turns, cannot be unbewitched, and can be stacked a maximum of 1 time.
        corruption_pestilence_new_stat_weight = objective_values.get('permedam', 0) * 2 + objective_values.get('perrandam', 0) * 2
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Corruption Pestilence").id,
                                corruption_pestilence_new_stat_weight)

        #TODO: find better way to add weight to Servitude's Embrace
        #Servitude's Embrace
        #At the end of each turn, the bearer attracts entities in a 3-cell cross around themself by 2 cells. If the bearer has no entities next to them at the end of their turn, they enter the Unmovable state until the start of their next turn. The state is removed if they suffer damage.
        servitudes_embrace_new_stat_weight = objective_values.get('dodge', 0) * 20 + objective_values.get('lock', 0) * 20
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Servitude's Embrace").id,
                                servitudes_embrace_new_stat_weight)

        #Misery's Flail-Scale
        #When the bearer suffers an AP, MP or Range reduction, the damage they suffer is reduced by 4% for 2 turns. Damage suffered by the attacker is increased by 4% for 2 turns. Stackable max. 3 times.
        miserys_flail_scale_new_stat_weight = objective_values.get('respermee', 0) * 4 + objective_values.get('resperran', 0) * 4
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Misery's Flail-Scale").id,
                                miserys_flail_scale_new_stat_weight)
        
        #Adding more weight to Domakuro equivalent to dmg * 10 (includes summon buff)
        #Starting on turn 5, the bearer and their summons gain up to 64 Damage until the end of the fight.\nThis bonus is reduced each time the bearer inflicts damage on an enemy during their turn for each of the first 4 turns of the fight:\nNo attacks: 16 Damage\n1 attack: 8 Damage\n2 attacks or more: 0 Damage
        domakuro_dofus_new_stat_weight = (objective_values.get('neutdam', 0) + 
                                          objective_values.get('earthdam', 0) + 
                                          objective_values.get('firedam', 0) + 
                                          objective_values.get('airdam', 0) + 
                                          objective_values.get('waterdam', 0)) * 8
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Domakuro').id, 
                               domakuro_dofus_new_stat_weight)
        #Adding more weight to Dorigami equivalent to 20 (avg vit weight) + lvl * 1.25
        #Applies 100% of level as Shield at the start of each turn for the first 5 turns. \nDuring each of these 5 turns, if the caster kills a summons, the caster gains 100% of their level as shield for 2 turns (max. 4 times), and 300% (max. 2 times) for a monster or player.\nShields are only obtained during the caster's turn.
        dorigami_dofus_new_stat_weight = 20 * level * 1.25
        self.problem.add_to_of('p', 
                               self.structure.get_item_by_name('Dorigami').id, 
                               dorigami_dofus_new_stat_weight)
        
        #Nightmare Dofus
        #Bontarian Shield: When the bearer is unbewitched or debuffed, the bearer gains 100% of their level as shield for 1 turn.\nBrakmarian Power: Whenever the bearer inflicts or suffers pushback damage, the bearer gains 100 Power for 1 turn.\nNightmare Eye: If the bearer triggers Bontarian Shield and Brakmarian Power in the same turn, the damage they inflict and suffer increases by 10% for 1 turn.\nThe effects can only be triggered once per turn.
        nightmare_dofus_new_stat_weight = objective_values.get('hp', 0) * level * 0.5 + objective_values.get('pow', 0) * 40 + objective_values.get('permedam', 0) * 4 + objective_values.get('perrandam', 0) * 4
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Nightmare Dofus").id,
                                nightmare_dofus_new_stat_weight)

        #Sylvan Dofus
        #For each MP used, the bearer gains 8 Power for 2 turns, stackable 20 times. If the bearer does not use any MP, they are healed for 10% of their HP at the end of their turn.
        sylvan_dofus_new_stat_weight = objective_values.get('pow', 0) * 50 + objective_values.get('hp', 0) * (4500.0 * 10 / 100) * 0.2 * level / 200
        self.problem.add_to_of('p',
                                self.structure.get_item_by_name("Sylvan Dofus 2").id,
                                sylvan_dofus_new_stat_weight)

    def write_objective_function(self, objective_values, level):
        self.problem.init_objective_function()

        for stat, value in objective_values.items():
            if stat != 'meleeness':
                stat_obj = self.structure.get_stat_by_key(stat)
                if stat_obj:
                    self.problem.add_to_of('stat', stat_obj.id, value)
                else:
                    logger.warning('Could not find stat %s', stat)
        
        self.add_weird_item_weights_to_objective_funcion(objective_values, level)

        self.problem.finish_objective_function()
    
    #def add_objective_term(self, stat_name, weight):
    #    for item in self.items_list:
    #        for stat_id, value in item.stats:
    #            if self.structure.get_stat_name_by_id(stat_id) == stat_name:
    #                self.problem.add_to_of('x', item.id, value * weight)
    #    
    #    for item_set in self.sets_list:
    #        for num_items, stat_id, value in item_set.bonus:
    #            if self.structure.get_stat_name_by_id(stat_id) == stat_name:
    #                self.problem.add_to_of('ss', '%d_%d' % (set.id, num_items + 1), value * weight)
    
    def create_constraints(self):
        self.create_type_constraints()
        self.create_presence_constraints()
        self.create_level_constraints()
        self.create_set_constraints()
        self.create_set_max_cap_constraints()
        self.create_stat_total_constraints()
        self.create_stat_cap_constraints()
        self.create_exo_constraints()
        self.create_condition_contraints()
        self.create_minimum_stat_constraints()
        self.create_advanced_minimum_stat_constraints()
        self.create_or_item_count_constraints()
        self.create_locked_equip_constraints()
#        self.create_two_handed_constraints()
        self.create_forbidden_items_constraints()
        self.create_stats_points_constraints()
        self.create_light_set_constraints()
        self.create_prysmaradite_constraints()
        
    def setup(self, model_input):
        self.input = model_input.get_old_input()

        self.modify_level_constraints(model_input.char_level)
        self.modify_stat_total_constraints(model_input.base_stats_by_attr,
                                           model_input.options)
        self.modify_minimum_stat_constraints(model_input.minimum_stats, 
                                             model_input.char_level)
        self.modify_locked_equip_constraints(model_input.locked_equips)
        self.modify_forbidden_items_constraints(model_input.forbidden_equips,
                                                model_input.options)
        self.modify_stats_points_constraints(model_input.char_class,
                                             model_input.stat_points_to_distribute,
                                             model_input.base_stats_by_attr)
        self.modify_empty_slot_constraints(model_input.empty_slot_types)

        self.write_objective_function(model_input.objective_values, model_input.char_level)
    
    def create_type_constraints(self):
        types_list = self.structure.get_types_list()
        for item_type in types_list:
            items_of_type = []
            for item in self.items_list:
                if self.structure.get_type_name_by_id(item.type) == item_type:
                    items_of_type.append(item)
            # A type with no items (Shield in Retro 1.29) collapses sum([]) <= n into a bool.
            if not items_of_type:
                continue
            restriction = self.problem.restriction_lt_eq(TYPE_NAME_TO_SLOT_NUMBER[item_type],
                                                        [(1, 'x', item_entry.id) for item_entry in items_of_type])
            self.restrictions.type_constraints[item_type] = restriction

    def modify_empty_slot_constraints(self, empty_slots):
        locked_count = {}
        for slot in empty_slots:
            t = SLOT_NAME_TO_TYPE.get(slot)
            if t:
                locked_count[t] = locked_count.get(t, 0) + 1
        for type_name, constraint in self.restrictions.type_constraints.items():
            max_slots = TYPE_NAME_TO_SLOT_NUMBER[type_name]
            locked = locked_count.get(type_name, 0)
            constraint.changeRHS(max(0, max_slots - locked))

#     def create_two_handed_constraints(self):
#         one_handed_items = []
#         for item in self.items_list:
#             if item.is_one_handed:
#                 one_handed_items.append(item)
#         for item in self.items_list:
#             if self.structure.get_type_name_by_id(item.type) == 'Shield':
#                 restriction = self.problem.restriction_lt_eq(0, [(-1, 'p', item_entry.id) for item_entry in one_handed_items] + [(1, 'p', item.id)])
#                 self.restrictions.two_handed_constraints[item.id] = restriction
    
    def create_presence_constraints(self):
        for item in self.items_list:
            restriction1 = self.problem.restriction_lt_eq(0, [(1, 'p', item.id),
                                                              (-1, 'x', item.id)])
            restriction2 = self.problem.restriction_lt_eq(0, [(-2, 'p', item.id),
                                                              (1, 'x', item.id)])
            self.restrictions.first_presence_constraints[item.id] = restriction1
            self.restrictions.second_presence_constraints[item.id] = restriction2
            

    def create_level_constraints(self):
        for item in self.items_list:
            restriction = self.problem.restriction_lt_eq(0, [(1, 'p', item.id)])
            self.restrictions.level_constraints[item.id] = restriction
    
    def modify_level_constraints(self, char_level):
        for item in self.items_list:
            restriction = self.restrictions.level_constraints.get(item.id, None)
            restriction.changeRHS(0 if char_level < item.level else 1)
    
    def create_forbidden_items_constraints(self):
        for item in self.items_list:
            restriction = self.problem.restriction_lt_eq(0, [(1, 'p', item.id)])  
            self.restrictions.forbidden_items_constraints[item.id] = restriction
    
    def create_stats_points_constraints(self):
        for stat in self.main_stats_list:
            self.restrictions.first_stats_points_constraints[stat.key] = {}
            self.restrictions.second_stats_points_constraints[stat.key] = {}
            self.restrictions.third_stats_points_constraints[stat.key] = {}
            for i in range(1, 6):
                restriction = self.problem.restriction_lt_eq(1990, [(-1, 'stat_point', 'statpoint_%d_%d' % (i, stat.id)),
                                                                    (1990, 'stat_point_max', 'statpointmax_%d_%d' % (i-1, stat.id))])  
                self.restrictions.first_stats_points_constraints[stat.key][i] = restriction
            for i in range(0, 6):
                restriction = self.problem.restriction_lt_eq(0, [(1, 'stat_point', 'statpoint_%d_%d' % (i, stat.id))])  
                self.restrictions.second_stats_points_constraints[stat.key][i] = restriction
            for i in range(0, 5):
                restriction = self.problem.restriction_lt_eq(0, [(-1, 'stat_point', 'statpoint_%d_%d' % (i, stat.id)),
                                                              (-2000, 'stat_point_max', 'statpointmax_%d_%d' % (i, stat.id))]) 
                self.restrictions.third_stats_points_constraints[stat.key][i] = restriction 
        matrix = []
        for stat in self.main_stats_list:
            matrix.extend([(0.5, 'stat_point', 'statpoint_0_%d' % stat.id),
                           (1, 'stat_point', 'statpoint_1_%d' % stat.id),
                           (2, 'stat_point', 'statpoint_2_%d' % stat.id),
                           (3, 'stat_point', 'statpoint_3_%d' % stat.id),
                           (4, 'stat_point', 'statpoint_4_%d' % stat.id),
                           (5, 'stat_point', 'statpoint_5_%d' % stat.id)])
        restriction = self.problem.restriction_lt_eq(0, matrix)
        self.restrictions.fourth_stats_points_constraint = restriction 

    def modify_stats_points_constraints(self, char_class, stat_points, base_stats_by_attr=None):
        game_version = getattr(self.structure, 'game_version', 'dofus3')
        caps = get_soft_caps_for(game_version, char_class)
        base_stats_by_attr = base_stats_by_attr or {}
        # base_stats_by_attr is keyed by full stat name; the cost tiers by stat key.
        name_by_key = {stat.key: stat.name for stat in self.main_stats_list}
        push_curve = scrolls_push_cost_curve(game_version)
        for stat in caps:
            # On retro the scrolled base eats the cheap low tiers before any point is spent.
            scrolled = (base_stats_by_attr.get(name_by_key.get(stat), 0)
                        if push_curve else 0)
            widths = tier_widths_after_scroll(caps[stat], scrolled)
            second = self.restrictions.second_stats_points_constraints.get(stat, None)
            third = self.restrictions.third_stats_points_constraints.get(stat, None)
            for i in range(0, 6):
                second[i].changeRHS(widths[i] if widths[i] is not None else 1991)
            for i in range(0, 5):
                third[i].changeRHS(-widths[i] if widths[i] is not None else -1991)

        restriction = self.restrictions.fourth_stats_points_constraint
        restriction.changeRHS(stat_points)
    
    def modify_forbidden_items_constraints(self, forbidden_equips, options):
        new_forbid_list = forbidden_equips
        
        or_items = self.structure.get_available_or_items()
        for _, or_item_items in or_items.items():
            for item in or_item_items:
                if item.id in forbidden_equips:
                    for or_item in or_item_items:
                        new_forbid_list.add(or_item.id)

        for item in self.items_list:
            restriction = self.restrictions.forbidden_items_constraints.get(item.id, None)
            if ((item.id in new_forbid_list)
                or (not options.get('shields', True) and item.type == self.structure.get_type_id_by_name('Shield'))
                or (not options.get('trophies', True) and 'Trophy' in item.flags)
                or (options['dofus'] == 'lightset'
                    and item.type == self.structure.get_type_id_by_name('Dofus')
                    and item.weird_conditions['light_set']) 
                or (options['dofus'] == False 
                    and item.type == self.structure.get_type_id_by_name('Dofus'))
                or (options['dofus'] == 'cawwot' 
                    and item.type == self.structure.get_type_id_by_name('Dofus'))
                    and item.id != self.structure.get_item_by_name('Cawwot Dofus').id
                or ((not options['dragoturkey'])
                    and item.type == self.structure.get_type_id_by_name('Pet'))
                    and 'Dragoturkey' in item.name
                or ((not options['seemyool'])
                    and item.type == self.structure.get_type_id_by_name('Pet'))
                    and 'Seemyool' in item.name
                or ((not options['rhineetle'])
                    and item.type == self.structure.get_type_id_by_name('Pet'))
                    and 'Rhineetle' in item.name
                or ((not options['prysmaradite'])
                    and item.weird_conditions['prysmaradite'])):
                restriction.changeRHS(0)
            else:
                restriction.changeRHS(1)
        # The exo option decides which of the two synthesized Gelano rows is
        # usable, and it used to decide it alone: whatever the player forbade,
        # one row came back. In "only what I own" that meant a ring nobody
        # owned, since the inventory restriction speaks through the same
        # exclusions. The option still picks the row; an exclusion still wins.
        gelano1 = self.structure.get_item_by_name('Gelano (#1)')
        gelano2 = self.structure.get_item_by_name('Gelano (#2)')
        if gelano1 and gelano2:
            wants_exo = options['mp_exo'] == 'gelano'
            for gelano, allowed_by_option in ((gelano2, not wants_exo),
                                              (gelano1, wants_exo)):
                restriction = self.restrictions.forbidden_items_constraints.get(
                    gelano.id, None)
                if restriction is None:
                    continue
                restriction.changeRHS(
                    1 if allowed_by_option and gelano.id not in new_forbid_list
                    else 0)
    
    def create_or_item_count_constraints(self):
        """One item split into rows is still one item.

        An item gated behind alternative conditions ships as "(#1)" and "(#2)",
        and the exo variants do the same. Nothing counted the group, so the two
        rows of Crocoring could fill both ring slots: one ring worn twice, and
        two pieces of its set counted from one. The pair of a setless ring is
        the case the game does allow, so the ceiling is the one a single member
        already has.
        """
        for _name, members in self.structure.get_available_or_items().items():
            if len(members) < 2:
                continue
            first = members[0]
            doublable = (self.structure.game_version != 'retro'
                         and self.structure.get_type_name_by_id(first.type) == 'Ring'
                         and first.set is None)
            restriction = self.problem.restriction_lt_eq(
                2 if doublable else 1,
                [(1, 'x', item.id) for item in members])
            self.restrictions.or_item_count_constraints[first.id] = restriction

    def create_locked_equip_constraints(self):
        for item in self.items_list:
            restriction = self.problem.restriction_lt_eq(-1, [(-1, 'x', item.id)])
            self.restrictions.locked_equip_constraints[item.id] = restriction
        or_items = self.structure.get_available_or_items()
        for item_name in or_items:
            restriction2 = self.problem.restriction_lt_eq(-1, [(-1, 'x', item.id) for item in or_items[item_name]])
            self.restrictions.locked_equip_constraints[item_name] = restriction2

    def modify_locked_equip_constraints(self, locked_equips):
        locked_equip_values = []
        for item in list(locked_equips.values()):
                locked_equip_values.append(item)
        locked_dic = Counter(locked_equip_values)
        locked_dic_names = Counter(list(locked_equips.values()))
        or_items = self.structure.get_available_or_items()
        for item_id, occurrences in locked_dic.items():
            if occurrences > 1 and item_id != '':
                item = self.structure.get_item_by_id(item_id)
                locked_dic[item_id] = 2 if self.structure.get_type_name_by_id(item.type) == 'Ring' and item.set == None else 1
        for item_name, occurrences in locked_dic_names.items():
            if occurrences > 1 and item_name != '':
                if item_name in or_items:
                    item = or_items[item_name].get(0)
                    locked_dic_names[item_name] = 2 if self.structure.get_type_name_by_id(item.type) == 'Ring' and item.set == None else 1
        
        
        for item in self.items_list:
            restriction = self.restrictions.locked_equip_constraints[item.id]
            restriction.changeRHS(-locked_dic[item.id] if item.id in locked_equip_values else 0)
        for item_name in or_items:
            restriction = self.restrictions.locked_equip_constraints[item_name]
            restriction.changeRHS(-locked_dic_names[item_name] if item_name in list(locked_equips.values()) else 0)
            
    def create_set_constraints(self):
        for item_set in self.sets_list:
            
            valid_items_in_set = []
            s = get_structure()
            for item in item_set.items:
                if not s.get_item_by_id(item).removed:
                    valid_items_in_set.append(item)
            restriction = self.problem.restriction_eq(0, [(1, 'x', item) for item in valid_items_in_set]
                                                            + [(-1, 's', item_set.id)])
            self.restrictions.first_set_constraints[item_set.name] = restriction
        
        for item_set in self.sets_list:
            restrictions_list = []
            for slot in range (1, 9):
                restriction = self.problem.restriction_lt_eq(0, [(slot, 'ss', '%d_%d' % (item_set.id, slot + 1)), (-1, 's', item_set.id)])   
                restrictions_list.append(restriction)
            self.restrictions.second_presence_constraints[item_set.name] = restrictions_list

        for item_set in self.sets_list:
            restriction = self.problem.restriction_eq(1, [(1, 'ss', '%d_%d' % (item_set.id, slot + 1)) for slot in range (0, 9)]) 
            self.restrictions.third_set_constraints[item_set.name] = restriction
        
        for item_set in self.sets_list:
            restrictions_list = []
            for slot in range (0, 9):
                restriction = self.problem.restriction_lt_eq(8 + slot,
                                                             [(8, 'ss', '%d_%d' % (item_set.id, slot + 1)),
                                                              (1, 's', item_set.id)])
                restrictions_list.append(restriction)
            self.restrictions.fourth_set_constraints[item_set.name] = restrictions_list
    
    def create_set_max_cap_constraints(self):
        """Big-M constraints for set-based stat caps (e.g. Cire Momore AP/MP/Range limits)."""
        overage_ss_per_stat = {}  # stat_id -> list of (set_id, tier_index)

        for item_set in self.sets_list:
            if not item_set.max_caps:
                continue
            for num_items, stat_id, max_value in item_set.max_caps:
                stat = self.structure.get_stat_by_id(stat_id)
                if stat is None or stat.name not in self.stat_maximum:
                    continue
                global_max = self.stat_maximum[stat.name]
                if max_value >= global_max:
                    continue
                matrix = [
                    (1, 'stat', stat_id),
                    (global_max - max_value, 'ss', '%d_%d' % (item_set.id, num_items + 1)),
                ]
                restriction = self.problem.restriction_lt_eq(global_max, matrix)
                self.restrictions.set_max_cap_constraints[(item_set.id, num_items, stat_id)] = restriction

                if stat_id in self._capped_stat_ids:
                    overage_ss_per_stat.setdefault(stat_id, []).append((item_set.id, num_items + 1))

        for stat_id, ss_keys in overage_ss_per_stat.items():
            stat = self.structure.get_stat_by_id(stat_id)
            if not stat or stat.name not in self.stat_maximum:
                continue
            global_max = self.stat_maximum[stat.name]
            overage_matrix = [(1, 'overage', stat_id)]
            for (set_id, k) in ss_keys:
                overage_matrix.append((-global_max, 'ss', '%d_%d' % (set_id, k)))
            self.problem.restriction_lt_eq(0, overage_matrix)

    def create_light_set_constraints(self):
        """
        Constraints for light sets:
        - Only one bonus 3 present if at least one item has the weird_condition 'light_set'
        - Only two bonus 2 present if at least one item has the weird_condition 'light_set'
        - If there is no weird_condition 'light_set' present, there can be at most 6 trophies
        """
        N_TOTAL_SETS = len(self.sets_list)
        # Count 1 for each bonus 2 for all item sets tested
        matrix = [(1, 'ss', '%d_%d' % (item_set.id, 2 + 1)) for item_set in self.sets_list]
        # Count 2 for each bonus 3 for all item sets tested
        matrix += [(2, 'ss', '%d_%d' % (item_set.id, 3 + 1)) for item_set in self.sets_list]
        matrix.append((-N_TOTAL_SETS, 'ytrophy', 1))
        # Light-set trophy cap: dofus3 "Set bonus < 3" allows 2, touch "Set bonus < 2" allows 1.
        light_set_caps = []
        for item in self.items_list:
            cap = item.weird_conditions['light_set']
            if cap:
                light_set_caps.append(2 if cap is True else cap)
        light_set_cap = min(light_set_caps) if light_set_caps else 2
        restriction = self.problem.restriction_lt_eq(light_set_cap, matrix)
        self.restrictions.first_light_set_constraint = restriction
        
        restriction = self.problem.restriction_lt_eq(N_TOTAL_SETS, [(N_TOTAL_SETS, 'ytrophy', 1), 
                                                                              (1, 'trophies', 1)]) 
        self.restrictions.second_light_set_constraint = restriction
        
        plist = []
        # Limits the number of bonus 4 or more to 0
        for set_bonus in range(4, 9): 
            plist.extend([(1, 'ss', '%d_%d' % (item_set.id, set_bonus + 1)) for item_set in self.sets_list])
        plist.append((-N_TOTAL_SETS, 'ytrophy', 2))
        restriction = self.problem.restriction_lt_eq(0, plist)
        self.restrictions.third_light_set_constraint = restriction
        
        restriction = self.problem.restriction_lt_eq(N_TOTAL_SETS, [(N_TOTAL_SETS, 'ytrophy', 2), 
                                                                              (1, 'trophies', 1)]) 
        self.restrictions.fourth_light_set_constraint = restriction
        plist = []
        # Count one for each item with weird_condition 'light_set'
        for item in self.items_list:
            if item.weird_conditions['light_set']:
                plist.append((1, 'x', item.id))
        #This will only work while all the items with this condition are trophies
        MAXIMUM_TROPHIES = 6
        plist.append((-MAXIMUM_TROPHIES, 'trophies', 1))

        restriction = self.problem.restriction_lt_eq(0, plist) 
        self.restrictions.fifth_light_set_constraint = restriction
    
    def create_prysmaradite_constraints(self):
        prysmaradite_count = []
        for item in self.items_list:
            if item.weird_conditions['prysmaradite']:
                prysmaradite_count.append((1, 'x', item.id))

        if prysmaradite_count:
            restriction = self.problem.restriction_lt_eq(1, prysmaradite_count)
            self.restrictions.prysmaradite_constraints = restriction
        
    def create_condition_contraints(self):
        for item in self.items_list:
            for stat, value in item.min_stats_to_equip:
                restriction = self.problem.restriction_lt_eq(10000,
                                                            [(value + 10000, 'p', item.id),
                                                             (-1, 'stat', stat)])
                self.restrictions.min_condition_contraints[(item.id, stat)] = restriction 
            
        for item in self.items_list:
            for stat, value in item.max_stats_to_equip:
                restriction = self.problem.restriction_lt_eq(100000 + value,
                                                             [(100000, 'p', item.id),
                                                              (1, 'stat', stat)])
                
                self.restrictions.max_condition_contraints[(item.id, stat)] = restriction

        self.create_or_condition_constraints()

    def create_or_condition_constraints(self):
        """Gates the game lets you satisfy one of, "MP < 6 or AP < 12".

        One binary per branch says which one the build leans on. At least one
        must be picked when the item is worn, and a branch only binds when it is
        the one picked, so the other stays free. Both were dropped before, which
        let the solver hand out an item the game refuses to equip.
        """
        for item in self.items_list:
            if not item.or_conditions:
                continue
            selectors = []
            for number, gates in enumerate(item.or_conditions):
                key = '%s_%s' % (item.id, number)
                self.problem.setup_variable('b', key, 0, 1)
                selectors.append((1, 'b', key))
                for stat, is_max, value in gates:
                    if is_max:
                        # stat <= value unless this branch is off or the item is out
                        restriction = self.problem.restriction_lt_eq(
                            200000 + value,
                            [(100000, 'p', item.id), (100000, 'b', key),
                             (1, 'stat', stat)])
                    else:
                        restriction = self.problem.restriction_lt_eq(
                            200000 - value,
                            [(100000, 'p', item.id), (100000, 'b', key),
                             (-1, 'stat', stat)])
                    self.restrictions.or_condition_contraints[
                        (item.id, number, stat)] = restriction
            # at least one branch when the item is worn: p - sum(b) <= 0
            restriction = self.problem.restriction_lt_eq(
                0, [(1, 'p', item.id)] + [(-c, family, key)
                                          for c, family, key in selectors])
            self.restrictions.or_branch_constraints[item.id] = restriction

    def create_stat_total_constraints(self):
        for stat in self.stats_list:
            # A capped stat splits in two: 'total' is what the gear gives and
            # 'stat' is what the character reads, min(cap, total).
            head = 'total' if stat.name in self.stat_maximum else 'stat'
            matrix = [(-1, head, stat.id)]
            for item in self.items_list:
                for stat_id, value in item.stats:
                    if stat_id == stat.id:
                        matrix.append((value, 'x', item.id))
            for item_set in self.sets_list:
                for num_items, stat_id, value in item_set.bonus:
                    if stat_id == stat.id:
                        matrix.append((value, 'ss', '%d_%d' % (item_set.id, num_items + 1)))
            if stat in self.main_stats_list:
                for i in range(0, 6):
                    matrix.append((1, 'stat_point', 'statpoint_%d_%d' % (i, stat.id)))
            # overage absorbs excess when a set cap drives the stat below the character's base
            if stat.id in self._capped_stat_ids:
                matrix.append((-1, 'overage', stat.id))
            if stat.key in self._EXO_STAT_KEYS:
                matrix.append((1, 'exo', stat.id))
            restriction = self.problem.restriction_eq(0, matrix)
            self.restrictions.stat_total_constraints[stat.name] = restriction

    _CAP_BIG_M = 100000

    def create_stat_cap_constraints(self):
        """stat = min(cap, total), the way the game reads a capped stat.

        The cap used to bound the variable the gear was tied to, which made it
        a rule about what could be worn: the solver spent a slot on a -1 AP
        weapon to get back under 12, and called a legal build impossible when
        no such piece existed. Four inequalities and one binary say the real
        thing instead. capped = 0 pins stat to total, capped = 1 pins it to the
        cap, and only one of the two is ever feasible.
        """
        big_m = self._CAP_BIG_M
        for stat in self.stats_list:
            if stat.name not in self.stat_maximum:
                continue
            cap = self.stat_maximum[stat.name]
            constraints = [
                # stat <= total
                self.problem.restriction_lt_eq(
                    0, [(1, 'stat', stat.id), (-1, 'total', stat.id)]),
                # stat >= total unless the cap is what binds
                self.problem.restriction_lt_eq(
                    0, [(1, 'total', stat.id), (-1, 'stat', stat.id),
                        (-big_m, 'capped', stat.id)]),
                # stat >= cap when the cap is what binds
                self.problem.restriction_lt_eq(
                    big_m - cap, [(big_m, 'capped', stat.id),
                                  (-1, 'stat', stat.id)]),
            ]
            self.restrictions.stat_cap_constraints[stat.name] = constraints

    def create_exo_constraints(self):
        """The exo point exists only if something gives it.

        exo <= (1 when the option is on) + the pieces worn that carry one. The
        right hand side starts at 0 and modify_exo_constraints raises it once
        the options are known. A piece that carries an exo can still be worn
        without it counting: the variable simply stays at 0.
        """
        carriers = getattr(self, '_exo_carriers', None) or {}
        for stat in self.stats_list:
            if stat.key not in self._EXO_STAT_KEYS:
                continue
            matrix = [(1, 'exo', stat.id)]
            for item in self.items_list:
                if item.id in carriers.get(stat.key, ()):
                    matrix.append((-1, 'p', item.id))
            self.restrictions.exo_constraints[stat.key] = (
                self.problem.restriction_lt_eq(0, matrix))

    def modify_exo_constraints(self, options):
        for stat in self.stats_list:
            if stat.key not in self._EXO_STAT_KEYS:
                continue
            restriction = self.restrictions.exo_constraints.get(stat.key)
            if restriction is None:
                continue
            option = options.get('%s_exo' % stat.key)
            # mp_exo can hold 'gelano', which is not this point: that choice
            # swaps in Gelano (#1), which carries the MP itself. Counting it
            # here as well would give the build two.
            restriction.changeRHS(1 if option is True else 0)

    def modify_stat_total_constraints(self, base_stats_by_attr, options):
        for stat in self.stats_list:
            restriction = self.restrictions.stat_total_constraints[stat.name]
            # The exo point is not part of the character's base any more: it
            # is the 'exo' variable, so that owning one on a piece and ticking
            # the option cannot add up to two.
            value = base_stats_by_attr.get(stat.name, 0)
            restriction.changeRHS(-value)
        self.modify_exo_constraints(options)

    def create_minimum_stat_constraints(self):
        dependencies = {'Dodge': [['Agility'],[0.1]],
                        'Lock': [['Agility'],[0.1]],
                        'AP Reduction': [['Wisdom'],[0.1]],
                        'MP Reduction': [['Wisdom'],[0.1]],
                        'AP Loss Resist': [['Wisdom'],[0.1]],
                        'MP Loss Resist': [['Wisdom'],[0.1]],
                        'Initiative': [['Agility', 'Intelligence', 'Strength', 'Chance'],
                                       [1, 1, 1, 1]],
                        'Prospecting': [['Chance'],[0.1]],
                        'Pods': [['Strength'],[5]],
                        'HP': [['Vitality'],[1]]}

        for stat in self.stats_list:
            if stat.name in dependencies:
                sec_stats = dependencies[stat.name][0]
                sec_stats_multipliers = dependencies[stat.name][1]
                matrix = []
                matrix.append((-1, 'stat', stat.id))
                for (i, sec_stat) in enumerate(sec_stats):
                    matrix.append((-sec_stats_multipliers[i], 
                                    'stat', 
                                    self.structure.get_stat_by_name(sec_stat).id))
                restriction = self.problem.restriction_lt_eq(-10000, matrix) 
            else:
                restriction = self.problem.restriction_lt_eq(-10000, [(-1, 'stat', stat.id)])  
            self.restrictions.minimum_stat_constraints[stat.name] = restriction
    
    def create_advanced_minimum_stat_constraints(self):
        adv_mins = self.structure.get_adv_mins()        
        
        for stat in adv_mins:
            matrix = []
            is_percent_resist_sum = all(stat_name.strip().startswith('%') and stat_name.strip().endswith('Resist') 
                                      for stat_name in stat['stats'])
            if is_percent_resist_sum:
                for stat_name in stat['stats']:
                    stat_obj = self.structure.get_stat_by_name(stat_name)
                    var_id = f"capped_{stat_obj.key}"
                    constraint_matrix = [(1, 'capped_resist', var_id), (-1, 'stat', stat_obj.id)]
                    self.problem.restriction_lt_eq(0, constraint_matrix)
                    matrix.append((-1, 'capped_resist', var_id))
            else:
                for stat_name in stat['stats']:
                    matrix.append((-1, 'stat', self.structure.get_stat_by_name(stat_name).id))
            
            restriction = self.problem.restriction_lt_eq(-10000, matrix)   
            self.restrictions.advanced_minimum_stat_constraints[stat['key']] = restriction

    def modify_minimum_stat_constraints(self, minimum_stats, level):
        for stat in self.stats_list:
            if stat.name == 'HP':
                restriction = self.restrictions.minimum_stat_constraints[stat.name]
                restriction.changeRHS(-minimum_stats.get(stat.name, -10000) + 55 + 5*(level-1))
            else:
                restriction = self.restrictions.minimum_stat_constraints[stat.name]
                restriction.changeRHS(-minimum_stats.get(stat.name, -10000))
        self.modify_advanced_minimum_stat_constraints(minimum_stats.get('adv_mins', {}))
    
    def modify_advanced_minimum_stat_constraints(self, minimum_stats):
        adv_min_stats = self.structure.get_adv_mins()
        for stat in adv_min_stats:
            restriction = self.restrictions.advanced_minimum_stat_constraints[stat['key']]
            restriction.changeRHS(-minimum_stats.get(stat['name'], -10000))
    
    def run(self, retries=0, change_of=False):
        if change_of:
            self.input['objective_values']['vit'] += 1
            self.write_objective_function(self.input['objective_values'], self.input['char_level'])
        try:
            self.problem.run()
        except pulp.PulpSolverError:
            if retries > 0:            
                self.run(retries-1, True)
            else:
                raise
                
    def get_result_string(self):
        if self.problem.get_status() == 'Infeasible':
            return 'Infeasible'
        
        result = ''
        
        lp_vars = self.problem.get_result()
        grouped_vars = {}
        for k, v in lp_vars.items():
            prefix, suffix = k.split('_', 1)
            group = grouped_vars.setdefault(prefix, {})
            group[suffix] = v
                
        result += ', '.join(grouped_vars) + '\n\n'
        
        result += 'Sets:\n'
        for k, v in grouped_vars['ss'].items():
            if v > 0:
                set_id, number_of_pieces = k.rsplit('_', 1)
                set_id = int(set_id)
                number_of_pieces = int(number_of_pieces) - 1
                if number_of_pieces > 1:
                    result += ('%s (%d pieces)\n' % (self.structure.get_set_by_id(set_id).name, number_of_pieces))
        result += '\nStats:\n'
        for stat in self.stats_list:
            result += '%s: %d\n' % (stat.name, grouped_vars['stat'][str(stat.id)])

        result += '\nGear:\n'
        for k, v in grouped_vars['x'].items():
            for _ in range(int(v)):
                result += self.structure.get_item_by_id(int(k)).name + '\n'
        return result
        
    def get_stats(self):
        lp_vars = self.problem.get_result()
        
        stats = {}
        for stat in self.main_stats_list: 
            stats[stat.key] = 0
            for i in range(0,6):
                sanitized_id = str(stat.id).replace(' ', '_').replace('-', '_')
                stats[stat.key] += int(lp_vars['stat_point_statpoint_%d_%s' % (i, sanitized_id)])
                #print '%s: tier %d - %d' % (stat.name, i, lp_vars['stat_point_statpoint_%d_%s' % (i, sanitized_id)])
                #if i < 5:                
                #    print 'y %s: tier %d - %d' % (stat.name, i, lp_vars['stat_point_max_statpointmax_%d_%s' % (i, sanitized_id)])
        return stats
        
    def get_result_minimal(self):
        item_id_list = []
   
        lp_vars = self.problem.get_result()
        grouped_vars = {}
        for k, v in lp_vars.items():
            prefix, suffix = k.split('_', 1)
            group = grouped_vars.setdefault(prefix, {})
            group[suffix] = v
        
        for k, v in grouped_vars['x'].items():
            for _ in range(int(v)):
                item = int(k)
                item_id_list.append(item)
                
        result = ModelResultMinimal.from_item_id_list(item_id_list, self.input, self.get_stats())
        return result

    def get_solved_status(self):
        return self.problem.get_status()


class ModelInput(object):

    def __init__(self, char_level, base_stats_by_attr, minimum_stats, locked_equips,
                 forbidden_equips, objective_values, options, char_class,
                 stat_points_to_distribute, empty_slot_types=None, stat_overrides=None):
        self.char_level = char_level
        self.base_stats_by_attr = base_stats_by_attr
        self.minimum_stats = minimum_stats
        self.locked_equips = locked_equips
        self.forbidden_equips = forbidden_equips
        self.objective_values = objective_values
        self.options = options
        self.char_class = char_class
        self.stat_points_to_distribute = stat_points_to_distribute
        self.empty_slot_types = empty_slot_types or []
        self.stat_overrides = stat_overrides or {}

    def get_old_input(self):
        return {'char_level': self.char_level,
                'base_stats_by_attr': self.base_stats_by_attr,
                'minimum_stats': self.minimum_stats,
                'locked_equips': self.locked_equips,
                'forbidden_equips': self.forbidden_equips,
                'objective_values': self.objective_values,
                'options': self.options,
                'origin': 'generated'}

    def cache_key(self):
        """A key the next process can compute again.

        `__hash__` below builds a tuple of strings -- the game version, the
        class, the stat names -- and `hash()` of a str is randomised per
        process. Its value therefore differs in every gunicorn worker and after
        every restart, while DatabaseSolutionMemory stores it in a column: a
        solve written before a restart can never be found again, and two
        workers never share one. Measured on the live site, steady since March:
        391 hits for 2 779 misses in the week of 24 August, near 12%.

        Sorting is not decoration. `repr()` of a set or a dict follows the
        order its members hash into, so a canonical form built on repr alone
        would move for the same reason.
        """
        from fashionistapulp.structure import get_current_game_version
        minimum_stats = dict(self.minimum_stats or {})
        adv_mins = minimum_stats.pop('adv_mins', None)
        return _stable_digest([
            get_current_game_version(),
            self.char_level,
            self.base_stats_by_attr,
            minimum_stats,
            adv_mins,
            self.locked_equips,
            sorted(self.forbidden_equips or [], key=repr),
            self.objective_values,
            self.options,
            self.char_class,
            self.stat_points_to_distribute,
            sorted(self.empty_slot_types or [], key=repr),
            self.stat_overrides,
        ])

    def __hash__(self, *args, **kwargs):
        # DatabaseSolutionMemory keys its cache by this hash, so it must include the game version.
        from fashionistapulp.structure import get_current_game_version
        overrides_key = frozenset(
            (item_id, frozenset(stats.items()))
            for item_id, stats in self.stat_overrides.items()
        )
        return (get_current_game_version(),
                self.char_level,
                freeze(self.base_stats_by_attr),
                frozenset([p for p in list(self.minimum_stats.items()) if p[0] != 'adv_mins']),
                freeze(self.minimum_stats.get('adv_mins')),
                freeze(self.locked_equips),
                frozenset(self.forbidden_equips),
                freeze(self.objective_values),
                freeze(self.options),
                self.char_class,
                self.stat_points_to_distribute,
                frozenset(self.empty_slot_types),
                overrides_key).__hash__()

def _canonical(value):
    """The same value in a shape that orders itself the same way everywhere."""
    if isinstance(value, dict):
        return ['d', sorted(([_canonical(k), _canonical(v)]
                             for k, v in value.items()), key=repr)]
    if isinstance(value, (set, frozenset)):
        return ['s', sorted((_canonical(v) for v in value), key=repr)]
    if isinstance(value, (list, tuple)):
        return ['l', [_canonical(v) for v in value]]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return ['r', repr(value)]


def _stable_digest(value):
    """A signed 64-bit int, the same in every process. SolutionMemory keys on
    a BigIntegerField, so the digest is cut to fit rather than widened."""
    payload = json.dumps(_canonical(value), sort_keys=True,
                         separators=(',', ':'), ensure_ascii=True)
    return int.from_bytes(hashlib.sha256(payload.encode('ascii')).digest()[:8],
                          'big', signed=True)


def freeze(d):
    if d is None:
        return None
    else:
        return frozenset(list(d.items()))
