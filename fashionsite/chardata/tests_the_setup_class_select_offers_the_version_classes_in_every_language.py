# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ class select offers exactly the classes of the page's version, whatever the language."""

import re

from django.test import TestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import LANGUAGES, setup_page
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import set_current_game_version


def _select_options(html):
    block = re.search(r'<select[^>]*id="select-char-class".*?</select>', html, re.S).group(0)
    return [value for value in re.findall(r'<option value="([^"]*)"', block) if value]


class TheSetupClassSelectFollowsTheVersionTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_each_language_offers_the_classes_the_version_has(self):
        for version in VERSIONS:
            expected = set(filter_classes_for_version(CHARACTER_CLASSES, version))
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    html, _page = setup_page(self.client, version, language)
                    options = _select_options(html)
                    self.assertEqual(len(options), len(set(options)))
                    self.assertEqual(expected, set(options))
