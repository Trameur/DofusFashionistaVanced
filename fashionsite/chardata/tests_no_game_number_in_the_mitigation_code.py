# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The combat code holds no game number: only 0, 1 and the 100 of a percentage; the rest comes from the records."""
import ast
import os

from django.test import SimpleTestCase

from fashionistapulp import combat

ALLOWED = (0, 1, 100)


def _sources():
    folder = os.path.dirname(os.path.abspath(combat.__file__))
    return sorted(os.path.join(folder, name) for name in os.listdir(folder)
                  if name.endswith('.py'))


def numbers_in(source):
    """[(line, value)] of every numeric literal outside the allowed ones."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Constant) and type(node.value) in (int, float, complex)
                and node.value not in ALLOWED):
            found.append((node.lineno, node.value))
    return found


class NoGameNumberTests(SimpleTestCase):

    def test_the_combat_package_has_sources(self):
        self.assertIn('mitigation.py', [os.path.basename(path) for path in _sources()])

    def test_no_numeric_literal_but_zero_one_and_a_hundred(self):
        for path in _sources():
            with open(path, encoding='utf-8') as handle:
                source = handle.read()
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual([], numbers_in(source))

    def test_the_check_sees_a_cap_written_in(self):
        self.assertEqual([(1, 50)], numbers_in('cap = min(value, 50)\n'))
        self.assertEqual([(1, 0.5)], numbers_in('half = value * 0.5\n'))
        self.assertEqual([], numbers_in('kept = value * (100 - percent) / 100.0\n'))

    def test_the_player_cap_is_read_from_the_version(self):
        with open(os.path.join(os.path.dirname(_sources()[0]), 'mitigation.py'),
                  encoding='utf-8') as handle:
            self.assertIn('percent_resist_cap(', handle.read())
