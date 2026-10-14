# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A preset is only a way to fill the /setup/ form: the fields it posts store the build the same boxes ticked by hand store."""
import json

from django.test import TestCase

from chardata.models import Char
from chardata.presets import (GUARD_DEFAULT_PERCENT, GUARD_KIND, PLAY_MODE_BY_KEY, guard_plan,
                              setup_recipes, stored_choices, stored_guard)
from chardata.smart_build import get_char_aspects
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import (
    _DoorBuilds, classes_of, form_fields)
from chardata.weights_minimums import page_state
from fashionistapulp.structure import set_current_game_version

# recipe key: (focus boxes, priority, mode, option boxes the mode ticks, safeguard percent or None)
BY_HAND = {
    'balanced': ((), 'balanced', 'general', (), None),
    'damage': ((), 'damage', 'general', (), None),
    'glass_cannon': (('glasscannon',), 'balanced', 'general', (), None),
    'tank': ((), 'defense', 'general', (), None),
    'healer': ((), 'heals', 'general', (), None),
    'critical': (('crit',), 'damage', 'general', (), None),
    'fixed_damage': (('dam',), 'balanced', 'general', (), None),
    'no_crit': (('noncrit',), 'balanced', 'general', (), None),
    'ap_removal': (('aprape',), 'balanced', 'general', (), None),
    'mp_removal': (('mprape',), 'balanced', 'general', (), None),
    'pusher': (('pushback',), 'balanced', 'general', (), None),
    'summoner': (('summon',), 'balanced', 'general', (), None),
    'trapper': (('trap',), 'balanced', 'general', (), None),
    'koli_1v1': ((), 'balanced', 'koli_1v1', ('duel', 'pvp'), None),
    'koli_2v2': ((), 'balanced', 'koli_2v2', ('pvp',), None),
    'koli_3v3': ((), 'balanced', 'koli_3v3', ('pvp',), None),
    'aggression_1v1': ((), 'balanced', 'aggression_1v1', ('duel', 'pvp'), None),
    'group_pvp': ((), 'balanced', 'group_pvp', ('pvp',), None),
    'xp_mule': (('wis',), 'balanced', 'general', (), None),
    'prospecting_mule': (('pp',), 'balanced', 'general', (), None),
    'farm': (('wis', 'pp'), 'balanced', 'general', (), None),
    'pod_carrier': (('pods',), 'balanced', 'general', (), None),
}
MULES = ('xp_mule', 'prospecting_mule', 'farm', 'pod_carrier')


def hand_fields(key, char_class, level, element):
    """The form a player posts after ticking the boxes of the table by hand."""
    focus, priority, mode, options, guard = BY_HAND[key]
    fields = form_fields(char_class, level, set(element) | set(focus) | set(options),
                         priority=priority, play_mode=mode)
    return fields + [('guard_pct', str(GUARD_DEFAULT_PERCENT if guard is None else guard))]


def recipe_fields(recipe, char_class, level, element, mode_boxes):
    """The form the page posts once a chip has filled it: the recipe's boxes, the ones its mode ticks, its priority, mode and safeguard."""
    fields = form_fields(char_class, level, set(element) | set(recipe.focus) | set(mode_boxes),
                         priority=recipe.priority, play_mode=recipe.mode)
    guard = GUARD_DEFAULT_PERCENT if recipe.guard_pct is None else recipe.guard_pct
    return fields + [('guard_pct', str(guard))]


def stored(version, char):
    set_current_game_version(version)
    char = Char.objects.get(pk=char.pk)
    return json.loads(json.dumps({
        'state': page_state(char), 'aspects': sorted(get_char_aspects(char)),
        'choices': list(stored_choices(char)), 'guard': stored_guard(char),
        'plan': guard_plan(char)}, sort_keys=True))


class TheHandTableSaysWhatEveryRecipeFillsTests(TestCase):

    def test_the_table_has_one_row_per_recipe_of_every_version_and_no_other(self):
        offered = {recipe.key for version in VERSIONS for recipe in setup_recipes(version)}
        self.assertEqual(offered, set(BY_HAND))

    def test_the_boxes_priority_mode_and_safeguard_of_each_recipe_are_the_ones_ticked_by_hand(self):
        for version in VERSIONS:
            for recipe in setup_recipes(version):
                focus, priority, mode, _options, guard = BY_HAND[recipe.key]
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertEqual(set(focus), set(recipe.focus))
                    self.assertEqual(priority, recipe.priority)
                    self.assertEqual(mode, recipe.mode)
                    self.assertEqual(guard, recipe.guard_pct)


