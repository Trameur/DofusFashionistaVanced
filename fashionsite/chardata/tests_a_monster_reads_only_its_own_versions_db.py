# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A monster grade is read from its own version's database, named in the page language, with missing columns read as unknown."""
import os
import pathlib
import shutil
import sqlite3
import tempfile
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata import targets
from chardata.targets import (ELEMENTS, TARGET_VERSIONS, monster_target, read_target,
                              search_monsters)
from fashionistapulp.fashionista_config import get_items_db_path

FULL = ('level', 'life_points', 'earth_resistance', 'fire_resistance', 'water_resistance',
        'air_resistance', 'neutral_resistance', 'earth_flat_resistance',
        'fire_flat_resistance', 'water_flat_resistance', 'air_flat_resistance',
        'neutral_flat_resistance', 'critical_damage_reduction', 'push_damage_reduction')


def _ids(version):
    conn = sqlite3.connect('file:%s?mode=ro' % get_items_db_path(version).replace('\\', '/'),
                           uri=True)
    try:
        return {row[0] for row in conn.execute(
            'SELECT DISTINCT monster_ankama_id FROM monster_grades')}
    finally:
        conn.close()


def _write_db(path, columns, grades, names):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE monster_grades (monster_ankama_id INTEGER, grade INTEGER, %s)'
                 % ', '.join('%s INTEGER' % column for column in columns))
    for row in grades:
        conn.execute('INSERT INTO monster_grades VALUES (%s)' % ', '.join('?' * len(row)), row)
    conn.execute('CREATE TABLE monster_names (monster_ankama_id INTEGER, language TEXT, '
                 'name TEXT)')
    conn.executemany('INSERT INTO monster_names VALUES (?, ?, ?)', names)
    conn.commit()
    conn.close()


class _FreshMemo(object):

    def _fresh(self):
        saved = (dict(targets._GRADES), dict(targets._INDEX))
        targets._GRADES.clear()
        targets._INDEX.clear()

        def restore():
            targets._GRADES.clear()
            targets._INDEX.clear()
            targets._GRADES.update(saved[0])
            targets._INDEX.update(saved[1])

        self.addCleanup(restore)


class TwoVersionsOnDiskTests(_FreshMemo, SimpleTestCase):
    """Two small databases standing for the two versions."""

    def setUp(self):
        self._fresh()
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        self.paths = {'dofus3': os.path.join(folder, 'one.db'),
                      'beta': os.path.join(folder, 'two.db')}
        both = (7, 1) + tuple(range(10, 10 + len(FULL)))
        _write_db(self.paths['dofus3'], FULL,
                  [both, (8, 1) + (None,) * len(FULL)],
                  [(7, 'en', 'Shared one'), (7, 'fr', 'Commun un'), (8, 'en', 'Blank one')])
        _write_db(self.paths['beta'], ('level', 'life_points', 'earth_resistance'),
                  [(7, 1, 200, 5000, 30), (9, 2, 150, 4000, -20)],
                  [(7, 'en', 'Shared one renamed'), (9, 'en', 'Beta only'),
                   (9, 'fr', 'Seulement beta')])
        patcher = mock.patch.object(targets, 'get_items_db_path',
                                    side_effect=lambda version: self.paths[version])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_monster_of_one_version_is_not_found_on_the_other(self):
        self.assertEqual('beta', read_target('beta', 'm9.2')[0].version)
        self.assertEqual((None, 'monster'), read_target('dofus3', 'm9.2'))
        self.assertEqual((None, 'grade'), read_target('beta', 'm7.2'))
        self.assertEqual((None, 'monster'), read_target('beta', 'm8.1'))

    def test_the_name_comes_from_that_versions_names_in_the_page_language(self):
        self.assertEqual('Commun un', monster_target('dofus3', 7, 1, 'fr').label)
        self.assertEqual('Shared one', monster_target('dofus3', 7, 1, 'en').label)
        self.assertEqual('Shared one renamed', monster_target('beta', 7, 1, 'fr').label)
        with translation.override('fr'):
            self.assertEqual('Seulement beta', read_target('beta', 'm9.2')[0].label)
            self.assertEqual(['Seulement beta'],
                             [found['name'] for found in search_monsters('beta', 'seulement')])
            self.assertEqual([], search_monsters('dofus3', 'seulement'))

    def test_each_version_reads_its_own_values(self):
        own = monster_target('dofus3', 7, 1)
        beta = monster_target('beta', 7, 1)
        self.assertEqual((10, 11), (own.level, own.hp))
        self.assertEqual((200, 5000), (beta.level, beta.hp))
        self.assertEqual(12, own.percent_of(ELEMENTS[0]))
        self.assertEqual(30, beta.percent_of(ELEMENTS[0]))

    def test_a_null_or_absent_column_reads_unknown_not_zero(self):
        blank = monster_target('dofus3', 8, 1)
        self.assertIsNone(blank.hp)
        self.assertEqual([None] * len(ELEMENTS), [blank.percent_of(element)
                                                  for element in ELEMENTS])
        self.assertIsNone(blank.flat)
        self.assertEqual(set(FULL), set(blank.unknown))
        beta = monster_target('beta', 9, 2)
        self.assertEqual(-20, beta.percent_of(ELEMENTS[0]))
        self.assertEqual([None] * (len(ELEMENTS) - 1),
                         [beta.percent_of(element) for element in ELEMENTS[1:]])
        self.assertEqual(set(FULL) - {'level', 'life_points', 'earth_resistance'},
                         set(beta.unknown))
        self.assertEqual([], beta.immune_elements())


