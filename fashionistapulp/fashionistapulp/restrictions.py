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

class Restrictions:
    
    def __init__(self):
        self.type_constraints = {}
#        self.two_handed_constraints = {}
        self.first_presence_constraints = {}
        self.second_presence_constraints = {}
        self.level_constraints = {}
        self.forbidden_items_constraints = {}
        self.locked_equip_constraints = {}
        self.first_set_constraints = {}
        self.second_set_constraints = {}
        self.third_set_constraints = {}
        self.fourth_set_constraints = {}
        self.min_condition_contraints = {}
        self.max_condition_contraints = {}
        self.or_condition_contraints = {}
        self.or_item_count_constraints = {}
        self.or_branch_constraints = {}
        self.stat_total_constraints = {}
        self.exo_constraints = {}
        self.minimum_stat_constraints = {}
        self.advanced_minimum_stat_constraints = {}
        self.first_stats_points_constraints = {}
        self.second_stats_points_constraints = {}
        self.third_stats_points_constraints = {}
        self.fourth_stats_points_constraint = None
        self.set_max_cap_constraints = {}