class ARecipePostsTheFieldsOfTheSameBoxesTickedByHandTests(TestCase):

    def test_every_recipe_of_every_version_posts_the_hand_fields(self):
        for version in VERSIONS:
            char_class = sorted(classes_of(version))[0]
            element = one_element_box(version)
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    options = PLAY_MODE_BY_KEY[recipe.mode].boxes
                    self.assertEqual(
                        sorted(hand_fields(recipe.key, char_class, 200, element)),
                        sorted(recipe_fields(recipe, char_class, 200, element, options)))
                    self.assertEqual(set(BY_HAND[recipe.key][3]), set(options))


class ARecipeStoresTheBuildOfTheSameBoxesTickedByHandTests(_DoorBuilds, TestCase):

    def build(self, version, fields):
        return stored(version, self.door_build(version, fields))

    def check_version(self, version, recipes=None, door=None, level=200, element=None):
        char_class = sorted(classes_of(version))[0]
        element = one_element_box(version) if element is None else element
        found = []
        for recipe in recipes or setup_recipes(version):
            options = PLAY_MODE_BY_KEY[recipe.mode].boxes
            from_recipe = recipe_fields(recipe, char_class, level, element, options)
            by_hand = hand_fields(recipe.key, char_class, level, element)
            if door is not None:
                from_recipe = [field for field in from_recipe if field[0] != 'wizard'] + [(door, door)]
                by_hand = [field for field in by_hand if field[0] != 'wizard'] + [(door, door)]
            first = self.build(version, from_recipe)
            second = self.build(version, by_hand)
            if first != second:
                found.append('%s %s' % (version, recipe.key))
            guard = BY_HAND[recipe.key][4]
            guard = GUARD_DEFAULT_PERCENT if guard is None else guard
            choices = [BY_HAND[recipe.key][1], BY_HAND[recipe.key][2]]
            if first['choices'] != choices or first['guard'] != guard:
                found.append('%s %s stored the wrong choices %s %s' % (
                    version, recipe.key, first['choices'], first['guard']))
            plan = None if choices[0] == 'balanced' else [GUARD_KIND[choices[0]], guard]
            if first['plan'] != plan:
                found.append('%s %s stored the safeguard plan %s' % (
                    version, recipe.key, first['plan']))
            if not set(element) | set(recipe.focus) | set(options) <= set(first['aspects']):
                found.append('%s %s lost a ticked box' % (version, recipe.key))
        self.assertEqual([], found)

    def test_dofus3(self):
        self.check_version('dofus3')

    def test_beta(self):
        self.check_version('beta')

    def test_dofus2(self):
        self.check_version('dofus2')

    def test_touch(self):
        self.check_version('touch')

    def test_retro(self):
        self.check_version('retro')

    def test_a_mule_recipe_without_any_element_stores_the_build_of_the_hand_boxes_without_one(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                recipes = [recipe for recipe in setup_recipes(version) if recipe.key in MULES]
                self.assertEqual(sorted(MULES), sorted(recipe.key for recipe in recipes))
                self.check_version(version, recipes, element=frozenset())

    def test_the_other_two_doors_store_the_same_build_for_a_recipe_as_for_the_hand_boxes(self):
        wanted = {'glass_cannon', 'critical', 'koli_1v1', 'farm', 'tank'}
        for door in ('optimize', 'byhand'):
            for version in ('dofus3', 'retro'):
                with self.subTest(door=door, version=version):
                    recipes = [recipe for recipe in setup_recipes(version) if recipe.key in wanted]
                    self.check_version(version, recipes, door=door)

    def test_a_recipe_posted_at_a_low_level_stores_the_hand_build_too(self):
        wanted = {'glass_cannon', 'koli_3v3', 'healer'}
        recipes = [recipe for recipe in setup_recipes('dofus3') if recipe.key in wanted]
        self.check_version('dofus3', recipes, level=50)
