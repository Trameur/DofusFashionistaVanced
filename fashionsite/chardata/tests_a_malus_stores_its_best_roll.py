# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A ranged stat stores its best roll: the maximum for a bonus, the end nearest zero for a malus."""
import os
import sqlite3
import unittest

from django.test import SimpleTestCase

from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

# (item, stat, best roll, worst roll), one malus example per version
EXAMPLES = {
    'dofus3': ('Abdominable Belt', 'AP Reduction', -3, -4),
    'beta': ('Abdominable Belt', 'AP Reduction', -3, -4),
    'dofus2': ('Abdominable Belt', 'AP Reduction', -3, -4),
    'touch': ('1001 Claws Torque', 'Initiative', -101, -150),
    'retro': ('Abipaca Shovel', 'Vitality', -27, -35),
}


def _connect(version):
    path = get_items_db_path(version)
    if not os.path.exists(path):
        raise unittest.SkipTest('%s is absent' % path)
    return sqlite3.connect('file:%s?mode=ro' % path, uri=True)


class AMalusStoresItsBestRollTests(SimpleTestCase):

    def test_every_ranged_line_stores_its_larger_end(self):
        for version in VERSIONS:
            connection = _connect(version)
            try:
                rows = connection.execute(
                    'SELECT i.name, st.name, s.value, s.min_value, s.max_value'
                    ' FROM stats_of_item s JOIN items i ON i.id = s.item'
                    ' JOIN stats st ON st.id = s.stat'
                    ' WHERE s.min_value IS NOT NULL'
                    ' AND s.value <> s.max_value').fetchall()
                ranged = connection.execute(
                    'SELECT COUNT(*) FROM stats_of_item'
                    ' WHERE min_value IS NOT NULL').fetchone()[0]
            finally:
                connection.close()
            with self.subTest(version=version):
                self.assertGreater(ranged, 10000, msg='the ranges are gone')
                self.assertEqual([], rows[:5], msg='%d rows' % len(rows))

    def test_a_known_malus_holds_the_end_nearest_zero(self):
        for version, (item, stat, best, worst) in EXAMPLES.items():
            connection = _connect(version)
            try:
                row = connection.execute(
                    'SELECT s.value, s.min_value, s.max_value'
                    ' FROM stats_of_item s JOIN items i ON i.id = s.item'
                    ' JOIN stats st ON st.id = s.stat'
                    ' WHERE i.name = ? AND st.name = ?',
                    (item, stat)).fetchone()
            finally:
                connection.close()
            with self.subTest(version=version, item=item):
                self.assertIsNotNone(row, msg='the item this test names is gone')
                self.assertEqual((best, worst, best), row)
