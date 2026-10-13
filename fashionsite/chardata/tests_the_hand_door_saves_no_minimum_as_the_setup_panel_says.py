# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ panel says minimums are saved through the Wizard door only, and the two creation doors do exactly that."""
from django.test import TestCase
from django.utils import translation

from chardata import setup_preview
from chardata.models import Char
from chardata.presets import ELEMENT_BOXES, setup_boxes
from chardata.smart_build import inert_aspects
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import (
    _DoorBuilds, classes_of, form_fields)
from chardata.weights_minimums import page_state
from fashionistapulp.structure import set_current_game_version

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
DOOR_NOTE = 'Minimums are saved when you continue to the Wizard. Creating a set by hand saves the weights only.'


def shown(values):
    return {key: value for key, value in values.items() if value != ''}


def one_element_box(version):
    offered = setup_boxes(version) - set(inert_aspects(version))
    return frozenset({sorted(offered & set(ELEMENT_BOXES))[0]})


class TheTwoDoorsSaveMinimumsAsThePanelSaysTests(_DoorBuilds, TestCase):

    def saved(self, version, door):
        char_class = sorted(classes_of(version))[0]
        boxes = one_element_box(version)
        fields = [(key, value) for key, value in form_fields(char_class, 200, boxes)
                  if key != 'wizard'] + [(door, door)]
        built = self.door_build(version, fields)
        set_current_game_version(version)
        preview = setup_preview.preview_state(version, char_class, 200, boxes)
        return preview, page_state(Char.objects.get(pk=built.pk))

    def test_the_wizard_door_saves_every_minimum_the_preview_shows(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                preview, saved = self.saved(version, 'wizard')
                self.assertTrue(shown(preview['minimums']))
                self.assertEqual(shown(preview['minimums']), shown(saved['minimums']))

    def test_the_hand_door_saves_the_weights_the_preview_shows_and_no_minimum(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                preview, saved = self.saved(version, 'byhand')
                self.assertTrue(shown(preview['minimums']))
                self.assertEqual({}, shown(saved['minimums']))
                self.assertEqual(preview['weights'], saved['weights'])


class TheSetupPageSaysItInEveryLanguageTests(TestCase):

    def test_the_panel_carries_the_note_in_the_language_of_the_reader(self):
        for language in LANGUAGES:
            with translation.override(language):
                wanted = translation.gettext(DOOR_NOTE)
            for version in VERSIONS:
                with self.subTest(language=language, version=version):
                    html, page = setup_page(self.client, version, language)
                    notes = page.find('p', id='setup-preview-door')
                    self.assertEqual(1, len(notes))
                    self.assertTrue(page.inside(notes[0][1], 'aside', 'setup-preview'))
                    self.assertIn(wanted, html)
        set_current_game_version('dofus3')
