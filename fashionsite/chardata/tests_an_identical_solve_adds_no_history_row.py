# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Recording a solution identical to the latest history row of the build leaves the history as it was."""

from chardata.models import SolutionGeneration
from chardata.solution_history import record_solution_generation
from django.test import TestCase

from chardata.tests import SolutionGenerationHistoryTests


class AnIdenticalSolveAddsNoHistoryRowTests(TestCase):

    _build_char_with_items = SolutionGenerationHistoryTests._build_char_with_items
    _base_input = staticmethod(SolutionGenerationHistoryTests._base_input)

    def _minimal(self, hat, strength):
        from fashionistapulp.modelresult import ModelResultMinimal
        return ModelResultMinimal({'hat': hat.id}, self._base_input(), {'str': strength})

    def test_the_same_solution_twice_leaves_one_row(self):
        owner, char, hats = self._build_char_with_items()
        first = record_solution_generation(char, self._minimal(hats[0], 1))
        second = record_solution_generation(char, self._minimal(hats[0], 1))
        self.assertEqual(first.id, second.id)
        self.assertEqual(SolutionGeneration.objects.filter(char=char).count(), 1)

    def test_a_different_solution_still_adds_a_row(self):
        owner, char, hats = self._build_char_with_items()
        record_solution_generation(char, self._minimal(hats[0], 1))
        record_solution_generation(char, self._minimal(hats[0], 2))
        self.assertEqual(SolutionGeneration.objects.filter(char=char).count(), 2)

    def test_going_back_to_an_older_solution_adds_a_row(self):
        owner, char, hats = self._build_char_with_items()
        record_solution_generation(char, self._minimal(hats[0], 1))
        record_solution_generation(char, self._minimal(hats[0], 2))
        record_solution_generation(char, self._minimal(hats[0], 1))
        self.assertEqual(SolutionGeneration.objects.filter(char=char).count(), 3)
