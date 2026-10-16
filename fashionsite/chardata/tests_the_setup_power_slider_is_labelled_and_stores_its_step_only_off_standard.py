# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ power slider is a labelled range, and a new build stores its step only when it is not Standard."""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.char_blobs import read_char_blob
from chardata.create_project_view import create_project
from chardata.fashion_action import _model_input
from chardata.models import Char
from chardata.power_steps import POWER_BY_KEY, POWER_STEPS, stored_power
from chardata.stats_weights import get_stats_weights
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import door_fields
from chardata.tests_the_setup_page_draws_the_live_weights_panel import _Page, setup_page
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from fashionistapulp.structure import set_current_game_version


class TheSliderIsALabelledRangeTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_every_version_draws_one_range_with_a_label_a_value_text_and_a_description(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                (range_attrs, ancestors), = page.find('input', id='setup-power')
                self.assertEqual('range', range_attrs['type'])
                self.assertEqual(('0', str(len(POWER_STEPS) - 1), '1'),
                                 (range_attrs['min'], range_attrs['max'], range_attrs['step']))
                standard = [index for index, step in enumerate(POWER_STEPS)
                            if step.key == 'standard'][0]
                self.assertEqual(str(standard), range_attrs['value'])
                self.assertEqual('Standard', range_attrs['aria-valuetext'])
                self.assertEqual(1, len(page.find('label', **{'for': 'setup-power'})))
                self.assertEqual(1, len(page.find(id=range_attrs['aria-describedby'])))
                self.assertTrue(page.inside(ancestors, 'form', 'main_form'))

    def test_the_posted_field_says_standard_until_the_player_moves_the_slider(self):
        _html, page = setup_page(self.client, 'dofus3')
        (hidden, _ancestors), = page.find('input', name='power')
        self.assertEqual(('hidden', 'standard'), (hidden['type'], hidden['value']))

    def test_every_step_is_named_with_its_explanation(self):
        html, page = setup_page(self.client, 'dofus3')
        named = [attrs['data-power'] for attrs, _a in page.find('span')
                 if 'setup-power-step' in attrs.get('class', '').split()]
        self.assertEqual([step.key for step in POWER_STEPS], named)
        for step in POWER_STEPS:
            self.assertIn(str(step.label), html)
        self.assertIn('within 3% of the best', html)
        self.assertIn('within 1% of the best', html)
        self.assertNotIn('proven within', html)

    def test_the_edit_page_of_a_build_has_no_slider(self):
        owner = User.objects.create_user('power-edit', 'edit@test.local', 'pw-power-edit-6')
        self.client.force_login(owner)
        set_current_game_version('dofus3')
        char_class = sorted(classes_of('dofus3'))[0]
        request = RequestFactory().post('/', dict(door_fields('optimize', char_class, 200,
                                                              one_element_box('dofus3'))))
        request.user = owner
        request.game_version = 'dofus3'
        create_project(request)
        char = Char.objects.order_by('-id').first()
        response = self.client.get('/project/%d/' % char.pk, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, response.status_code)
        page = _Page(response.content.decode('utf-8'))
        self.assertEqual([], page.find('input', id='setup-power'))
        self.assertEqual([], page.find('input', name='power'))


class TheNewBuildStoresTheStepTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('power-step', 'power@test.local', 'pw-power-step-6')

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def create(self, version, extra=()):
        set_current_game_version(version)
        char_class = sorted(classes_of(version))[0]
        data = {}
        for key, value in door_fields('optimize', char_class, 200, one_element_box(version)) + list(extra):
            data.setdefault(key, []).append(value)
        request = RequestFactory().post('/', data)
        request.user = self.owner
        request.game_version = version
        self.assertEqual(302, create_project(request).status_code)
        set_current_game_version(version)
        return Char.objects.order_by('-id').first()

    def options(self, char):
        return read_char_blob(char.options, {}, 'options', char)

    def gap(self, char):
        request = RequestFactory().get('/')
        request.user = self.owner
        request.game_version = char.game_version
        return _model_input(request, char, get_stats_weights(char, persist=False)).gap

    def test_no_field_or_standard_stores_the_options_of_today_and_searches_with_no_gap(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                today = self.create(version)
                standard = self.create(version, [('power', 'standard')])
                unknown = self.create(version, [('power', 'turbo')])
                self.assertNotIn('power', self.options(today))
                self.assertEqual(self.options(today), self.options(standard))
                self.assertEqual(self.options(today), self.options(unknown))
                for char in (today, standard, unknown):
                    self.assertIs(POWER_BY_KEY['standard'], stored_power(char))
                    self.assertEqual(0, self.gap(char))

    def test_flash_and_fast_are_stored_and_give_the_solver_their_gap(self):
        for version in VERSIONS:
            for key in ('flash', 'fast'):
                with self.subTest(version=version, step=key):
                    today = self.options(self.create(version))
                    char = self.create(version, [('power', key)])
                    self.assertEqual(dict(today, power=key), self.options(char))
                    self.assertEqual(POWER_BY_KEY[key].gap, self.gap(char))
