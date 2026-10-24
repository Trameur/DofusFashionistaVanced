# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu landing carries no Dofus class drawing, Dofus stats or Dofus keywords."""
import ast
import os

from django.core.cache import cache
from django.test import TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.wakfu_flag_for_tests import wakfu_flag

LANDINGS = ('/wakfu/', '/fr/wakfu/', '/es/wakfu/', '/pt/wakfu/', '/de/wakfu/')
TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates', 'chardata', 'wakfu')
INTRO = 'The Fashionista is coming to Wakfu: item encyclopedia first, then the build optimizer.'


class TheWakfuLandingDropsTheDofusChromeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_dofus_home_keeps_the_drawing_the_stats_and_the_keywords(self):
        with wakfu_flag(True):
            html = self.client.get('/').content.decode('utf-8')
        self.assertIn('class="char-overlay"', html)
        self.assertIn('sidebar-stats-row', html)
        self.assertIn('content="Dofus, sets', html)

    def test_no_wakfu_landing_draws_a_dofus_class_or_counts_dofus_versions(self):
        with wakfu_flag(True):
            for path in LANDINGS:
                html = self.client.get(path).content.decode('utf-8')
                self.assertNotIn('class="char-overlay"', html, path)
                self.assertNotIn('chardata/designs/', html, path)
                self.assertNotIn('sidebar-stats', html, path)

    def test_no_wakfu_landing_names_dofus_in_its_meta_keywords(self):
        with wakfu_flag(True):
            for path in LANDINGS:
                html = self.client.get(path).content.decode('utf-8')
                self.assertRegex(html, r'content="Wakfu,[^"]*" name="keywords"', path)
                self.assertNotIn('content="Dofus, sets', html, path)


class TheWakfuTemplatesStayReadableTests(TestCase):
    def test_no_wakfu_template_line_outside_a_trans_tag_passes_99_characters(self):
        for name in os.listdir(TEMPLATES):
            with open(os.path.join(TEMPLATES, name), encoding='utf-8') as source:
                for number, line in enumerate(source, 1):
                    if '{% trans' in line or '{% blocktrans' in line:
                        continue
                    self.assertLess(len(line.rstrip('\r\n')), 100, '%s:%d' % (name, number))


class TheGermanWakfuIntroSpellsEncyclopediaLikeTheRestOfTheSiteTests(TestCase):
    def test_the_intro_uses_the_one_word_compound_of_the_dofus_encyclopedia_entry(self):
        with translation.override('de'):
            intro = gettext(INTRO)
            dofus = gettext('Dofus Item Encyclopedia')
        self.assertIn('Gegenstandsenzyklop', dofus)
        self.assertIn('Gegenstandsenzyklop', intro)
        self.assertNotIn('Gegenstands-', intro)


class TheSitemapFunctionImportsTheVersionRegistryOnceTests(TestCase):
    def test_sitemap_pages_has_one_import_of_game_versions(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'fashionsite', 'urls.py')
        with open(path, encoding='utf-8') as source:
            tree = ast.parse(source.read())
        function = next(node for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef) and node.name == '_sitemap_pages')
        imports = [node for node in ast.walk(function) if isinstance(node, ast.ImportFrom)
                   and any(alias.name == 'GAME_VERSIONS' for alias in node.names)]
        self.assertEqual(1, len(imports))
