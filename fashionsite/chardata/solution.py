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
from django.utils import timezone
from chardata.util import get_stats_and_scrolled
from chardata.inventory_solver import get_effective_stat_overrides
from chardata.legacy_ids import repair_minimal_solution


def _repair_character_base(char, minimal_solution):
    """Fill in the level-based base stats a solution lacks, without rewriting it."""
    from chardata.util import character_own_stats
    entree = getattr(minimal_solution, 'input', None)
    if not isinstance(entree, dict):
        return
    base = entree.get('base_stats_by_attr')
    if base is None:
        base = entree['base_stats_by_attr'] = {}
    if 'AP' in base:
        return
    for stat, value in character_own_stats(char.level).items():
        base.setdefault(stat, value)


def get_solution_from_minimal(char, minimal_solution, refresh_base_stats=True):
    if minimal_solution:
        _repair_character_base(char, minimal_solution)
        # Pieces left under pre-migration ids, repaired on read
        repair_minimal_solution(char, minimal_solution)
        if refresh_base_stats or not getattr(minimal_solution, 'stats', None):
            spent, scrolled = get_stats_and_scrolled(char)
            minimal_solution.update_base_stats(spent, scrolled)
        stat_overrides = get_effective_stat_overrides(char) or None
        return model_result_from_minimal(minimal_solution, stat_overrides)
    return None


def get_solution_from_blob(char, minimal_solution_blob, refresh_base_stats=True):
    if minimal_solution_blob:
        return get_solution_from_minimal(char, pickle.loads(minimal_solution_blob),
                                         refresh_base_stats)
    return None


def get_solution(char):
    if char.minimal_solution:
        return get_solution_from_blob(char, char.minimal_solution)
    return None

def get_solver_facts(minimal_solution_blob):
    """(proven, seconds, candidate pool), each None when the solution predates it."""
    if not minimal_solution_blob:
        return None, None, None
    try:
        minimal = pickle.loads(minimal_solution_blob)
    except Exception:
        return None, None, None
    return (getattr(minimal, 'proven', None),
            getattr(minimal, 'solve_seconds', None),
            getattr(minimal, 'candidate_pool', None))


def set_solution(char, solution):
    set_minimal_solution(char, ModelResultMinimal.from_model_result(solution))

def wears_something(solution):
    """Whether a solution dresses the character: the gate on publishing."""
    par_emplacement = getattr(solution, 'item_per_slot', None) or {}
    return any(par_emplacement.values())


def set_minimal_solution(char, solution):
    char.minimal_solution = pickle.dumps(solution)
    char.stuff_time = timezone.now()
    # Public by default: published the first time it is dressed, unless already chosen
    if char.auto_publish and not char.link_shared and wears_something(solution):
        char.link_shared = True
    char.save()