class TheGameDatabasesTests(_FreshMemo, SimpleTestCase):
    """The databases the site ships."""

    def setUp(self):
        self._fresh()

    def test_a_monster_only_beta_has_reads_not_found_on_dofus3(self):
        only_beta = sorted(_ids('beta') - _ids('dofus3'))
        if not only_beta:
            self.skipTest('every beta monster is also on dofus3')
        token = 'm%d.1' % only_beta[0]
        target, refused = read_target('beta', token)
        if target is None:
            self.skipTest('that beta monster has no first grade')
        self.assertEqual('', refused)
        self.assertEqual((None, 'monster'), read_target('dofus3', token))

    def test_each_version_opens_only_its_own_file(self):
        opened = []
        real = targets._connect

        def watched(version):
            opened.append(version)
            return real(version)

        shared = sorted(_ids('beta') & _ids('dofus3'))[0]
        with mock.patch.object(targets, '_connect', watched):
            for version in ('dofus3', 'beta'):
                del opened[:]
                read_target(version, 'm%d.1' % shared)
                with self.subTest(version=version):
                    self.assertTrue(opened)
                    self.assertEqual({version}, set(opened))

    def test_every_target_version_opens_only_its_own_file(self):
        files = {version: pathlib.Path(get_items_db_path(version)).resolve()
                 for version in TARGET_VERSIONS}
        self.assertEqual(len(TARGET_VERSIONS), len(set(files.values())))
        first = {version: min(_ids(version)) for version in TARGET_VERSIONS}
        opened = []
        real = sqlite3.connect

        def watched(database, *args, **kwargs):
            opened.append(str(database).split('?')[0])
            return real(database, *args, **kwargs)

        with mock.patch.object(targets.sqlite3, 'connect', watched):
            for version in TARGET_VERSIONS:
                del opened[:]
                target = monster_target(version, first[version], 1)
                search_monsters(version, str(first[version]))
                with self.subTest(version=version):
                    self.assertTrue(opened)
                    self.assertEqual({files[version].as_uri()}, set(opened))
                    if target is not None:
                        self.assertEqual(version, target.version)

    def test_a_monster_one_version_lacks_reads_not_found_there(self):
        for version in ('dofus2', 'touch', 'retro'):
            for other in TARGET_VERSIONS:
                if other == version:
                    continue
                missing = sorted(_ids(version) - _ids(other))
                if not missing:
                    continue
                with self.subTest(version=version, other=other):
                    self.assertEqual((None, 'monster'), read_target(other, 'm%d.1' % missing[0]))
                    found, refused = read_target(version, 'm%d.1' % missing[0])
                    if found is not None:
                        self.assertEqual(('', version), (refused, found.version))

    def test_the_same_monster_reads_each_versions_own_values(self):
        shared = sorted(_ids('touch') & _ids('retro') & _ids('dofus2'))
        differs = False
        for monster in shared[:40]:
            seen = {}
            for version in ('touch', 'retro', 'dofus2'):
                target = monster_target(version, monster, 1)
                if target is not None:
                    seen[version] = (target.level, target.hp,
                                     tuple(target.percent_of(element) for element in ELEMENTS))
            differs = differs or len(set(seen.values())) > 1
        self.assertTrue(differs)

    def test_a_version_without_targets_reads_none(self):
        for version in ('touchbeta', 'retrobeta', 'wakfu'):
            with self.subTest(version=version):
                self.assertEqual((None, 'version'), read_target(version, 'm1.1'))
                self.assertIsNone(monster_target(version, 1, 1))
                self.assertEqual([], search_monsters(version, 'a'))
