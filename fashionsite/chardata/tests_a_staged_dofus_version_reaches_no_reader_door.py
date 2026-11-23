# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Dofus version marked experimental is listed for the data tools and absent from every reader door."""
import importlib
import io
import os
import sys
from contextlib import redirect_stdout
from unittest import mock

from django.test import RequestFactory, TestCase

from fashionistapulp import fashionista_config, game_versions
from fashionistapulp.game_versions import GameVersion

from chardata import encyclopedia_view
from fashionsite import urls

STAGED = 'stagedbeta'
SITEMAP_SECTIONS = ('pages', 'items', 'sets', 'resources', 'monsters')


def _staged_version():
    return GameVersion(STAGED, 'Staged', 'items.db', 'item_db_dumped.dump',
                       seo_word='3 Staged', experimental=True,
                       family='dofus3', channel='beta')


def _stage_a_version():
    return (mock.patch.dict(game_versions.GAME_VERSIONS,
                            {STAGED: _staged_version()}),
            mock.patch.object(game_versions, 'VERSION_ORDER',
                              game_versions.VERSION_ORDER + (STAGED,)))


class StagedDofusVersionReachesNoReaderDoor(TestCase):

    def setUp(self):
        self.patchers = _stage_a_version()
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_data_lists_still_name_the_staged_version(self):
        self.assertIn(STAGED, game_versions.dofus_versions())
        self.assertIn(STAGED, game_versions.version_keys(include_experimental=True))

    def test_every_reader_list_drops_it(self):
        self.assertNotIn(STAGED, game_versions.version_keys())
        self.assertNotIn(STAGED, game_versions.reader_dofus_versions())
        self.assertNotIn(STAGED, game_versions.prefixed_reader_versions())
        self.assertNotIn(STAGED, game_versions.sibling_versions('dofus3'))
        self.assertNotIn(STAGED, game_versions.family_members('dofus3'))
        for _main, members in game_versions.switcher_games():
            self.assertNotIn(STAGED, members)

    def test_it_has_no_url_route_or_namespace(self):
        for pattern in urls._prefixed_version_routes():
            self.assertNotEqual(STAGED + '/', str(pattern.pattern))
            self.assertNotEqual(STAGED, pattern.namespace)

    def test_the_two_check_commands_do_not_walk_it(self):
        for name in ('check_pages', 'check_actions'):
            module = importlib.import_module(
                'chardata.management.commands.%s' % name)
            module = importlib.reload(module)
            try:
                self.assertNotIn(STAGED, module.VERSIONS)
                self.assertEqual(tuple(game_versions.reader_dofus_versions()),
                                 module.VERSIONS)
            finally:
                for patcher in self.patchers:
                    patcher.stop()
                importlib.reload(module)
                for patcher in self.patchers:
                    patcher.start()

    def test_the_switcher_and_prefix_tables_built_at_import_drop_it(self):
        from chardata import context_processors, middleware
        try:
            importlib.reload(context_processors)
            importlib.reload(middleware)
            self.assertNotIn(STAGED, [key for key, _label in context_processors.ACTIVE_GAME_VERSIONS])
            self.assertNotIn(STAGED + '/', context_processors._VERSION_PREFIXES)
            self.assertNotIn(STAGED, middleware.GAME_VERSION_PREFIXES)
            self.assertNotIn(STAGED, context_processors._GAME_VERSION_LABELS)
            request = RequestFactory().get('/')
            shown = context_processors.game_version(request)
            self.assertNotIn(STAGED, [key for key, _label in shown['active_game_versions']])
        finally:
            for patcher in self.patchers:
                patcher.stop()
            importlib.reload(context_processors)
            importlib.reload(middleware)
            for patcher in self.patchers:
                patcher.start()

    def test_a_rendered_page_shows_it_in_no_switcher_entry_or_alternate_link(self):
        from chardata import context_processors, middleware
        try:
            importlib.reload(context_processors)
            importlib.reload(middleware)
            response = self.client.get('/')
            self.assertEqual(200, response.status_code)
            page = response.content.decode('utf-8')
            self.assertTrue(page)
            self.assertIn('rel="alternate"', page)
            self.assertNotIn(STAGED, page)
        finally:
            for patcher in self.patchers:
                patcher.stop()
            importlib.reload(context_processors)
            importlib.reload(middleware)
            for patcher in self.patchers:
                patcher.start()

    def test_the_db_scripts_still_offer_it_as_a_choice(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(game_versions.__file__))))
        sys.path.insert(0, root)
        try:
            for name in ('dump_item_db', 'load_item_db'):
                with self.subTest(script=name):
                    module = importlib.import_module(name)
                    shown = io.StringIO()
                    with mock.patch.object(sys, 'argv', [name, '-h']), \
                            redirect_stdout(shown), \
                            self.assertRaises(SystemExit):
                        module.main()
                    self.assertIn(STAGED, shown.getvalue())
        finally:
            sys.path.remove(root)

    def test_the_sitemap_reads_neither_its_database_nor_its_pages(self):
        asked = []
        real_db_path = fashionista_config.get_items_db_path
        real_structure = encyclopedia_view.get_structure

        def db_path(version, *args, **kwargs):
            asked.append(version)
            return real_db_path(version, *args, **kwargs)

        def structure(version, *args, **kwargs):
            asked.append(version)
            return real_structure(version, *args, **kwargs)

        saved = dict(urls._SITEMAP_CACHES)
        saved_items = dict(urls._SITEMAP_ITEM_CACHE)
        urls._SITEMAP_CACHES.clear()
        self.addCleanup(urls._SITEMAP_CACHES.update, saved)
        self.addCleanup(urls._SITEMAP_CACHES.clear)
        self.addCleanup(urls._SITEMAP_ITEM_CACHE.update, saved_items)
        with mock.patch.object(fashionista_config, 'get_items_db_path', db_path), \
                mock.patch.object(encyclopedia_view, 'get_structure', structure):
            built = {name: dict(urls.SITEMAP_SECTIONS)[name](urls.SITEMAP_BASE)
                     for name in SITEMAP_SECTIONS}
        self.assertTrue(asked, 'the sitemap read no version: the spy is blind')
        self.assertNotIn(STAGED, asked)
        for name, body in built.items():
            with self.subTest(section=name):
                self.assertTrue(body)
                self.assertNotIn('/%s/' % STAGED, body)
                self.assertNotIn(STAGED, body)


class TheSitemapIsTheSameWithAndWithoutAStagedVersion(TestCase):

    def _build(self, staged):
        saved = dict(urls._SITEMAP_CACHES)
        saved_items = dict(urls._SITEMAP_ITEM_CACHE)
        urls._SITEMAP_CACHES.clear()
        urls._SITEMAP_ITEM_CACHE.update({'ts': 0.0, 'xml': ''})
        patchers = list(_stage_a_version()) if staged else []
        for patcher in patchers:
            patcher.start()
        try:
            return {name: dict(urls.SITEMAP_SECTIONS)[name](urls.SITEMAP_BASE)
                    for name in SITEMAP_SECTIONS}
        finally:
            for patcher in patchers:
                patcher.stop()
            urls._SITEMAP_CACHES.clear()
            urls._SITEMAP_CACHES.update(saved)
            urls._SITEMAP_ITEM_CACHE.update(saved_items)

    def test_staging_a_version_changes_no_sitemap_byte(self):
        without = self._build(staged=False)
        with_staged = self._build(staged=True)
        for name in SITEMAP_SECTIONS:
            with self.subTest(section=name):
                self.assertEqual(without[name], with_staged[name])
