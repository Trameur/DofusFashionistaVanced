# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build or a form still carrying the retired flash or fast step is ignored and solves as the 90 seconds search."""
import re
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.char_blobs import read_char_blob
from chardata.create_project_view import create_project
from chardata.fashion_action import GUARD_BUDGET_SECONDS, _model_input
from chardata.models import Char
from chardata.options import set_options
from chardata.stats_weights import get_stats_weights
from chardata.tests_a_search_stopped_on_time_can_go_on import (
    BUTTON, GAP, NOT_PROVEN, PROVEN, WIDE_GAP, _outcome)
from chardata.tests_a_standard_search_with_two_solves_ends_inside_its_budget import (
    _RetroFlow, no_set)
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import door_fields
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from fashionistapulp import lpproblem
from fashionistapulp.structure import set_current_game_version

RETIRED = ('flash', 'fast')


class ARetiredStepIsNeverStoredTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('retired-step', 'retired@test.local', 'pw-retired-6')

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

    def test_a_posted_step_stores_the_options_of_a_post_without_it(self):
        for version in VERSIONS:
            today = self.options(self.create(version))
            self.assertNotIn('power', today)
            for key in RETIRED + ('standard', 'turbo'):
                with self.subTest(version=version, step=key):
                    char = self.create(version, [('power', key)])
                    self.assertEqual(today, self.options(char))


class AStoredRetiredStepSearchesAsStandardTests(_RetroFlow, TestCase):

    def retired(self, key):
        char = self.build_at(None)
        set_options(char, {'power': key})
        char.save()
        return Char.objects.get(pk=char.pk)

    def model_input(self, char):
        request = RequestFactory().get('/')
        request.user = self.owner
        request.game_version = char.game_version
        return _model_input(request, char, get_stats_weights(char, persist=False))

    def test_the_input_has_no_gap_and_the_key_of_a_build_without_the_step(self):
        plain = self.model_input(self.build_at(None))
        for key in RETIRED:
            with self.subTest(step=key):
                model_input = self.model_input(self.retired(key))
                self.assertEqual(0, model_input.gap)
                self.assertEqual(plain.cache_key(), model_input.cache_key())
                self.assertEqual(hash(plain), hash(model_input))

    def test_it_solves_once_on_the_whole_limit_and_never_errors(self):
        for key in RETIRED:
            with self.subTest(step=key):
                model, _location = self.fashion(self.retired(key),
                                                _outcome(self.hat, 1000.0, 1050.0))
                self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
                self.assertEqual(0, model.inputs[0].gap)

    def test_stopped_on_time_with_a_set_it_shows_the_best_found_and_the_continue_form(self):
        char = self.retired('flash')
        self.fashion(char, _outcome(self.hat, 1000.0, 1050.0))
        page = self.page(char)
        self.assertIn(NOT_PROVEN % lpproblem.TIME_LIMIT_SECONDS, page)
        self.assertTrue(GAP % '5.0' in page or WIDE_GAP % '5.0' in page)
        self.assertNotIn(PROVEN, page)
        self.assertNotIn('Quick search', page)
        self.assertIn(BUTTON, page)
        self.assertEqual('%s/continuesearch/%d/' % (self.prefix, char.pk), self.form_action(page))
        form = re.search(r'<form[^>]*solver-continue-search[^>]*>', page).group(0)
        self.assertIn('onsubmit="loadingAndRunUnchecked();"', form)
        self.assertNotIn('data-retry-budget', page)

    def test_the_waiting_screen_counts_to_the_whole_budget_only(self):
        char = self.retired('fast')
        response = self.client.get('%s/stats/%d/' % (self.prefix, char.pk),
                                   HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, response.status_code)
        page = response.content.decode('utf-8')
        bar = re.search(r'<div[^>]*class="loading-progress"[^>]*>', page).group(0)
        self.assertIn('data-budget="%d"' % GUARD_BUDGET_SECONDS, bar)
        self.assertNotIn('data-retry-budget', page)
        self.assertNotIn('stillSearching', page)

    def test_stopped_on_time_without_a_set_it_searches_once_and_offers_search_again(self):
        char = self.retired('flash')
        with mock.patch('chardata.fashion_action._closest_solve',
                        return_value={'state': 'skipped'}):
            model, location = self.fashion(char, no_set(lpproblem.TIME_LIMIT_SECONDS))
        self.assert_on_the_no_set_page(char, location)
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
        page = self.client.get(location, HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn('for up to %d seconds' % GUARD_BUDGET_SECONDS, page)
        self.assertIn('loadingAndRunUnchecked(%d)' % GUARD_BUDGET_SECONDS, page)
