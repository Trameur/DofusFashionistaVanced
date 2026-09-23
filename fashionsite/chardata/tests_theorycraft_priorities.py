from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase


class TheorycraftPrioritiesTests(SimpleTestCase):
    def test_the_highest_non_zero_weights_are_named_and_limited(self):
        from chardata import solution_view

        stats = [SimpleNamespace(key=key, name=name)
                 for key, name in (('vit', 'Vitality'),
                                   ('str', 'Strength'),
                                   ('fire', 'Fire Damage'),
                                   ('wis', 'Wisdom'),
                                   ('ap', 'AP'),
                                   ('mp', 'MP'))]
        weights = {'vit': 10, 'str': -80, 'fire': 50, 'wis': 0,
                   'ap': 30, 'mp': 20}
        char = SimpleNamespace(id=1)

        with mock.patch.object(solution_view, 'get_stats_weights',
                               return_value=weights), \
             mock.patch.object(solution_view, 'get_structure') as structure:
            structure.return_value.get_stats_list.return_value = stats
            result = solution_view._solver_priorities(char)

        self.assertEqual(
            [{'name': 'Strength', 'weight': -80},
             {'name': 'Fire Damage', 'weight': 50},
             {'name': 'AP', 'weight': 30},
             {'name': 'MP', 'weight': 20},
             {'name': 'Vitality', 'weight': 10}],
            result)

    def test_the_solution_template_has_a_place_for_the_priority_summary(self):
        import io
        import os

        path = os.path.join(os.path.dirname(__file__), 'templates', 'chardata',
                            'solution.html')
        source = io.open(path, encoding='utf-8').read()
        self.assertIn('solver_priorities', source)
        self.assertIn('solver-priority', source)
        self.assertIn('solver-why-best-turn', source)

    def test_positive_percentage_resistances_are_named_from_the_solution(self):
        from chardata import solution_view

        stats = [SimpleNamespace(key='earthresper', name='% Earth Resist'),
                 SimpleNamespace(key='fireresper', name='% Fire Resist')]
        totals = '{"earthresper": 30, "fireresper": 0}'

        with mock.patch.object(solution_view, 'get_structure') as structure:
            structure.return_value.get_stat_by_key.side_effect = (
                lambda key: next((stat for stat in stats if stat.key == key),
                                 None))
            result = solution_view._solver_resistances(totals)

        self.assertEqual([{'name': '% Earth Resist', 'value': 30}], result)
