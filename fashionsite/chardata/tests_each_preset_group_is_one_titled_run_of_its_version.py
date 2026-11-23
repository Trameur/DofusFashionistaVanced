# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The preset chips of /setup/ come in four titled groups that are consecutive runs of the registry order, and the Atelier tile rules stay under html.fm-modern."""
import io
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.presets import RECIPE_GROUPS, RECIPES, setup_recipes
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
from chardata.tests_the_setup_stylesheet_support import STATIC, read_css, top_level_split

ATELIER = 'html.fm-modern .setup-atelier.setup-new'
TILES_MARK = '/* ---------- Tiles ---------- */'
PHONE_OR_TOUCH = '(max-width:767px), (pointer:coarse)'


def tiles_block():
    with io.open(os.path.join(STATIC, 'modern-setup.css'), encoding='utf-8') as handle:
        text = handle.read()
    return re.sub(r'/\*.*?\*/', '', text[text.index(TILES_MARK):], flags=re.S)


def blocks(source, prelude_of_parent=''):
    """(wrapping at-rule, selector list, declarations) of every rule of the source, at-rules unrolled."""
    found = []
    position = 0
    while True:
        opening = source.find('{', position)
        if opening == -1:
            return found
        prelude = ' '.join(source[position:opening].split())
        depth, index = 1, opening + 1
        while depth:
            depth += {'{': 1, '}': -1}.get(source[index], 0)
            index += 1
        body = source[opening + 1:index - 1]
        position = index
        if prelude.startswith('@'):
            found.extend(blocks(body, prelude))
        else:
            found.append((prelude_of_parent, [' '.join(piece.split()) for piece in top_level_split(prelude)], body))


class EveryRecipeBelongsToOneGroupTests(SimpleTestCase):

    def test_every_key_of_the_registry_has_a_group_and_no_key_has_two(self):
        keys = [key for _group, _title, group_keys in RECIPE_GROUPS for key in group_keys]
        self.assertEqual(sorted(keys), sorted(recipe.key for recipe in RECIPES))
        self.assertEqual(len(keys), len(set(keys)))

    def test_the_groups_of_each_version_are_consecutive_runs(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                seen = []
                for recipe in setup_recipes(version):
                    if not seen or seen[-1] != recipe.group:
                        seen.append(recipe.group)
                self.assertEqual(len(seen), len(set(seen)))

    def test_a_recipe_names_its_group_and_title(self):
        for group, title, keys in RECIPE_GROUPS:
            for recipe in RECIPES:
                if recipe.key in keys:
                    self.assertEqual((group, title), (recipe.group, recipe.group_title))


class EverySetupPageDrawsOneTitledGroupPerRunTests(TestCase):

    def test_the_page_of_each_version_draws_a_group_per_run_with_its_title_and_the_chips_in_registry_order(self):
        for version in VERSIONS:
            body, page = setup_page(self.client, version)
            with self.subTest(version=version):
                runs = []
                for recipe in setup_recipes(version):
                    if not runs or runs[-1][0] != recipe.group:
                        runs.append((recipe.group, []))
                    runs[-1][1].append(recipe.key)
                groups = [(attrs, ancestors) for attrs, ancestors in page.find('div', role='group')
                          if 'setup-chip-group' in attrs.get('class', '').split()]
                self.assertEqual([attrs['aria-labelledby'] for attrs, _ in groups],
                                 ['setup-chip-group-%s' % group for group, _keys in runs])
                with translation.override('en'):
                    titles = {group: str(title) for group, title, _keys in RECIPE_GROUPS}
                for group, _keys in runs:
                    title = re.search(r'<p [^>]*id="setup-chip-group-%s"[^>]*>([^<]*)</p>' % group, body)
                    self.assertIsNotNone(title, group)
                    self.assertEqual(titles[group], title.group(1))
                    self.assertEqual(['setup-chip-group-title', 'fm-x'],
                                     sorted(page.find('p', id='setup-chip-group-%s' % group)[0][0]['class'].split(),
                                            key=['setup-chip-group-title', 'fm-x'].index))
                chips = [attrs['data-recipe'] for attrs, _ in page.find('button', type='button')
                         if 'setup-chip' in attrs.get('class', '').split()]
                self.assertEqual(chips, [key for _group, keys in runs for key in keys])
                self.assertEqual(chips, [recipe.key for recipe in setup_recipes(version)])


class TheStylesheetsGroupTheChipsTests(SimpleTestCase):

    def test_classic_and_enhanced_flatten_the_groups_so_the_chips_stay_one_flex_row(self):
        rules = blocks(read_css('setup.css'))
        found = [body for _media, selectors, body in rules if selectors == ['.setup-chips > .setup-chip-group']]
        self.assertEqual(1, len(found))
        self.assertEqual('display:contents', ''.join(found[0].split()).rstrip(';'))

    def test_the_headings_are_hidden_outside_the_modern_design(self):
        self.assertIn('html:not(.fm-modern) .fm-x{ display:none !important; }', read_css('modern-setup.css'))


class TheAtelierTileRulesStayUnderTheModernDesignTests(SimpleTestCase):

    def test_every_selector_of_the_tile_rules_starts_with_the_atelier_scope(self):
        rules = blocks(tiles_block())
        self.assertGreater(len(rules), 60)
        for _media, selectors, _body in rules:
            for selector in selectors:
                with self.subTest(selector=selector):
                    self.assertTrue(selector.startswith(ATELIER), selector)

    def test_the_tile_height_is_44_pixels_on_a_phone_and_on_a_touch_screen(self):
        rules = blocks(tiles_block())
        phone = [body for media, selectors, body in rules
                 if media == '@media %s' % PHONE_OR_TOUCH and selectors == [ATELIER]]
        self.assertEqual(1, len(phone))
        self.assertIn('--fm-tile-h:44px', ''.join(phone[0].split()))
        base = [body for media, selectors, body in rules if not media and selectors == [ATELIER]]
        self.assertIn('--fm-tile-h:40px', ''.join(base[0].split()))

    def test_the_old_preset_layout_rules_the_grid_replaces_are_gone(self):
        text = read_css('modern-setup.css')
        for dead in ('grid-template-columns:auto auto minmax(0,1fr)', '.setup-recipes > .setup-share{ grid-row:4',
                     '.setup-saved[open]{ grid-row:6', 'scroll-snap-type:none'):
            self.assertNotIn(dead, text)


class TheSegmentFocusRingBeatsThePillRingTests(SimpleTestCase):

    def test_the_inset_ring_of_the_mode_segments_is_important_so_it_wins_over_the_pill_ring(self):
        rules = blocks(tiles_block())
        ringed = [(selectors, body) for _media, selectors, body in rules
                  if any('#fm-mode-general' in s and ':focus-visible' in s for s in selectors)]
        self.assertEqual(2, len(ringed))
        for selectors, body in ringed:
            with self.subTest(selectors=selectors):
                self.assertIn('inset 0 0 0 4px', body)
                self.assertTrue(''.join(body.split()).rstrip(';').endswith('!important'), body)

    def test_the_narrowest_preset_chips_keep_room_for_the_longest_german_word(self):
        rules = blocks(tiles_block())
        narrow = [body for media, selectors, body in rules
                  if media.startswith('@container (max-width:299px)') and selectors == [ATELIER + ' .setup-recipes > .setup-chips .setup-chip']]
        self.assertEqual(1, len(narrow))
        self.assertIn('padding-inline:3px', ''.join(narrow[0].split()))
        self.assertIn('font-size:12px', ''.join(narrow[0].split()))
