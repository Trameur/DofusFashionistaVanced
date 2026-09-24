# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Wakfu is experimental and never reader-facing (game_versions.py).

A pasted header ending in "- Wakfu" used to be read as a stated version,
which built a link to /wakfu/import/text/, a page that does not exist.
"""
from django.test import SimpleTestCase, TestCase

from chardata.text_build_import import _VERSION_PAR_LIBELLE, read_items


class TheVersionLabelTableNeverNamesAnExperimentalVersionTests(SimpleTestCase):

    def test_wakfu_is_not_a_recognised_header_label(self):
        self.assertNotIn('wakfu', _VERSION_PAR_LIBELLE)

    def test_the_reader_facing_versions_are_still_there(self):
        for cle in ('dofus3', 'beta', 'dofus2', 'retro', 'touch'):
            self.assertIn(cle, _VERSION_PAR_LIBELLE.values())


class APastedWakfuHeaderIsIgnoredTests(TestCase):

    def test_a_wakfu_header_states_no_version(self):
        lu = read_items('My Iop - Iop lvl 200 - Wakfu', 'dofus3', 'en')
        self.assertIsNone(lu['stated_version'])

    def test_the_import_page_never_links_to_wakfu(self):
        page = self.client.post('/import/text/', {
            'text': 'My Iop - Iop lvl 200 - Wakfu'})
        self.assertNotContains(page, '/wakfu/import/text/')
        self.assertNotContains(page, 'This build comes from')
        self.assertIsNone(page.context.get('other_version_url'))
