# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The data version of Wakfu is read from its database, never typed."""
import os
import sqlite3
import tempfile
from contextlib import closing
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.data_versions import read_data_version, stored_data_version
from chardata.wakfu_flag_for_tests import wakfu_flag
from fashionistapulp.game_versions import GAME_VERSIONS
from fashionsite.context_processors import site_version


def _database(directory, rows):
    path = os.path.join(directory, 'items.db')
    with closing(sqlite3.connect(path)) as db:
        if rows is not None:
            db.execute('CREATE TABLE data_version (version TEXT NOT NULL)')
            db.executemany('INSERT INTO data_version VALUES (?)', [(row,) for row in rows])
        else:
            db.execute('CREATE TABLE other (x TEXT)')
        db.commit()
    return path


class TheWakfuFooterShowsTheVersionItsDatabaseStatesTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def test_a_table_with_one_row_gives_that_row(self):
        self.assertEqual('9.9.9.9', read_data_version(_database(self.folder, ['9.9.9.9'])))

    def test_a_database_without_the_table_gives_nothing(self):
        self.assertEqual('', read_data_version(_database(self.folder, None)))

    def test_a_table_without_a_row_gives_nothing(self):
        self.assertEqual('', read_data_version(_database(self.folder, [])))

    def test_a_missing_file_gives_nothing(self):
        self.assertEqual('', read_data_version(os.path.join(self.folder, 'absent.db')))

    def test_a_rewritten_file_is_read_again(self):
        path = _database(self.folder, ['1.0.0.0'])
        self.assertEqual('1.0.0.0', read_data_version(path))
        with closing(sqlite3.connect(path)) as db:
            db.execute('UPDATE data_version SET version = ?', ('2.0.0.0',))
            db.commit()
        os.utime(path, ns=(1, 1))
        self.assertEqual('2.0.0.0', read_data_version(path))

    def test_the_wakfu_site_version_is_the_one_the_database_states(self):
        path = _database(self.folder, ['9.9.9.9'])
        request = RequestFactory().get('/wakfu/')
        request.game_version = 'wakfu'
        with mock.patch('chardata.data_versions.get_items_db_path', return_value=path):
            self.assertEqual({'SITE_VERSION': '9.9.9.9'}, site_version(request))
            self.assertEqual('9.9.9.9', stored_data_version('wakfu'))

    def test_a_wakfu_page_does_not_fall_back_to_a_dofus_version(self):
        path = _database(self.folder, None)
        request = RequestFactory().get('/wakfu/')
        request.game_version = 'wakfu'
        with mock.patch('chardata.data_versions.get_items_db_path', return_value=path):
            self.assertEqual({'SITE_VERSION': ''}, site_version(request))

    def test_dofus3_keeps_its_configured_version(self):
        request = RequestFactory().get('/')
        request.game_version = 'dofus3'
        self.assertEqual({'SITE_VERSION': settings.SITE_VERSIONS['dofus3']},
                         site_version(request))

    def test_no_version_outside_dofus_has_a_typed_version_in_settings(self):
        typed = [key for key, known in GAME_VERSIONS.items()
                 if not known.dofus and key in settings.SITE_VERSIONS]
        self.assertEqual([], typed)


def _footer(html):
    return ' '.join(html[html.index('class="footer"'):].split())


class TheWakfuPageFooterShowsTheVersionItsDatabaseStatesTests(TestCase):
    def setUp(self):
        cache.clear()

    def _footer_of(self, path='/wakfu/'):
        with wakfu_flag(True):
            return _footer(self.client.get(path).content.decode('utf-8'))

    def test_the_footer_reads_the_version_the_database_states(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = _database(folder.name, ['9.9.9.9'])
        with mock.patch('chardata.data_versions.get_items_db_path', return_value=path):
            self.assertIn('Items up to Wakfu update 9.9.9.9', self._footer_of())

    def test_the_footer_names_no_dofus_version_when_the_database_states_none(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = _database(folder.name, None)
        with mock.patch('chardata.data_versions.get_items_db_path', return_value=path):
            footer = self._footer_of()
        self.assertNotIn('Items up to', footer)
        self.assertNotIn(settings.SITE_VERSIONS['dofus3'], footer)

    def test_the_footer_follows_the_shipped_database(self):
        stated = stored_data_version('wakfu')
        footer = self._footer_of()
        if stated:
            self.assertIn('Items up to Wakfu update %s' % stated, footer)
        else:
            print('the Wakfu database states no version')
            self.assertNotIn('Items up to', footer)
