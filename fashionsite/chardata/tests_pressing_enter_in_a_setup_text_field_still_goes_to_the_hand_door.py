# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Pressing Enter in a /setup/ text field still creates the set by hand, because a hidden hand door is the first submit button of the form and Optimize stays the first visible primary button."""
from django.test import SimpleTestCase, TestCase

from chardata.models import Char
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import door_fields
from chardata.tests_the_setup_page_draws_the_live_weights_panel import LANGUAGES, setup_page
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from chardata.tests_the_setup_stylesheet_support import declared, stylesheet
from fashionistapulp.structure import set_current_game_version

SETUP = stylesheet('setup.css')
DEFAULT_DOOR = '#submit-mode input.setup-default-door'


def submits_in_tree_order(page):
    return [(attrs, ancestors) for attrs, ancestors in page.find('input')
            if attrs.get('type') == 'submit' and page.inside(ancestors, 'form', 'main_form')]


class TheFirstSubmitButtonOfTheFormIsTheHiddenHandDoorTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_first_submit_in_tree_order_is_the_hand_door_inside_the_door_group(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                first, ancestors = submits_in_tree_order(page)[0]
                self.assertEqual('byhand', first['name'])
                self.assertIn('setup-default-door', first['class'].split())
                self.assertTrue(page.inside(ancestors, 'div', 'submit-mode'))

    def test_the_hidden_door_is_out_of_the_tab_order_and_out_of_the_reading_order(self):
        _html, page = setup_page(self.client, 'dofus3')
        first = submits_in_tree_order(page)[0][0]
        self.assertEqual('-1', first['tabindex'])
        self.assertEqual('true', first['aria-hidden'])

    def test_it_carries_the_label_of_the_visible_hand_door_in_every_language(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                _html, page = setup_page(self.client, 'dofus3', language)
                submits = [attrs for attrs, _ in submits_in_tree_order(page)]
                visible = [attrs for attrs in submits
                           if attrs['name'] == 'byhand'
                           and 'setup-default-door' not in attrs['class'].split()]
                self.assertEqual(1, len(visible))
                self.assertEqual(visible[0]['value'], submits[0]['value'])

    def test_the_form_has_one_hidden_door_and_three_visible_ones_with_optimize_first(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                submits = [attrs for attrs, _ in submits_in_tree_order(page)]
                hidden = [attrs for attrs in submits
                          if 'setup-default-door' in attrs['class'].split()]
                visible = [attrs for attrs in submits if attrs not in hidden]
                self.assertEqual(1, len(hidden))
                self.assertEqual(['optimize', 'byhand', 'wizard'],
                                 [attrs['name'] for attrs in visible])
                self.assertIn('setup-primary', visible[0]['class'].split())

    def test_nothing_that_submits_the_form_stands_before_the_hidden_door(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                every_submitter = [attrs for name, attrs, ancestors in page.elements
                                   if page.inside(ancestors, 'form', 'main_form')
                                   and ((name == 'input' and attrs.get('type') in ('submit', 'image'))
                                        or (name == 'button' and attrs.get('type', 'submit') == 'submit'))]
                self.assertIn('setup-default-door', every_submitter[0].get('class', '').split())


class EnterSubmitsTheFieldsOfTheHandDoorTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_a_form_submitted_with_the_hidden_door_goes_to_the_hand_solution_page(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                fields = door_fields('byhand', sorted(classes_of(version))[0], 200,
                                     one_element_box(version))
                response = self.client.post(_version_path(version, '/createproject/'), dict(fields))
                self.assertEqual(302, response.status_code)
                char = Char.objects.order_by('-id').first()
                self.assertEqual(_version_path(version, '/solution/%d/True/' % char.pk),
                                 response['Location'])


class TheHiddenDoorIsClippedAwayAndNotRemovedTests(SimpleTestCase):

    def declared(self, prop):
        return declared(SETUP, DEFAULT_DOOR, prop)

    def test_it_is_taken_out_of_the_flow_and_shrunk_to_one_pixel(self):
        self.assertEqual(('absolute', True), self.declared('position'))
        self.assertEqual(('1px', True), self.declared('width'))
        self.assertEqual(('1px', True), self.declared('height'))
        self.assertEqual(('-1px', True), self.declared('margin'))

    def test_it_is_clipped_transparent_and_cannot_be_clicked(self):
        self.assertEqual('rect(0 0 0 0)', self.declared('clip')[0])
        self.assertEqual('hidden', self.declared('overflow')[0])
        self.assertEqual('0', self.declared('opacity')[0])
        self.assertEqual('none', self.declared('pointer-events')[0])

    def test_it_is_not_removed_with_display_none_or_visibility_hidden(self):
        self.assertIsNone(self.declared('display'))
        self.assertIsNone(self.declared('visibility'))
