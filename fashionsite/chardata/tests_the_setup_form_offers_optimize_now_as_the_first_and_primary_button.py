# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ form draws Optimize now as its first and primary button, with the hand door and the wizard door after it as secondary buttons."""
from django.test import TestCase
from django.utils import translation

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import LANGUAGES, setup_page


class TheSetupFormButtonsTests(TestCase):

    def buttons(self, version, language='en'):
        _html, page = setup_page(self.client, version, language)
        return [attrs for attrs, ancestors in page.find('input')
                if attrs.get('type') == 'submit' and page.inside(ancestors, 'form', 'main_form')
                and 'setup-default-door' not in attrs.get('class', '').split()]

    def test_the_form_has_three_submit_buttons_optimize_first_in_every_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(['optimize', 'byhand', 'wizard'],
                                 [button['name'] for button in self.buttons(version)])

    def test_only_the_first_button_is_primary(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                classes = [button['class'].split() for button in self.buttons(version)]
                self.assertIn('setup-primary', classes[0])
                self.assertNotIn('setup-secondary', classes[0])
                for secondary in classes[1:]:
                    self.assertIn('setup-secondary', secondary)
                    self.assertNotIn('setup-primary', secondary)

    def test_the_buttons_read_optimize_now_create_a_set_by_hand_and_continue_to_wizard(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(['Optimize now', 'Create a set by hand', 'Continue to Wizard'],
                                 [button['value'] for button in self.buttons(version)])

    def test_every_language_translates_the_three_buttons(self):
        for language in LANGUAGES[1:]:
            with translation.override(language):
                wanted = [translation.gettext(text) for text in (
                    'Optimize now', 'Create a set by hand', 'Continue to Wizard')]
            with self.subTest(language=language):
                self.assertEqual(wanted, [button['value'] for button in
                                          self.buttons('dofus3', language)])
                self.assertEqual(3, len(set(wanted)))
                self.assertNotIn('Optimize now', wanted)
