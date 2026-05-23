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

class Item:
    
    def __init__(self):
        self.id = None
        self.name = None
        self.or_name = None # Canonical name for items like Bubotron Sword and Gelano
        self.type = None
        self.level = None
        self.set = None
        self.ankama_id = None
        self.ankama_type = None
        self.is_one_handed = False
        self.stats = []
        self.min_stats_to_equip = []
        self.max_stats_to_equip = []
        self.localized_extras = {}
        self.flags = []
        self.localized_names = {}
        self.accentless_local_names = {}
        self.weird_conditions = {'light_set': False, 'prysmaradite': False}
        self.removed = False
        self.dofus_touch = False

    def __repr__(self):
        return '[%d]%s' % (self.id, self.name)
