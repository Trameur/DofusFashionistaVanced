# -*- coding: utf-8 -*-
"""One list of game versions, not three that must be remembered together.

`GameVersion.experimental` is documented as "invisible everywhere a reader
could reach it". Wakfu is the first version to use it: 20 commits of data
pipeline, no page, nothing linking to it. That rule was held by three lists
written out by hand -- the reader-facing versions in context_processors, the
prefixed hubs in the sitemap, and the prefixes the guide bodies rewrite with --
and nothing compared any of them with the registry. All three are derived now,
and this is what keeps them derived.

The last test is the one with teeth: every assertion above passes trivially if
no experimental version exists at all. It demands that one does, and that it is
missing from every reader-facing list.
"""
from django.test import SimpleTestCase

from fashionistapulp.game_versions import (DEFAULT_VERSION, GAME_VERSIONS,
                                           prefixed_reader_versions,
                                           version_keys)

from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.guides_view import VERSION_PREFIXES


class OneListOfVersions(SimpleTestCase):

    def test_the_reader_list_is_the_registry_without_the_experimental_ones(self):
        self.assertEqual([key for key, _label in ACTIVE_GAME_VERSIONS],
                         version_keys())

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
