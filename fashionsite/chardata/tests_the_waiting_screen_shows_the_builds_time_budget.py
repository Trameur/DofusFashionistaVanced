# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The waiting screen counts towards the longest the build's solve may take, in the page language."""
import pickle
import re
from unittest import mock

from django.test import TestCase
from django.utils import translation
from django.utils.html import escapejs
from django.utils.translation import gettext

from chardata import fashion_action
from chardata.tests_a_build_with_no_set_is_shown_its_closest_set import _BuildMixin
from fashionistapulp import lpproblem

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
SEARCHING = 'Searching: %(elapsed)s s (at most %(budget)s s)'
ALMOST_DONE = 'Almost done'


def _trans_tag(text):
    """What {% trans %} prints for text: its percent signs are doubled for the lookup and restored after."""
    return gettext(text.replace('%', '%%')).replace('%%', '%')


class _WaitingMixin(_BuildMixin):
    prefix = ''

    def weights_page(self, char, language='en'):
        language_prefix = '' if language == 'en' else '/' + language
        response = self.client.get('%s%s/stats/%d/' % (language_prefix, self.prefix, char.pk),
                                   HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def budget(self, page):
        found = re.findall(r'<div[^>]*class="loading-progress"[^>]*>', page)
        self.assertEqual(1, len(found), 'one progress bar on the page')
        return (re.search(r'data-budget="([^"]*)"', found[0]).group(1),
                re.search(r'aria-valuemax="([^"]*)"', found[0]).group(1))

    def without_minimums(self):
        char = self.build()
        char.minimum_stats = pickle.dumps({})
        char.save()
        return char


class TheBudgetIsTheBuildsOwnTests(_WaitingMixin, TestCase):

    def test_a_build_with_a_minimum_counts_towards_the_whole_budget(self):
        budget = str(fashion_action.GUARD_BUDGET_SECONDS)
        self.assertEqual((budget, budget), self.budget(self.weights_page(self.build())))

    def test_a_build_without_a_minimum_counts_towards_the_whole_budget(self):
        budget = str(fashion_action.GUARD_BUDGET_SECONDS)
        self.assertEqual((budget, budget), self.budget(self.weights_page(self.without_minimums())))

    def test_a_build_with_a_safeguard_counts_towards_the_whole_budget(self):
        char = self.without_minimums()
        with mock.patch('chardata.fashion_action.guard_plan', return_value=('damage', 10)):
            page = self.weights_page(char)
        budget = str(fashion_action.GUARD_BUDGET_SECONDS)
        self.assertEqual((budget, budget), self.budget(page))

    def test_the_budget_is_a_plain_number_in_every_language(self):
        char = self.build()
        for language in LANGUAGES:
            with self.subTest(language=language):
                data_budget, maximum = self.budget(self.weights_page(char, language))
                self.assertRegex(data_budget, r'^\d+$')
                self.assertEqual(data_budget, maximum)


class TheCounterSpeaksThePageLanguageTests(_WaitingMixin, TestCase):

    def test_each_language_carries_its_own_counter_words(self):
        char = self.build()
        for language in LANGUAGES:
            with self.subTest(language=language):
                page = self.weights_page(char, language)
                with translation.override(language):
                    searching, almost_done = _trans_tag(SEARCHING), _trans_tag(ALMOST_DONE)
                if language != 'en':
                    self.assertNotEqual(SEARCHING, searching)
                    self.assertNotEqual(ALMOST_DONE, almost_done)
                self.assertIn("'%s'" % escapejs(searching), page)
                self.assertIn("'%s'" % escapejs(almost_done), page)
                self.assertNotIn('%%(', page)

    def test_the_counter_fills_its_placeholders_in_the_browser(self):
        page = self.weights_page(self.build(), 'fr')
        self.assertIn('interpolate(searching, {elapsed: elapsed, budget: budget}, true)', page)

    def test_a_button_hands_its_budget_to_the_counter(self):
        page = self.weights_page(self.build())
        self.assertIn('function loadingAndRunUnchecked(budget)', page)
        self.assertIn('startSolveProgress(budget);', page)


class ABuildOnAModelOfItsOwnCountsItsBuildTests(_WaitingMixin, TestCase):
    version = 'touch'
    prefix = '/touch'

    def temporix_build(self):
        char = self.build()
        char.options = pickle.dumps({'temporix': True})
        char.save()
        return char

    def test_before_any_build_is_timed_the_first_guess_is_counted(self):
        with mock.patch.dict(fashion_action._BUILD_SECONDS, {}, clear=True):
            page = self.weights_page(self.temporix_build())
        budget = str(lpproblem.TIME_LIMIT_SECONDS + fashion_action.FIRST_BUILD_SECONDS)
        self.assertEqual((budget, budget), self.budget(page))

    def test_the_last_build_of_the_version_is_counted_in_whole_seconds(self):
        with mock.patch.dict(fashion_action._BUILD_SECONDS, {self.version: 12.3}, clear=True):
            page = self.weights_page(self.temporix_build())
        budget = str(lpproblem.TIME_LIMIT_SECONDS + 13)
        self.assertEqual((budget, budget), self.budget(page))

    def test_a_quick_build_never_counts_below_the_whole_budget(self):
        with mock.patch.dict(fashion_action._BUILD_SECONDS, {self.version: 1.0}, clear=True):
            page = self.weights_page(self.temporix_build())
        budget = str(fashion_action.GUARD_BUDGET_SECONDS)
        self.assertEqual((budget, budget), self.budget(page))


class TouchCountsTowardsItsBudgetUnderItsPrefixTests(TheBudgetIsTheBuildsOwnTests):
    version = 'touch'
    prefix = '/touch'


class RetroCountsTowardsItsBudgetUnderItsPrefixTests(TheBudgetIsTheBuildsOwnTests):
    version = 'retro'
    prefix = '/retro'
