# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Bellaphone, the Dofus 3.8 class, is offered on the Beta alone and is safe without its game data."""
from django.test import SimpleTestCase, TestCase
from django.utils import translation

OTHER_VERSIONS = ('dofus3', 'dofus2', 'touch', 'retro')
GAME_NAMES = {'fr': 'Bellaphone', 'en': 'Bellaphone', 'es': 'Bel\u00edade',
              'pt': 'Bel\u00e9fone', 'de': 'Bellaphon'}


class BellaphoneIsListedOnTheBetaAloneTests(SimpleTestCase):

    def test_the_beta_lists_it(self):
        from chardata.version_compat import class_exists_in_version, filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        self.assertIn('Bellaphone', filter_classes_for_version(CHARACTER_CLASSES, 'beta'))
        self.assertTrue(class_exists_in_version('Bellaphone', 'beta'))

    def test_no_other_version_lists_it(self):
        from chardata.version_compat import class_exists_in_version, filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        for version in OTHER_VERSIONS:
            with self.subTest(version=version):
                self.assertNotIn('Bellaphone', filter_classes_for_version(CHARACTER_CLASSES, version))
                self.assertFalse(class_exists_in_version('Bellaphone', version))

    def test_the_beta_keeps_every_class_dofus3_has(self):
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        live = set(filter_classes_for_version(CHARACTER_CLASSES, 'dofus3'))
        beta = set(filter_classes_for_version(CHARACTER_CLASSES, 'beta'))
        self.assertEqual({'Bellaphone'}, beta - live)
        self.assertEqual(set(), live - beta)

    def test_the_game_breed_is_21(self):
        from chardata.character_look import CLASS_TO_BREED
        self.assertEqual(21, CLASS_TO_BREED['Bellaphone'])
        self.assertEqual(1, list(CLASS_TO_BREED.values()).count(21))

    def test_the_beta_constants_list_it_too(self):
        from fashionistapulp import dofus_constants_beta
        self.assertIn('Bellaphone', dofus_constants_beta.CHARACTER_CLASSES)

    def test_the_quick_start_offers_it_on_the_beta_with_its_own_figure(self):
        from chardata.home_view import quick_start_classes
        beta = {entry['key']: entry for entry in quick_start_classes('beta')}
        self.assertIn('Bellaphone', beta)
        self.assertIn('designs/wizard/Bellaphone/myWizardBellaphone1.png', beta['Bellaphone']['figure'])
        for version in OTHER_VERSIONS:
            with self.subTest(version=version):
                self.assertNotIn('Bellaphone', [e['key'] for e in quick_start_classes(version)])


class BellaphoneIsNamedInFiveLanguagesTests(SimpleTestCase):

    def test_each_language_uses_the_name_the_game_gives(self):
        from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
        for language, name in GAME_NAMES.items():
            with self.subTest(language=language), translation.override(language):
                self.assertEqual(name, str(LOCALIZED_CHARACTER_CLASSES['Bellaphone']))

    def test_the_five_catalogues_carry_the_entry(self):
        import os
        import re
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locale')
        for language, name in GAME_NAMES.items():
            path = os.path.join(root, language, 'LC_MESSAGES', 'django.po')
            with self.subTest(language=language):
                with open(path, encoding='utf-8') as handle:
                    text = handle.read()
                found = re.search(r'msgid "Bellaphone"\r?\nmsgstr "([^"]*)"', text)
                self.assertIsNotNone(found)
                self.assertEqual('' if language == 'en' else name, found.group(1))


