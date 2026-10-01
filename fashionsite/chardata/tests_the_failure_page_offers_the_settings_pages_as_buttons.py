# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The failure page leads to each settings page by a button, and every language fills it."""
import pickle

from django.test import TestCase
from django.utils import translation
from django.utils.html import escape
from django.utils.translation import gettext

from chardata import fashion_action
from chardata.min_stats import get_min_stats
from chardata.tests_a_build_with_no_set_is_shown_its_closest_set import (_BuildMixin, _Clock,
                                                                         _ElasticModel)
from chardata.tests_a_search_stopped_on_time_without_a_set_says_so import _StopMixin

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
BUTTONS = (('min_stats', 'Minimum Characteristics'), ('inclusions', 'Lock Items'),
           ('stats', 'Characteristics Weights'), ('options', 'Options'))


def _failure_body(page):
    start = page.index('class="infeasible-layout"')
    return page[start:page.index('</ul>', start)]


class _FailurePageMixin(_BuildMixin):
    prefix = ''

    def failure_page(self, char, language='en'):
        language_prefix = '' if language == 'en' else '/' + language
        response = self.client.get('%s%s/infeasible/%d/' % (language_prefix, self.prefix, char.pk),
                                   HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')


class TheFailurePageLeadsToEachSettingsPageTests(_FailurePageMixin, TestCase):

    def test_four_buttons_lead_to_minimums_locks_weights_and_options(self):
        char = self.build()
        body = _failure_body(self.failure_page(char))
        for name, label in BUTTONS:
            with self.subTest(page=name):
                self.assertIn('<a class="button-generic" href="%s/%s/%d/">%s</a>'
                              % (self.prefix, name, char.pk, label), body)

    def test_the_banner_edit_button_still_opens_the_build_setup(self):
        char = self.build()
        page = self.failure_page(char)
        self.assertRegex(page, r'href="%s/project/%d/"[^>]*>Edit</a>' % (self.prefix, char.pk))


class TouchLeadsToItsOwnSettingsPagesTests(TheFailurePageLeadsToEachSettingsPageTests):
    version = 'touch'
    prefix = '/touch'


class RetroLeadsToItsOwnSettingsPagesTests(TheFailurePageLeadsToEachSettingsPageTests):
    version = 'retro'
    prefix = '/retro'


class TheTipsNameWhatCanBeChangedTests(_FailurePageMixin, TestCase):

    def test_an_unreachable_minimum_keeps_its_own_tip(self):
        char = self.build()
        char.minimum_stats = pickle.dumps(dict(get_min_stats(char), AP=99))
        char.save()
        body = _failure_body(self.failure_page(char))
        self.assertRegex(body, r'Lower these <a href="?/min_stats/%d/"?>minimums</a>, which ask for '
                               r'more than this version can reach:' % char.pk)
        self.assertRegex(body, r'AP \(\d+\)')

    def test_the_level_tip_takes_the_place_of_the_critical_hit_tip(self):
        body = _failure_body(self.failure_page(self.build()))
        self.assertIn("Check that your minimums suit the character's level", body)
        self.assertNotIn('crits', body)
        self.assertNotIn('&#x00BD;', body)


class EveryLanguageFillsTheFailurePageTests(_StopMixin, _FailurePageMixin, TestCase):

    def test_no_language_leaves_a_placeholder_or_an_english_button(self):
        char = self.build()
        self.stop(char, seconds=30)
        for language in LANGUAGES:
            with self.subTest(language=language):
                body = _failure_body(self.failure_page(char, language))
                self.assertNotIn('%(', body)
                self.assertNotIn('{{', body)
                self.assertNotIn('{%', body)
                with translation.override(language):
                    expected = [escape(gettext(text)) for text in (
                        'Search again', 'Closest set found', 'Keep this set',
                        'Minimum Characteristics', 'Lock Items')]
                for text in expected:
                    self.assertIn(text, body)
                if language != 'en':
                    self.assertNotIn('Keep this set', body)
                    self.assertNotIn('minimums reached', body)

    def test_every_language_says_a_closest_set_found_on_time_may_not_be_the_closest(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(fashion_action.CLOSEST_SECONDS, 'Optimal'),
                                           (3, 'Optimal')], [self.hat.id], proven=False)
        self.solve_to_failure(char, elastic)
        sentence = ('This is the closest set to your minimums the solver found in %(seconds)s '
                    'seconds, with every locked item, forbidden item and item condition kept. It '
                    'ran out of time before it could prove that no set comes closer.')
        for language in LANGUAGES:
            with self.subTest(language=language):
                body = _failure_body(self.failure_page(char, language))
                with translation.override(language):
                    expected = gettext(sentence) % {'seconds': fashion_action.CLOSEST_SECONDS}
                if language != 'en':
                    self.assertNotEqual(sentence % {'seconds': fashion_action.CLOSEST_SECONDS},
                                        expected)
                self.assertIn(expected, body)
                self.assertNotIn('%(', body)
