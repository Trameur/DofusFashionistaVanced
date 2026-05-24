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

from fashionistapulp.modelresult import model_result_from_minimal, ModelResultMinimal

import pickle
from chardata.util import get_stats, get_scrolled_stats
from chardata.lock_forbid import get_stat_overrides

def get_solution(char):
    if char.minimal_solution:
        minimal_solution = pickle.loads(char.minimal_solution)
        if minimal_solution:
            minimal_solution.update_base_stats(get_stats(char), get_scrolled_stats(char))
            stat_overrides = get_stat_overrides(char) or None
            return model_result_from_minimal(minimal_solution, stat_overrides)
    return None

def set_solution(char, solution):
    set_minimal_solution(char, ModelResultMinimal.from_model_result(solution))

def set_minimal_solution(char, solution):
    char.minimal_solution = pickle.dumps(solution)
    char.save()