class BellaphoneWorksWithoutItsGameDataTests(TestCase):

    def test_a_default_class_is_never_one_awaiting_its_data(self):
        from chardata.presets import version_class
        from chardata.setup_preview import panel_context
        self.assertNotEqual('Bellaphone', version_class('Nobody', 'beta'))
        self.assertTrue(panel_context('beta')['sections'])

    def test_the_setup_preview_answers_for_it(self):
        from chardata.setup_preview import DEFAULT_PLAY_MODE, DEFAULT_PRIORITY, preview_state
        state = preview_state('beta', 'Bellaphone', 200, frozenset(), DEFAULT_PRIORITY,
                              DEFAULT_PLAY_MODE, False)
        self.assertIn('weights', state)

    def test_the_default_profile_stands_in_for_the_missing_class_profile(self):
        from chardata.smart_build import RACE_TO_BUILD_PROFILE, param_for_build
        self.assertNotIn('Bellaphone', RACE_TO_BUILD_PROFILE)
        self.assertEqual(RACE_TO_BUILD_PROFILE['default']['vit_importance'],
                         param_for_build('Bellaphone', set(), 'vit_importance', game_version='beta'))

    def test_a_player_can_write_its_name_in_any_language(self):
        from chardata.nl_parser import _CLASS_ALIAS_INDEX, _normalize
        for name in GAME_NAMES.values():
            with self.subTest(name=name):
                self.assertEqual('Bellaphone', _CLASS_ALIAS_INDEX[_normalize(name)])

    def test_a_build_read_from_a_breed_id_finds_it(self):
        from chardata.fashionista_build import _class_of
        self.assertEqual('Bellaphone', _class_of(21))
        self.assertEqual('Bellaphone', _class_of('bellaphone'))

    def test_a_dofus3_page_does_not_offer_it_as_the_class_of_a_build(self):
        from chardata.presets import version_class
        self.assertNotEqual('Bellaphone', version_class('Bellaphone', 'dofus3'))


def _select_options(html):
    import re
    block = re.search(r'<select[^>]*id="select-char-class".*?</select>', html, re.S).group(0)
    return re.findall(r'<option value="([^"]*)"', block)


class TheSetupClassSelectFollowsTheVersionTests(TestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        self.addCleanup(set_current_game_version, 'dofus3')

    def options(self, version, language):
        from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
        html, _page = setup_page(self.client, version, language)
        return _select_options(html)

    def test_no_language_leaks_a_class_the_version_lacks(self):
        from chardata.version_compat import CLASSES_NOT_IN_VERSION
        for version in OTHER_VERSIONS:
            for language in GAME_NAMES:
                with self.subTest(version=version, language=language):
                    options = self.options(version, language)
                    for absent in CLASSES_NOT_IN_VERSION.get(version, ()):
                        self.assertNotIn(absent, options)

    def test_forgelance_stays_out_of_dofus2_touch_and_retro(self):
        for version in ('dofus2', 'touch', 'retro'):
            for language in GAME_NAMES:
                with self.subTest(version=version, language=language):
                    self.assertNotIn('Forgelance', self.options(version, language))

    def test_the_beta_offers_it_in_every_language(self):
        for language in GAME_NAMES:
            with self.subTest(language=language):
                options = self.options('beta', language)
                self.assertIn('Bellaphone', options)
                self.assertIn('Forgelance', options)

    def test_the_select_starts_with_an_empty_option(self):
        for version in OTHER_VERSIONS + ('beta',):
            with self.subTest(version=version):
                self.assertEqual('', self.options(version, 'en')[0])


class TheSmartBuildReadsOnlyTheClassesOfItsVersionTests(TestCase):

    def test_dofus3_does_not_read_it(self):
        from chardata.nl_parser import parse_build_request
        parsed = parse_build_request('bellaphone 200 terre pvm', 'dofus3')
        self.assertIsNone(parsed['char_class'])
        self.assertFalse(parsed['matched_class'])

    def test_the_beta_keeps_it(self):
        from chardata.nl_parser import parse_build_request
        parsed = parse_build_request('bellaphone 200 terre pvm', 'beta')
        self.assertEqual('Bellaphone', parsed['char_class'])
        self.assertTrue(parsed['matched_class'])

    def test_a_posted_phrase_on_dofus3_asks_for_the_class(self):
        from chardata.models import Char
        before = Char.objects.count()
        response = self.client.post('/smartbuild/', {'q': 'bellaphone 200 terre pvm', 'confirm': '1'},
                                    HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, response.status_code)
        self.assertEqual(before, Char.objects.count())
        self.assertContains(response, 'Tell us which class')
