# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The item dump writes each weapon's range, the Dofus 3 database holds it, and a database without the table reads no range."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ITEMSCRAPER = os.path.join(ROOT, 'itemscraper')
EROTEGG_BOW = 32235
CHAOTIC_SCYTHE = 26011
OTHER_VERSIONS = ('beta', 'dofus2', 'touch', 'retro')


def _transformed():
    with open(os.path.join(ITEMSCRAPER, 'transformed_equipment.json'), encoding='utf-8') as handle:
        return json.load(handle)


def _read(version, query):
    from fashionistapulp.fashionista_config import get_items_db_path
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return list(conn.execute(query))
    finally:
        conn.close()


def _has_range_table(version):
    return bool(_read(version, "SELECT name FROM sqlite_master WHERE type = 'table'"
                               " AND name = 'weapon_range'"))


class TheDumpWritesEachWeaponRangeTests(SimpleTestCase):

    def test_a_weapon_range_lands_in_weapon_range_and_a_piece_without_one_does_not(self):
        records = _transformed()
        picked = [record for record in records
                  if record.get('ankama_id') in (EROTEGG_BOW, CHAOTIC_SCYTHE)]
        hat = next(record for record in records
                   if record.get('w_type') == 'Hat' and 'range' not in record
                   and not record.get('or_branch_count'))
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, 'transformed_equipment.json'), 'w',
                      encoding='utf-8') as handle:
                json.dump(picked + [hat], handle)
            with open(os.path.join(directory, 'transformed_sets.json'), 'w',
                      encoding='utf-8') as handle:
                json.dump([], handle)
            dump = os.path.join(directory, 'items.dump')
            done = subprocess.run([sys.executable, 'get_equipments3.py', '--input-dir', directory,
                                   '--dump-output', dump], cwd=ITEMSCRAPER, capture_output=True,
                                  text=True, timeout=120,
                                  env={key: value for key, value in os.environ.items()
                                       if key != 'PYTHONPATH'})
            self.assertEqual(0, done.returncode, done.stderr)
            database = sqlite3.connect(':memory:')
            with open(dump, encoding='utf-8') as handle:
                database.executescript(handle.read())
        rows = sorted(database.execute(
            'SELECT items.ankama_id, min_value, max_value FROM weapon_range'
            ' JOIN items ON items.id = weapon_range.item'))
        self.assertEqual([(CHAOTIC_SCYTHE, 1, 2), (EROTEGG_BOW, 3, 7)], rows)


class TheDofus3DatabaseHoldsEveryWeaponRangeTests(SimpleTestCase):

    def test_every_weapon_with_ap_has_exactly_one_range(self):
        with_ap = {item for (item,) in _read('dofus3', 'SELECT item FROM weapon_ap')}
        ranged = [item for (item,) in _read('dofus3', 'SELECT item FROM weapon_range')]
        self.assertEqual(len(ranged), len(set(ranged)))
        self.assertEqual(with_ap, set(ranged))

    def test_the_ranges_are_the_transformed_equipment_ones(self):
        expected = {record['ankama_id']: {tuple(record['range'])}
                    for record in _transformed() if record.get('range')}
        stored = {}
        for ankama_id, lowest, farthest in _read(
                'dofus3', 'SELECT items.ankama_id, min_value, max_value FROM weapon_range'
                          ' JOIN items ON items.id = weapon_range.item'):
            stored.setdefault(ankama_id, set()).add((lowest, farthest))
        self.assertEqual(expected, stored)

    def test_the_structure_reads_a_weapon_range(self):
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        for item_id, expected in ((EROTEGG_BOW, (3, 7)), (CHAOTIC_SCYTHE, (1, 2))):
            with self.subTest(item_id=item_id):
                weapon = structure.get_weapon_for_item(structure.get_item_by_id(item_id))
                self.assertEqual(expected, weapon.range)


class AVersionWithoutTheTableReadsNoRangeTests(SimpleTestCase):

    def test_a_database_without_the_table_gives_no_weapon_a_range(self):
        from fashionistapulp.structure import get_structure
        without = [version for version in OTHER_VERSIONS if not _has_range_table(version)]
        self.assertTrue(without)
        for version in without:
            with self.subTest(version=version):
                structure = get_structure(version)
                ranged = [item.id for item in structure.get_available_items_list()
                          if structure.get_type_name_by_id(item.type) == 'Weapon'
                          and getattr(structure.get_weapon_for_item(item), 'range', None)
                          is not None]
                self.assertEqual([], ranged)
