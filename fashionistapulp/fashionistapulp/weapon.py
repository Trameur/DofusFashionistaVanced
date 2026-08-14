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

class Weapon:
    
    def __init__(self):
        self.crit_bonus = None
        self.crit_chance = None
        self.ap = None
        self.uses_per_turn = None
        self.weapon_type = None
        self.hits_dict = {}
        
        self.non_crit_hits = None
        self.crit_hits = None

    @property
    def crit_chance_percent(self):
        #return 55 - self.crit_chance
        return self.crit_chance

class WeaponType:
    
    def __init__(self):
        self.id = None
        self.name = None
        self.key = None
