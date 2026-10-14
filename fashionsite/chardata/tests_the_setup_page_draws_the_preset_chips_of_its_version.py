# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ page of each version draws one chip per recipe of that version, outside the form, with the controls the chip fills in its data attributes."""
from django.test import TestCase
from django.utils import translation

from chardata.presets import setup_recipes
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import LANGUAGES, setup_page
from fashionistapulp.structure import set_current_game_version

MULES = ('xp_mule', 'prospecting_mule', 'farm', 'pod_carrier')


def chips_of(page):
    return [(attrs, ancestors) for attrs, ancestors in page.find('button')
            if 'setup-chip' in attrs.get('class', '').split()]


class TheChipsMatchTheRecipesOfTheVersionTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_each_version_draws_one_chip_per_recipe_in_the_order_of_the_registry(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                drawn = [attrs['data-recipe'] for attrs, _ in chips_of(page)]
                self.assertEqual([recipe.key for recipe in setup_recipes(version)], drawn)

    def test_a_chip_carries_exactly_the_controls_of_its_recipe(self):
        for version in VERSIONS:
            _html, page = setup_page(self.client, version)
            recipes = {recipe.key: recipe for recipe in setup_recipes(version)}
            for attrs, _ancestors in chips_of(page):
                recipe = recipes[attrs['data-recipe']]
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertEqual(' '.join(recipe.focus), attrs['data-focus'])
                    self.assertEqual(recipe.priority, attrs['data-priority'])
                    self.assertEqual(recipe.mode, attrs['data-mode'])
                    if recipe.guard_pct is None:
                        self.assertNotIn('data-guard', attrs)
                    else:
                        self.assertEqual(str(recipe.guard_pct), attrs['data-guard'])
                    self.assertEqual('button', attrs['type'])
                    self.assertEqual('false', attrs['aria-pressed'])

    def test_a_chip_never_names_an_element(self):
        for version in VERSIONS:
            _html, page = setup_page(self.client, version)
            for attrs, _ancestors in chips_of(page):
                with self.subTest(version=version, recipe=attrs['data-recipe']):
                    self.assertFalse({'str', 'int', 'cha', 'agi', 'omni', 'none'}
                                     & set(attrs['data-focus'].split()))

    def test_only_the_four_mule_chips_carry_the_mule_flag(self):
        for version in VERSIONS:
            _html, page = setup_page(self.client, version)
            flagged = [attrs['data-recipe'] for attrs, _ in chips_of(page) if 'data-mule' in attrs]
            with self.subTest(version=version):
                self.assertEqual(sorted(MULES), sorted(flagged))
                for attrs, _ in chips_of(page):
                    if 'data-mule' in attrs:
                        self.assertEqual('true', attrs['data-mule'])

    def test_every_chip_shows_the_label_of_its_recipe(self):
        for version in VERSIONS:
            html, page = setup_page(self.client, version)
            for recipe in setup_recipes(version):
                with self.subTest(version=version, recipe=recipe.key):
                    self.assertIn('>%s</button>' % recipe.label, html)


class TheKolossiumAndAggressionChipsFollowTheVersionTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def modes(self, version):
        _html, page = setup_page(self.client, version)
        return {attrs['data-recipe']: attrs['data-mode'] for attrs, _ in chips_of(page)
                if attrs['data-mode'] != 'general'}

    def test_dofus_3_draws_the_three_kolossium_chips(self):
        self.assertEqual({'koli_1v1': 'koli_1v1', 'koli_2v2': 'koli_2v2', 'koli_3v3': 'koli_3v3'},
                         self.modes('dofus3'))

    def test_touch_has_no_2v2_chip(self):
        self.assertEqual({'koli_1v1': 'koli_1v1', 'koli_3v3': 'koli_3v3'}, self.modes('touch'))

    def test_retro_draws_aggression_and_group_pvp_and_no_kolossium_chip(self):
        self.assertEqual({'aggression_1v1': 'aggression_1v1', 'group_pvp': 'group_pvp'},
                         self.modes('retro'))

    def test_touch_draws_no_trapper_chip_and_retro_no_removal_or_pusher_chip(self):
        _html, touch = setup_page(self.client, 'touch')
        _html, retro = setup_page(self.client, 'retro')
        touch_keys = [attrs['data-recipe'] for attrs, _ in chips_of(touch)]
        retro_keys = [attrs['data-recipe'] for attrs, _ in chips_of(retro)]
        self.assertNotIn('trapper', touch_keys)
        self.assertFalse({'ap_removal', 'mp_removal', 'pusher'} & set(retro_keys))


class TheChipsSendNothingWithTheFormTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_whole_section_is_outside_the_form_and_hidden_until_the_script_runs(self):
        for version in VERSIONS:
            _html, page = setup_page(self.client, version)
            with self.subTest(version=version):
                section = page.find('section', id='setup-recipes')
                self.assertEqual(1, len(section))
                self.assertIn('hidden', section[0][0])
                self.assertEqual(version, section[0][0]['data-version'])
                self.assertFalse(page.inside(section[0][1], 'form', 'main_form'))

    def test_no_control_of_the_section_is_named_so_nothing_of_it_is_posted(self):
        for version in VERSIONS:
            _html, page = setup_page(self.client, version)
            for tag in ('input', 'select', 'textarea', 'button'):
                for attrs, ancestors in page.find(tag):
                    if not page.inside(ancestors, 'section', 'setup-recipes'):
                        continue
                    with self.subTest(version=version, tag=tag, id=attrs.get('id')):
                        self.assertNotIn('name', attrs)
                        self.assertFalse(page.inside(ancestors, 'form', 'main_form'))

    def test_no_button_of_the_section_can_submit_the_form(self):
        _html, page = setup_page(self.client, 'dofus3')
        for attrs, ancestors in page.find('button'):
            if page.inside(ancestors, 'section', 'setup-recipes'):
                self.assertEqual('button', attrs['type'], attrs)

    def test_the_share_and_saved_controls_are_drawn_hidden_or_empty_until_the_script_fills_them(self):
        _html, page = setup_page(self.client, 'dofus3')
        self.assertEqual(1, len(page.find('button', id='setup-share-copy')))
        self.assertIn('hidden', page.find('input', id='setup-share-url')[0][0])
        self.assertIn('readonly', page.find('input', id='setup-share-url')[0][0])
        self.assertIn('hidden', page.find('details', id='setup-saved')[0][0])
        self.assertEqual(1, len(page.find('ul', id='setup-saved-list')))
        self.assertEqual('40', page.find('input', id='setup-saved-name')[0][0]['maxlength'])

    def test_the_status_lines_are_live_regions_that_stay_in_the_page(self):
        _html, page = setup_page(self.client, 'dofus3')
        for element_id, tag in (('setup-recipes-note', 'p'), ('setup-share-status', 'span'),
                                ('setup-saved-status', 'p')):
            with self.subTest(element_id=element_id):
                attrs = page.find(tag, id=element_id)[0][0]
                self.assertEqual('status', attrs['role'])
                self.assertNotIn('hidden', attrs)

    def test_the_section_comes_before_the_form_so_a_preset_is_chosen_first(self):
        html, _page = setup_page(self.client, 'dofus3')
        self.assertLess(html.index('id="setup-recipes"'), html.index('id="main_form"'))


class TheSectionSpeaksEachLanguageTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_title_and_the_buttons_are_translated(self):
        for language in LANGUAGES[1:]:
            html, _page = setup_page(self.client, 'dofus3', language)
            with translation.override(language):
                for msgid in ('Start from a preset', 'Copy link', 'My setups', 'Save this setup',
                              'Name this setup', 'Link to this setup'):
                    with self.subTest(language=language, msgid=msgid):
                        self.assertIn(translation.gettext(msgid), html)
                        self.assertNotEqual(msgid, translation.gettext(msgid))
