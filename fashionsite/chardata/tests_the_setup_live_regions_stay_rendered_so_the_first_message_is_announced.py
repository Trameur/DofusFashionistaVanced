# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ panel keeps the live regions of the edit count and the safeguard rendered, so a screen reader announces the first message written in them."""
import io
import re

from django.test import SimpleTestCase, TestCase

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT, _Versioned, setup_page
from chardata.tests_the_setup_stylesheet_support import declared, matching, stylesheet

REGIONS = ('setup-preview-edited', 'setup-preview-guard')


def hidden_between(ancestors, panel_id):
    names = [attrs.get('id') for _tag, attrs in ancestors]
    inner = ancestors[names.index(panel_id) + 1:]
    return [(tag, attrs.get('id')) for tag, attrs in inner if 'hidden' in attrs]


class TheRegionsArePaintedFromTheStartTests(_Versioned, TestCase):

    def test_no_ancestor_below_the_panel_and_no_attribute_of_its_own_hides_a_region(self):
        for version in VERSIONS:
            for region in REGIONS:
                with self.subTest(version=version, region=region):
                    _html, page = setup_page(self.client, version)
                    found = page.find('p', id=region)
                    self.assertEqual(1, len(found))
                    attrs, ancestors = found[0]
                    self.assertNotIn('hidden', attrs)
                    self.assertEqual('polite', attrs['aria-live'])
                    self.assertEqual([], hidden_between(ancestors, 'setup-preview'))

    def test_the_regions_start_empty(self):
        for version in VERSIONS:
            html, _page = setup_page(self.client, version)
            for region in REGIONS:
                with self.subTest(version=version, region=region):
                    self.assertIsNotNone(re.search(r'<p\b[^>]*\bid="%s"[^>]*></p>' % region, html))

    def test_only_the_way_back_button_waits_hidden_beside_the_edit_count(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                bar = page.find('div', id='setup-preview-edits')
                self.assertEqual(1, len(bar))
                self.assertNotIn('hidden', bar[0][0])
                reset = page.find('button', id='setup-preview-reset')
                self.assertEqual(1, len(reset))
                self.assertIn('hidden', reset[0][0])
                self.assertTrue(page.inside(reset[0][1], 'div', 'setup-preview-edits'))
                count = page.find('p', id='setup-preview-edited')
                self.assertTrue(page.inside(count[0][1], 'div', 'setup-preview-edits'))


class TheScriptWritesTheTextAndLeavesTheRegionRenderedTests(SimpleTestCase):

    def setUp(self):
        self.source = io.open(SCRIPT, encoding='utf-8').read()

    def test_the_edit_count_is_written_and_only_the_button_is_shown_or_hidden(self):
        self.assertIn("setupWriteLive($edited, count ? setupPreviewEdits(count) : '');", self.source)
        self.assertIn("$reset.prop('hidden', !count);", self.source)
        self.assertNotIn('$edits', self.source)
        self.assertNotIn('$edited.prop(', self.source)

    def test_the_safeguard_text_is_written_and_the_line_is_never_hidden(self):
        self.assertIn("setupWriteLive($guard, text || '');", self.source)
        self.assertNotIn('$guard.prop(', self.source)


class NoRuleHidesAnEmptyRegionTests(SimpleTestCase):

    def setUp(self):
        self.rules = stylesheet('setup.css')

    def test_the_bar_is_laid_out_without_a_margin_of_its_own_so_an_idle_bar_takes_no_room(self):
        self.assertEqual(('flex', False), declared(self.rules, '.setup-preview-edits', 'display'))
        self.assertEqual(('0', False), declared(self.rules, '.setup-preview-edits', 'margin'))
        self.assertEqual(('6px 0', False),
                         declared(self.rules, '.setup-preview-edits .setup-preview-reset', 'margin'))

    def test_no_empty_pseudo_class_rule_takes_the_count_or_the_safeguard_line_out_of_the_page(self):
        for selector in ('.setup-preview-edits:empty', '.setup-preview-edited:empty',
                         '.setup-preview-guard:empty'):
            with self.subTest(selector=selector):
                self.assertEqual([], matching(self.rules, selector))
