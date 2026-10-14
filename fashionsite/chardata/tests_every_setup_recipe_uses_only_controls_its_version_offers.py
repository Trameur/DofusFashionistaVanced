# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every preset recipe of every version fills only controls the /setup/ page of that version offers and that do something there, and never an element."""
import json
import re
from unittest import mock

from django.test import SimpleTestCase, TestCase

from chardata import presets
from chardata.presets import (DEFAULT_PRIORITY, ELEMENT_BOXES, FOCUS_COLUMNS, FOCUS_LIMIT,
                              GUARD_DEFAULT_PERCENT, GUARD_PERCENTS, NO_ELEMENT, PLAY_MODES,
                              VERSION_PRESETS, play_modes, setup_recipes)
from chardata.smart_build import inert_aspects
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
from fashionistapulp.structure import set_current_game_version

MULES = {'xp_mule', 'prospecting_mule', 'farm', 'pod_carrier'}


def page_controls(client, version):
    """The focus boxes, priorities, modes and guards the setup page of the version really offers, read from its own markup."""
    html, page = setup_page(client, version)
    layout = json.loads(re.search(r'var aspectLayout = (.*?)\.map', html, re.S).group(1))
    inert = json.loads(re.search(r'var inertAspects = (.*?);\s', html, re.S).group(1))
    modes = json.loads(re.search(r'var modeLayout = (.*?);\s', html, re.S).group(1))
    priorities = [attrs['value'] for attrs, _ in page.find('input', name='priority')]
    guards = [int(option['value']) for option, ancestors in page.find('option')
              if any(name == 'select' and a.get('id') == 'guard-percent' for name, a in ancestors)]
    focus = {aspect for column in layout[2:] for aspect in column if aspect != 'balanced'}
    return {'focus': focus - set(inert), 'inert': set(inert), 'priorities': priorities,
            'modes': {'general'} | {mode[0] for mode in modes}, 'guards': guards,
            'elements': set(layout[0])}


class EveryVersionHasItsOwnRecipeTableInTheRegistryTests(SimpleTestCase):

    def test_every_version_of_the_registry_has_a_recipes_table(self):
        for version, entry in VERSION_PRESETS.items():
            with self.subTest(version=version):
                self.assertIn('recipes', entry)
                self.assertGreater(len(entry['recipes']), 0)

    def test_the_accessor_returns_the_table_of_the_registry_in_display_order(self):
        for version, entry in VERSION_PRESETS.items():
            with self.subTest(version=version):
                self.assertEqual(list(entry['recipes']), setup_recipes(version))

    def test_a_version_entry_without_a_table_shows_no_recipe(self):
        bare = {'styles': ('solo_pvm',), 'option_boxes': ('duel',)}
        with mock.patch.dict(VERSION_PRESETS, {'touch': bare}):
            self.assertEqual([], setup_recipes('touch'))

    def test_recipe_keys_are_unique_inside_a_version(self):
        for version in VERSION_PRESETS:
            keys = [recipe.key for recipe in setup_recipes(version)]
            with self.subTest(version=version):
                self.assertEqual(len(keys), len(set(keys)))

    def test_no_second_table_of_recipes_lives_outside_the_registry(self):
        for version, entry in VERSION_PRESETS.items():
            for recipe in entry['recipes']:
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertIn(recipe, presets.RECIPES)


class EveryRecipeFillsOnlyWhatItsVersionOffersTests(TestCase):

    def test_the_focus_boxes_are_offered_and_not_inert_on_the_version(self):
        for version in VERSIONS:
            offered = page_controls(self.client, version)
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertLessEqual(set(recipe.focus), offered['focus'])
                    self.assertFalse(set(recipe.focus) & set(inert_aspects(version)))
                    self.assertFalse(set(recipe.focus) & offered['inert'])

    def test_the_priority_the_mode_and_the_safeguard_are_offered_on_the_version(self):
        for version in VERSIONS:
            offered = page_controls(self.client, version)
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertIn(recipe.priority, offered['priorities'])
                    self.assertIn(recipe.mode, offered['modes'])
                    self.assertIn(recipe.mode, [key for key, _label in play_modes(version)])
                    if recipe.guard_pct is not None:
                        self.assertIn(recipe.guard_pct, offered['guards'])
                        self.assertIn(recipe.guard_pct, GUARD_PERCENTS)

    def test_a_recipe_ticks_at_most_the_focus_limit_of_boxes(self):
        self.assertEqual(2, FOCUS_LIMIT)
        for version in VERSIONS:
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertLessEqual(len(recipe.focus), FOCUS_LIMIT)
                    self.assertEqual(len(recipe.focus), len(set(recipe.focus)))
                    self.assertFalse({'crit', 'noncrit'} <= set(recipe.focus))
                    self.assertNotIn('balanced', recipe.focus)

    def test_no_recipe_sets_an_element(self):
        elements = set(ELEMENT_BOXES) | {NO_ELEMENT}
        for version in VERSIONS:
            offered = page_controls(self.client, version)
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertFalse(set(recipe.focus) & elements)
                    self.assertFalse(set(recipe.focus) & offered['elements'])
                    self.assertEqual(['key', 'label', 'focus', 'priority', 'mode', 'guard_pct'],
                                     list(recipe._fields))

    def test_the_focus_columns_the_recipes_pick_from_hold_no_element(self):
        in_focus = {aspect for column in FOCUS_COLUMNS for aspect in column}
        self.assertFalse(in_focus & set(ELEMENT_BOXES))


