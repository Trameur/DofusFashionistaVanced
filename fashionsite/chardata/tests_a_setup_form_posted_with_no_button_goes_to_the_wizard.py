# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A /setup/ form posted with no button name, or with a name no door owns, creates the build the Wizard door creates and goes to the Wizard."""
from django.test import TestCase
from django.urls import resolve

from chardata.models import Char
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_optimize_door_stores_the_wizard_build_and_opens_the_solution import stored_build
from chardata.tests_the_setup_creation_doors_support import door_fields
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from fashionistapulp.structure import set_current_game_version


class ANamelessSubmitGoesToTheWizardTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def post(self, version, extra=(), door='wizard'):
        set_current_game_version(version)
        fields = [(key, value) for key, value in door_fields(
            door, sorted(classes_of(version))[0], 200, one_element_box(version))
            if key != door] + list(extra)
        response = self.client.post(_version_path(version, '/createproject/'), dict(fields))
        self.assertEqual(302, response.status_code)
        return Char.objects.order_by('-id').first(), response

    def test_a_form_with_no_button_goes_to_the_wizard_page_of_the_new_build(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                char, response = self.post(version)
                self.assertEqual(_version_path(version, '/wizard/%d/' % char.pk),
                                 response['Location'])
                self.assertEqual('wizard', resolve(response['Location']).url_name)

    def test_a_name_no_door_owns_changes_nothing(self):
        for version in VERSIONS:
            for name in ('continue', 'submit', 'Optimize now'):
                with self.subTest(version=version, name=name):
                    char, response = self.post(version, [(name, name)])
                    self.assertEqual('wizard', resolve(response['Location']).url_name)

    def test_the_build_is_the_one_the_wizard_button_stores(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                bare, _ = self.post(version)
                named, _ = self.post(version, [('wizard', 'wizard')])
                self.assertNotEqual(bare.pk, named.pk)
                self.assertEqual(stored_build(named), stored_build(bare))
