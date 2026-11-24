# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A well-formed token naming no monster or no grade is refused without a database read or a memo entry."""
from unittest import mock

from django.test import SimpleTestCase

from chardata import targets
from chardata.targets import _monster_index, read_target


class TheTargetMemoIsBoundedTests(SimpleTestCase):

    def test_tokens_of_unknown_monsters_and_grades_add_nothing(self):
        for version in targets.TARGET_VERSIONS:
            entries = _monster_index(version)[0]
            known = entries[0][0]
            biggest = max(entry[0] for entry in entries)
            grades = {grade for grade, _level, _hp in entries[0][2]}
            before = dict(targets._GRADES)
            with mock.patch.object(targets, '_connect', side_effect=AssertionError('read')):
                for offset in range(1, 40):
                    self.assertEqual((None, 'monster'),
                                     read_target(version, 'm%d.1' % (biggest + offset)))
                    unknown_grade = max(grades) + offset
                    if unknown_grade < 1000:
                        self.assertEqual((None, 'grade'),
                                         read_target(version, 'm%d.%d' % (known, unknown_grade)))
            with self.subTest(version=version):
                self.assertEqual(before, targets._GRADES)
