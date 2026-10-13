# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A 14 AP minimum posted from /setup/ is stored as 12 on Touch and as 14 once the TemporiX switch is ticked, and the switch changes nothing where the version has none."""
from django.test import TestCase

from chardata.min_stats import get_min_stats_digested
from chardata.models import Char
from chardata.temporix_mode import char_uses_temporix
from chardata.tests_every_preset_keeps_its_weights_and_minimums import _version_path
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import DOORS, door_fields
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.temporix import version_has_temporix


WITHOUT_THE_SWITCH = {'dofus3': 12, 'beta': 12, 'dofus2': 12, 'retro': 14}


class TheTemporixSwitchLiftsTheApCapOfAPostedMinimumTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def stored_ap(self, version, door='wizard', temporix=False, minimum='14'):
        set_current_game_version(version)
        fields = door_fields(door, sorted(classes_of(version))[0], 200, one_element_box(version),
                             [('min_ap', minimum)] + ([('temporix', 'on')] if temporix else []))
        response = self.client.post(_version_path(version, '/createproject/'), dict(fields))
        self.assertEqual(302, response.status_code)
        char = Char.objects.order_by('-id').first()
        return get_min_stats_digested(char).get('AP'), char

    def test_touch_stores_the_minimum_capped_at_twelve_without_the_switch(self):
        stored, char = self.stored_ap('touch')
        self.assertEqual(12, stored)
        self.assertFalse(char_uses_temporix(char))

    def test_touch_stores_the_fourteen_asked_for_with_the_switch(self):
        stored, char = self.stored_ap('touch', temporix=True)
        self.assertEqual(14, stored)
        self.assertTrue(char_uses_temporix(char))

    def test_every_door_that_saves_a_minimum_agrees(self):
        for door in DOORS:
            with self.subTest(door=door):
                self.assertEqual(12, self.stored_ap('touch', door)[0])
                self.assertEqual(14, self.stored_ap('touch', door, temporix=True)[0])

    def test_a_minimum_under_the_cap_is_stored_as_typed_either_way(self):
        for temporix in (False, True):
            with self.subTest(temporix=temporix):
                self.assertEqual(9, self.stored_ap('touch', temporix=temporix, minimum='9')[0])

    def test_a_version_without_the_switch_ignores_it_and_keeps_its_own_cap(self):
        for version, cap in WITHOUT_THE_SWITCH.items():
            with self.subTest(version=version):
                self.assertFalse(version_has_temporix(version))
                stored, char = self.stored_ap(version, temporix=True)
                self.assertFalse(char_uses_temporix(char))
                self.assertEqual(cap, stored)

    def test_touch_is_the_version_that_has_the_switch(self):
        self.assertTrue(version_has_temporix('touch'))