class TheRecipesEachVersionKeepsAreTheOnesItsControlsAllowTests(SimpleTestCase):

    def keys(self, version):
        return [recipe.key for recipe in setup_recipes(version)]

    def test_a_recipe_for_an_inert_box_is_dropped_on_the_version_where_the_box_does_nothing(self):
        self.assertEqual(['trap'], list(inert_aspects('touch')))
        self.assertNotIn('trapper', self.keys('touch'))
        for version in ('dofus3', 'beta', 'dofus2', 'retro'):
            self.assertIn('trapper', self.keys(version))

    def test_retro_drops_the_recipes_of_the_boxes_it_ignores(self):
        for key in ('ap_removal', 'mp_removal', 'pusher'):
            self.assertNotIn(key, self.keys('retro'))
            self.assertIn(key, self.keys('dofus3'))

    def test_the_kolossium_modes_follow_the_modes_of_the_version(self):
        for version in VERSIONS:
            modes = {key for key, _label in play_modes(version)}
            kept = {recipe.mode for recipe in setup_recipes(version) if recipe.mode != 'general'}
            wanted = {mode.key for mode in PLAY_MODES if mode.boxes and mode.key in modes}
            with self.subTest(version=version):
                self.assertEqual(wanted, kept)
        self.assertEqual({'koli_1v1', 'koli_2v2', 'koli_3v3'},
                         {key for key in self.keys('dofus3') if key.startswith('koli')})
        self.assertEqual({'koli_1v1', 'koli_3v3'},
                         {key for key in self.keys('touch') if key.startswith('koli')})
        self.assertEqual({'aggression_1v1', 'group_pvp'},
                         set(self.keys('retro')) & {'aggression_1v1', 'group_pvp', 'koli_1v1'})
        self.assertFalse({key for key in self.keys('retro') if key.startswith('koli')})

    def test_the_mule_recipes_are_the_ones_that_only_tick_mule_boxes(self):
        for version in VERSIONS:
            found = {recipe.key for recipe in setup_recipes(version) if recipe.mule}
            with self.subTest(version=version):
                self.assertEqual(MULES, found)

    def test_every_version_keeps_the_universal_recipes(self):
        for version in VERSIONS:
            self.assertLessEqual({'balanced', 'damage', 'glass_cannon', 'tank', 'healer',
                                  'critical', 'fixed_damage', 'no_crit', 'summoner'},
                                 set(self.keys(version)), version)

    def test_no_recipe_asks_for_a_safeguard_stricter_than_the_default(self):
        for version in VERSIONS:
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    if recipe.guard_pct is not None:
                        self.assertGreaterEqual(recipe.guard_pct, GUARD_DEFAULT_PERCENT)

    def test_the_glass_cannon_ticks_its_own_box_and_leaves_the_priority_without_a_safeguard(self):
        for version in VERSIONS:
            recipe = {recipe.key: recipe for recipe in setup_recipes(version)}['glass_cannon']
            with self.subTest(version=version):
                self.assertEqual(('glasscannon',), recipe.focus)
                self.assertEqual(DEFAULT_PRIORITY, recipe.priority)
                self.assertIsNone(recipe.guard_pct)

    def test_the_labels_are_not_empty_in_the_source_language(self):
        for version in VERSIONS:
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertTrue(str(recipe.label).strip())

    def tearDown(self):
        set_current_game_version('dofus3')
