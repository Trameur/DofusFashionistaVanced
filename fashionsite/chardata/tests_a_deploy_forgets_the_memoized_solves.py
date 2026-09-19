# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A deploy forgets the memoized solves, and only them.

Thibaud, 2026-09-18: "en general il faut vider le cache lors d'un deploy, car
95% du temps un deploy c'est suite a une modif de donnees". The solver's memory
is keyed on the player's request alone, so it outlives the data it was solved
on. docker-entrypoint.sh now runs clear_solution_cache at every boot.
"""
import io
import os

from django.core.management import call_command
from django.test import TestCase

from chardata.models import SolutionCounter, SolutionMemory

ENTRYPOINT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'docker-entrypoint.sh')


class ADeployForgetsTheMemoizedSolvesTests(TestCase):

    def test_the_command_empties_the_memory_and_leaves_the_counters(self):
        for number in range(3):
            SolutionMemory.objects.create(input_hash=number, input=b'i',
                                          stored=b's')
        SolutionCounter.objects.create(input_hash=1)
        printed = io.StringIO()
        call_command('clear_solution_cache', stdout=printed)
        self.assertEqual(0, SolutionMemory.objects.count())
        self.assertEqual(1, SolutionCounter.objects.count())
        self.assertIn('Forgot 3 memoized solve(s).', printed.getvalue())

    def test_the_container_runs_it_after_the_migrations(self):
        with open(ENTRYPOINT, encoding='utf-8') as handle:
            script = handle.read()
        self.assertIn('manage.py clear_solution_cache', script)
        self.assertLess(script.index('manage.py migrate'),
                        script.index('manage.py clear_solution_cache'))
        self.assertLess(script.index('manage.py clear_solution_cache'),
                        script.index('exec gunicorn'))
