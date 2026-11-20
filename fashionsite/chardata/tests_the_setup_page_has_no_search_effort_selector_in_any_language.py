# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ page offers no search effort selector in any version or language, and its strings are gone from the catalogues."""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.create_project_view import create_project
from chardata.models import Char
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import door_fields
from chardata.tests_the_setup_page_draws_the_live_weights_panel import _Page, setup_page
from chardata.tests_the_setup_panel_strings_are_translated_in_five_languages import (
    DASH, EMOJI, LANGUAGES, MARK, TRANSLATED, catalogue)
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from fashionistapulp.structure import set_current_game_version

LABELS = {
    'en': 'Search effort',
    'fr': 'Effort de recherche',
    'es': 'Esfuerzo de b' + chr(0xFA) + 'squeda',
    'pt': 'Esfor' + chr(0xE7) + 'o de busca',
    'de': 'Gr' + chr(0xFC) + 'ndlichkeit des Optimierers',
}
GONE = (
    'Flash', 'Fast', 'Standard', 'Search effort',
    'The search stops as soon as its set is within %(gap)s%% of the best on your criteria, '
    'or after %(seconds)s s per search. The build page tells you which.',
    'Looks for the best set on your criteria for up to %(seconds)s s per search. '
    'The build page tells you whether it was proven.',
    'Still searching: %%(elapsed)s s (at most %%(budget)s s)',
)
KEPT = (
    'Quick search: the solver stopped as soon as it knew this set is within %(gap)s%% of the best '
    'on your criteria. A better set may exist, so this is not a proof.',
    'Within %(gap)s%% of the best, not a proof',
)
MARKUP = ('setup-power-row', 'fm-card-power', 'setup-power', 'setup-power-key')


def assert_no_selector(test, html, page, language):
    for element_id in ('setup-power-row', 'fm-card-power', 'setup-power'):
        test.assertEqual([], page.find(id=element_id))
    test.assertEqual([], page.find('input', name='power'))
    for token in MARKUP:
        test.assertNotIn(token, html)
    test.assertNotIn(LABELS[language], html)


class TheSetupPageHasNoSearchEffortSelectorTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_every_version_and_language_draws_no_selector(self):
        for version in VERSIONS:
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    html, page = setup_page(self.client, version, language)
                    assert_no_selector(self, html, page, language)

    def test_the_edit_page_of_a_saved_build_has_none_either(self):
        owner = User.objects.create_user('no-effort', 'effort@test.local', 'pw-no-effort-6')
        self.client.force_login(owner)
        set_current_game_version('dofus3')
        char_class = sorted(classes_of('dofus3'))[0]
        request = RequestFactory().post('/', dict(door_fields('optimize', char_class, 200,
                                                              one_element_box('dofus3'))))
        request.user = owner
        request.game_version = 'dofus3'
        create_project(request)
        char = Char.objects.order_by('-id').first()
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.client.get('/project/%d/' % char.pk, HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(200, response.status_code)
                html = response.content.decode('utf-8')
                assert_no_selector(self, html, _Page(html), language)


class TheSelectorStringsAreGoneFromEveryCatalogueTests(TestCase):

    def test_no_catalogue_carries_a_deleted_string(self):
        for lang in LANGUAGES:
            catalog = catalogue(lang, 'django')
            for msgid in GONE:
                with self.subTest(lang=lang, msgid=msgid[:40]):
                    self.assertIsNone(catalog.find(msgid))

    def test_the_quick_search_lines_stay_translated_with_their_placeholders(self):
        for lang in TRANSLATED:
            catalog = catalogue(lang, 'django')
            for msgid in KEPT:
                with self.subTest(lang=lang, msgid=msgid[:40]):
                    entry = catalog.find(msgid)
                    self.assertIsNotNone(entry)
                    self.assertFalse(entry.obsolete)
                    self.assertNotIn('fuzzy', entry.flags)
                    self.assertTrue(entry.msgstr.strip())
                    self.assertNotEqual(msgid, entry.msgstr)
                    self.assertIn('python-format', entry.flags)
                    self.assertEqual(sorted(MARK.findall(msgid)), sorted(MARK.findall(entry.msgstr)))
                    self.assertIsNone(DASH.search(entry.msgstr))
                    self.assertIsNone(EMOJI.search(entry.msgstr))
