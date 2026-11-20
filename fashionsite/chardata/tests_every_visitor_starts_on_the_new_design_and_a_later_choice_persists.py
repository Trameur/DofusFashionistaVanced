# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every visitor starts on the new design whatever production stored, and a choice stored under fm_design_v2 picks the design of every later page."""
import io
import os
import re
import unittest

from django.test import SimpleTestCase, TestCase

from chardata.tests_the_default_theme_is_automatic_and_a_stored_choice_wins import NODE, run_head

CHARDATA = os.path.dirname(os.path.abspath(__file__))
DESIGN_CLASSES = ('fm-modern', 'fm-enhanced')
THEME_CLASSES = ('fm-light', 'fm-dark')


def design_classes(result):
    return sorted(name for name in result['classes'] if name in DESIGN_CLASSES)


@unittest.skipUnless(NODE, 'node is not installed')
class TheHeadScriptPicksTheStoredDesignTests(SimpleTestCase):

    def head(self, **options):
        return run_head(cookie='theme=auto', **options)

    def test_a_visitor_with_nothing_stored_gets_the_new_design_only(self):
        self.assertEqual(['fm-modern'], design_classes(self.head()))

    def test_the_production_classic_choice_is_ignored(self):
        self.assertEqual(['fm-modern'], design_classes(self.head(storage={'fm_design': 'classic'})))

    def test_a_stored_classic_choice_gets_no_design_class(self):
        self.assertEqual([], design_classes(self.head(storage={'fm_design_v2': 'classic'})))

    def test_a_stored_enhanced_choice_gets_the_enhanced_class_only(self):
        self.assertEqual(['fm-enhanced'], design_classes(self.head(storage={'fm_design_v2': 'enhanced'})))

    def test_a_stored_new_choice_gets_the_new_design(self):
        self.assertEqual(['fm-modern'], design_classes(self.head(storage={'fm_design_v2': 'atelier'})))

    def test_a_value_that_is_not_a_design_gets_the_new_design(self):
        self.assertEqual(['fm-modern'], design_classes(self.head(storage={'fm_design_v2': 'bogus'})))

    def test_a_storage_that_throws_gets_the_new_design_and_the_no_storage_class(self):
        result = self.head(storageThrows=True)
        self.assertEqual(['fm-modern'], design_classes(result))
        self.assertIn('fm-nostore', result['classes'])

    def test_a_working_storage_never_gets_the_no_storage_class(self):
        for value in (None, 'classic', 'enhanced', 'atelier'):
            storage = {} if value is None else {'fm_design_v2': value}
            self.assertNotIn('fm-nostore', self.head(storage=storage)['classes'], value)

    def test_the_theme_class_is_set_whatever_the_design(self):
        cases = ({}, {'storage': {'fm_design': 'classic'}}, {'storageThrows': True}) + tuple(
            {'storage': {'fm_design_v2': value}} for value in ('classic', 'enhanced', 'atelier', 'bogus'))
        for options in cases:
            classes = self.head(**options)['classes']
            self.assertEqual(1, len([name for name in classes if name in THEME_CLASSES]), options)

    def test_only_the_enhanced_choice_starts_fetching_its_sheet_early(self):
        preloads = self.head(storage={'fm_design_v2': 'enhanced'})['preloads']
        self.assertEqual(1, len(preloads))
        self.assertEqual(('link', 'preload', 'style'), (preloads[0]['tag'], preloads[0]['rel'], preloads[0]['as']))
        self.assertIn('chardata/enhanced.css', preloads[0]['href'])
        for options in ({}, {'storageThrows': True}, {'storage': {'fm_design_v2': 'classic'}}, {'storage': {'fm_design_v2': 'atelier'}}):
            self.assertEqual([], self.head(**options)['preloads'], options)


class NothingReadsTheProductionDesignKeyTests(SimpleTestCase):

    def test_no_template_or_script_names_the_production_design_key(self):
        roots = (os.path.join(CHARDATA, 'templates'), os.path.join(CHARDATA, 'static', 'chardata'))
        found = []
        for root in roots:
            for folder, _, names in os.walk(root):
                for name in names:
                    if name.endswith(('.html', '.js')):
                        path = os.path.join(folder, name)
                        with io.open(path, encoding='utf-8', errors='replace') as handle:
                            text = handle.read()
                        if "'fm_design'" in text or '"fm_design"' in text:
                            found.append(os.path.relpath(path, CHARDATA))
        self.assertEqual([], found)


class TheRenderedHeadPreloadsTheSheetTheLoaderWritesTests(TestCase):

    def test_the_preload_and_the_loader_name_the_same_sheet_address(self):
        html = self.client.get('/').content.decode('utf-8')
        preload = re.search(r"r\.href='([^']+)'", html).group(1)
        loader = re.search(r"document\.write\('<link rel=\"stylesheet\" type=\"text/css\" href=\"([^\"]+)\">'\)", html).group(1)
        self.assertEqual(preload, loader)
        self.assertTrue(preload.endswith('.css') and 'enhanced' in preload, preload)
