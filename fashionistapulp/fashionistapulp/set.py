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

class Set:
    
    def __init__(self):
        self.id = None
        self.name = None
        self.ankama_id = None
        self.bonus = []
        self.bonus_per_num_items = {}
        self.max_caps = []  # list of (num_items, stat_id, max_value)
        self.items = []
        self.localized_names = {}
        self.dofus_touch = False

    def add_item(self, item_id):
        self.items.append(item_id)

    def get_num_items(self):
        return max(self.bonus_per_num_items)
