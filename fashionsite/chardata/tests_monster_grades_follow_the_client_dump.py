# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 and Beta monster grades are the rows the version's own client dump gives."""
import os
import sqlite3

from django.test import SimpleTestCase

import fashionista_version
from fashionistapulp.fashionista_config import get_items_db_path

BLUE_LARVA = 31

GRADE_36 = {
    'grade': 1, 'level': 16, 'lifePoints': 90, 'actionPoints': 5, 'movementPoints': 2,
    'paDodge': 0, 'pmDodge': 0, 'earthResistance': 6, 'airResistance': -9,
    'fireResistance': 6, 'waterResistance': -9, 'neutralResistance': 1,
}
GRADE_37 = {
    'grade': 1, 'level': 16, 'lifePoints': 90, 'actionPoints': 5, 'movementPoints': 2,
    'paLostDodge': 0, 'mpLostDodge': 0, 'reductionEarth': 6, 'reductionAir': -9,
    'reductionFire': 6, 'reductionWater': -9, 'reductionNeutral': 1,
}


def _storer():
    from chardata.tests import itemscraper_module
    return itemscraper_module('store_monster_grades')


class GradeRowTests(SimpleTestCase):

    def test_both_schemas_give_the_same_row(self):
        storer = _storer()
        expected = (BLUE_LARVA, 1, 16, 90, 5, 2, 0, 0, 6, -9, 6, -9, 1)
        self.assertEqual(expected, storer.grade_row(BLUE_LARVA, GRADE_36))
        self.assertEqual(expected, storer.grade_row(BLUE_LARVA, GRADE_37))

    def test_a_grade_with_neither_or_both_schemas_raises(self):
        storer = _storer()
        neither = {key: value for key, value in GRADE_37.items() if key != 'reductionAir'}
        both = dict(GRADE_36, **GRADE_37)
        for grade in (neither, both):
            with self.assertRaises(storer.UnknownGradeSchema):
                storer.grade_row(BLUE_LARVA, grade)

    def test_a_grade_without_life_points_or_level_is_dropped(self):
        storer = _storer()
        self.assertIsNone(storer.grade_row(BLUE_LARVA, dict(GRADE_37, lifePoints=0)))
        self.assertIsNone(storer.grade_row(BLUE_LARVA, dict(GRADE_37, level=0)))

    def test_negative_ap_and_mp_are_stored_as_null(self):
        storer = _storer()
        row = storer.grade_row(BLUE_LARVA, dict(GRADE_37, actionPoints=-1, movementPoints=-100))
        columns = dict(zip(storer.COLUMNS, row))
        self.assertIsNone(columns['action_points'])
        self.assertIsNone(columns['movement_points'])
        row = storer.grade_row(BLUE_LARVA, dict(GRADE_37, actionPoints=0, movementPoints=0))
        columns = dict(zip(storer.COLUMNS, row))
        self.assertEqual((0, 0), (columns['action_points'], columns['movement_points']))

    def test_too_few_rows_or_a_null_resistance_stops_the_store(self):
        storer = _storer()
        row = storer.grade_row(BLUE_LARVA, GRADE_37)
        with self.assertRaises(ValueError):
            storer.check_rows([row] * (storer.MIN_ROWS - 1))
        broken = row[:8] + (None,) + row[9:]
        with self.assertRaises(ValueError):
            storer.check_rows([row] * storer.MIN_ROWS + [broken])


class StoredGradesMatchTheDumpTests(SimpleTestCase):
    VERSIONS = {'dofus3': fashionista_version.FASHIONISTA_VERSION}

    def test_the_table_holds_the_rows_the_dump_gives(self):
        storer = _storer()
        for version, tag in self.VERSIONS.items():
            with self.subTest(version=version, tag=tag):
                path = os.path.join(storer.RAW_ROOT, tag, 'monsters.json')
                if not os.path.exists(path):
                    self.skipTest('raw/%s not fetched on this machine' % tag)
                conn = sqlite3.connect(get_items_db_path(version))
                try:
                    known = {row[0] for row in conn.execute(
                        'SELECT DISTINCT monster_ankama_id FROM monster_names')}
                    stored = set(conn.execute(
                        'SELECT %s FROM monster_grades' % ', '.join(storer.COLUMNS)))
                finally:
                    conn.close()
                rows, _empty, _unnamed = storer.build_rows(storer._table(path), known)
                built = set(rows)
                self.assertEqual(len(rows), len(built))
                self.assertEqual([], sorted(built - stored, key=str)[:5])
                self.assertEqual([], sorted(stored - built, key=str)[:5])
