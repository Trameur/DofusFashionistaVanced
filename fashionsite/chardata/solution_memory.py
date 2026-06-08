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
import datetime
import pickle

from django.db.models import F

from chardata.models import SolutionCounter, SolutionMemory, SolutionMemoryHits
from fashionistapulp.structure import get_current_game_version

THRESHOLD = 1

class EmptySolutionMemory(object):

    def get(self, model_input):
        return None

    def put(self, input_hash, result_tuple):
        pass

class DebugSolutionMemory(object):

    def __init__(self):
        self.memory = {}
        self.demand_counter = Counter()

    def get(self, model_input):
        input_hash = model_input.__hash__()
        self.demand_counter[input_hash] += 1
        return self.memory.get(input_hash)

    def put(self, model_input, result_tuple):
        input_hash = model_input.__hash__()
        if self.demand_counter[input_hash] >= THRESHOLD:
            self.memory[input_hash] = result_tuple

# TODO: Do not back up the solution cache.
# TODO: Create script to read most popular inputs.
# TODO: Create cronjob to clean up stale solutions in the cache.
class DatabaseSolutionMemory(object):

    def __init__(self):
        pass

    def get(self, model_input):
        today = datetime.date.today()
        input_hash = model_input.__hash__()
        SolutionCounter.objects.get_or_create(
            input_hash=input_hash,
            defaults={'game_version': get_current_game_version()})
        SolutionCounter.objects.filter(input_hash=input_hash).update(get_count=F('get_count')+1)
        memoized_solution = SolutionMemory.objects.filter(input_hash=input_hash).first()
        SolutionMemoryHits.objects.get_or_create(day=today)
        todays_state = SolutionMemoryHits.objects.filter(day=today)
        if memoized_solution is None:
            todays_state.update(count_miss=F('count_miss')+1)
            return None
        else:
            todays_state.update(count_hit=F('count_hit')+1)
            return pickle.loads(memoized_solution.stored)
        
    def put(self, model_input, result_tuple):
        input_hash = model_input.__hash__()
        SolutionCounter.objects.get_or_create(
            input_hash=input_hash,
            defaults={'game_version': get_current_game_version()})
        counter = SolutionCounter.objects.filter(input_hash=input_hash).first()

        if counter.get_count >= THRESHOLD:
            # Guard against race conditions.
            already_present = SolutionMemory.objects.filter(input_hash=input_hash).exists()
            if not already_present:
                solution = SolutionMemory(input_hash=input_hash,
                                          input=pickle.dumps(model_input),
                                          stored=pickle.dumps(result_tuple))
                solution.save()
