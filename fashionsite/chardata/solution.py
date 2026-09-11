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
from chardata.util import get_stats_and_scrolled
from chardata.inventory_solver import get_effective_stat_overrides


def _repair_character_base(char, minimal_solution):
    """Fill the five the character has of their own, when they are missing.

    A build imported before 2026-09-11 was saved with an EMPTY
    `base_stats_by_attr`, so its sheet was short of seven AP, three MP, a
    hundred prospecting, a thousand pods and one summon, and its "best combo
    this turn" panel vanished because a turn with two AP has nothing to
    cast. The cause is fixed where the build is placed; this repairs the
    ones already saved, as they are read.

    Nothing is rewritten in the database ([[no-retrofit-user-builds]]): the
    five depend on the level alone, so this costs no query and no migration.
    A solution that already carries them is left exactly as it is.
    """
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
    """(proven, seconds, candidate pool), each None when it predates them.

    Read from the pickled minimal solution and not from the ModelResult the
    page works with: model_result_from_minimal builds a different object and
    these facts do not survive the trip, which is exactly how they came
    back missing the first time they were wired up.

    None means the solver never told us, and the panel then shows nothing.
    False means it told us the answer is NOT proved, which is the case the
    reader most needs, so the two must never be conflated.
    """
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
    """Whether a solution actually dresses the character.

    The one gate on publishing: an empty solution is a build nobody has
    finished, and the gallery is not a list of empty drafts. Read from
    `item_per_slot`, the same field the gallery reads to draw a build's
    preview, so a build that would show as an empty frame there cannot get
    in.
    """
    par_emplacement = getattr(solution, 'item_per_slot', None) or {}
    return any(par_emplacement.values())


def set_minimal_solution(char, solution):
    char.minimal_solution = pickle.dumps(solution)
    # Public by default, from 2026-09-11: a build made by a logged in author
    # becomes visible the first time it is dressed, unless somebody has
    # already chosen. `auto_publish` is False on every build that existed
    # before that day and on every guest build, so neither is touched here.
    if char.auto_publish and not char.link_shared and wears_something(solution):
        char.link_shared = True
    char.save()
