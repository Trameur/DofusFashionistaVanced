# -*- coding: utf-8 -*-
"""Every reader-facing version list (routes, middleware, SEO words, sitemap hubs, guide prefixes) derives from one registry."""
from django.test import RequestFactory, SimpleTestCase
from django.urls import get_resolver, reverse

from fashionistapulp.game_versions import (DEFAULT_VERSION, GAME_VERSIONS,
                                           prefixed_reader_versions,
                                           reader_dofus_versions,
                                           switcher_games, switcher_order,
                                           version_keys)

from chardata.context_processors import ACTIVE_GAME_VERSIONS, game_version
from chardata.guides_view import VERSION_PREFIXES
from chardata.middleware import GameVersionMiddleware


class OneListOfVersions(SimpleTestCase):

    def test_the_reader_list_follows_the_switcher_order(self):
        self.assertEqual([key for key, _label in ACTIVE_GAME_VERSIONS], switcher_order())
        self.assertEqual(sorted(switcher_order()), sorted(version_keys()))

    def test_the_reader_list_carries_the_registry_labels(self):
        self.assertEqual(dict(ACTIVE_GAME_VERSIONS),
                         {key: GAME_VERSIONS[key].label
                          for key in version_keys()})

    def test_the_sitemap_hubs_are_the_reader_versions_under_a_prefix(self):
        self.assertEqual(sorted(prefixed_reader_versions()),
                         sorted(key for key, _label in ACTIVE_GAME_VERSIONS
                                if key != DEFAULT_VERSION))

    def test_the_guide_bodies_rewrite_with_the_same_prefixes(self):
        self.assertEqual(sorted(VERSION_PREFIXES),
                         sorted(prefixed_reader_versions()))

    def test_the_default_version_has_no_prefixed_hub(self):
        self.assertNotIn(DEFAULT_VERSION, prefixed_reader_versions())

    def test_an_experimental_version_exists_and_reaches_no_reader(self):
        experimental = sorted(key for key, version in GAME_VERSIONS.items()
                              if version.experimental)
        self.assertTrue(experimental,
                        'no experimental version: every test above is vacuous')
        for key in experimental:
            self.assertNotIn(key, [k for k, _label in ACTIVE_GAME_VERSIONS])
            self.assertNotIn(key, prefixed_reader_versions())
            self.assertNotIn(key, VERSION_PREFIXES)
            self.assertNotIn(key, version_keys())

    def test_the_switcher_games_cover_exactly_the_reader_versions(self):
        self.assertEqual(sorted(key for _main, members in switcher_games()
                                for key in members),
                         sorted(version_keys()))

    def test_no_experimental_version_is_a_reader_dofus_version(self):
        for key in reader_dofus_versions():
            self.assertFalse(GAME_VERSIONS[key].experimental)

    def test_the_url_namespaces_are_the_prefixed_reader_versions(self):
        namespaces = set(get_resolver().namespace_dict) & set(GAME_VERSIONS)
        self.assertEqual(namespaces, set(prefixed_reader_versions()))
        for key in prefixed_reader_versions():
            with self.subTest(key=key):
                self.assertEqual(reverse('%s:home' % key),
                                 '/%s/' % GAME_VERSIONS[key].prefix)

    def test_each_version_path_sets_its_version_seo_word_and_switch_base(self):
        factory = RequestFactory()
        middleware = GameVersionMiddleware(lambda request: None)
        for key in version_keys():
            prefix = GAME_VERSIONS[key].prefix
            for path, base in (('/%s/setup/' % prefix, '/setup/'),
                               ('/es/%s/encyclopedia/' % prefix, '/encyclopedia/')):
                path = path.replace('//', '/')
                with self.subTest(path=path):
                    request = factory.get(path)
                    middleware(request)
                    self.assertEqual(request.game_version, key)
                    context = game_version(request)
                    self.assertEqual(context['current_game_version_seo'],
                                     GAME_VERSIONS[key].seo_word)
                    self.assertEqual(context['version_switch_base_path'], base)

    def test_an_experimental_prefix_falls_back_to_the_default_version(self):
        factory = RequestFactory()
        middleware = GameVersionMiddleware(lambda request: None)
        for key, version in GAME_VERSIONS.items():
            if not version.experimental:
                continue
            with self.subTest(key=key):
                request = factory.get('/%s/setup/' % version.prefix)
                middleware(request)
                self.assertEqual(request.game_version, DEFAULT_VERSION)
