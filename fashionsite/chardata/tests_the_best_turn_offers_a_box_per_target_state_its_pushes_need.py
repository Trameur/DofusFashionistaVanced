# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The best turn offers one box per target state a castable push of the class needs, ticked when a spell keeps that state for the whole fight."""
import json
from unittest import mock

from django.test import RequestFactory, SimpleTestCase
from django.utils import translation

from chardata import spells_view
from chardata.spell_combo import castable_spells
from chardata.spell_reference import target_state_name
from chardata.tests_a_target_free_best_combo_is_unchanged import (
    VERSIONS, APayloadWithoutATargetTests, _classes, _in_version)

PAINT, PREY, BLOWN = 4244, 516, 807
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def _boxes(version, char_class, language='en', **kwargs):
    with translation.override(language):
        combo = APayloadWithoutATargetTests._combo(None, version, char_class, **kwargs)
    return combo['target_states'], combo


class TheBoxesATurnOffersTests(SimpleTestCase):

    def test_a_dofus2_eniripsa_gets_one_unchecked_paint_box(self):
        _in_version(self, 'dofus2')
        self.assertEqual([{'id': PAINT, 'checked': False,
                           'label': 'Target starts the turn in the Paint state'}],
                         _boxes('dofus2', 'Eniripsa')[0])

    def test_a_dofus2_ouginak_gets_a_checked_prey_box_since_prey_lasts_the_fight(self):
        _in_version(self, 'dofus2')
        self.assertEqual([{'id': PREY, 'checked': True,
                           'label': 'Target starts the turn in the Prey state'}],
                         _boxes('dofus2', 'Ouginak')[0])

    def test_a_touch_iop_gets_a_blown_box_named_in_each_language(self):
        names = {'en': 'Blown', 'fr': 'Soufflé', 'es': 'Inflado', 'pt': 'Inflado', 'de': 'Blown'}
        for version in ('touch', 'touchbeta'):
            _in_version(self, version)
            for language, name in names.items():
                with self.subTest(version=version, language=language):
                    boxes, _combo = _boxes(version, 'Iop', language)
                    self.assertEqual([BLOWN], [box['id'] for box in boxes])
                    self.assertFalse(boxes[0]['checked'])
                    self.assertIn(name, boxes[0]['label'])
        _in_version(self, 'touch')
        self.assertEqual("La cible commence le tour dans l'état Soufflé",
                         _boxes('touch', 'Iop', 'fr')[0][0]['label'])

    def test_a_class_with_no_target_state_push_gets_no_box(self):
        for version, char_class in (('dofus3', 'Eniripsa'), ('dofus3', 'Huppermage'),
                                    ('dofus3', 'Cra'), ('dofus2', 'Huppermage')):
            _in_version(self, version)
            with self.subTest(version=version, char_class=char_class):
                self.assertEqual([], _boxes(version, char_class)[0])

    def test_a_ticked_box_raises_the_pushback_turn(self):
        _in_version(self, 'dofus2')
        _boxes_off, unticked = _boxes('dofus2', 'Eniripsa', pushback=True,
                                      target_states={PAINT: False})
        _boxes_on, ticked = _boxes('dofus2', 'Eniripsa', pushback=True,
                                   target_states={PAINT: True})
        _boxes_none, default = _boxes('dofus2', 'Eniripsa', pushback=True, target_states=None)
        self.assertGreater(ticked['total'], unticked['total'])
        self.assertEqual(unticked['total'], default['total'])
        self.assertEqual([True], [box['checked'] for box in _boxes_on])

    def test_every_state_a_box_offers_has_a_game_name_in_each_language(self):
        for version in VERSIONS:
            _in_version(self, version)
            for char_class in _classes(version):
                for castable in castable_spells(char_class, 200, version):
                    state = castable.push_target_state
                    if state is None:
                        continue
                    for language in LANGUAGES:
                        with self.subTest(version=version, char_class=char_class,
                                          state=state, language=language):
                            self.assertTrue(target_state_name(version, state, language))


class ThePanelRequestTests(SimpleTestCase):

    def _post(self, **fields):
        request = RequestFactory().post('/best_combo/', dict({'pushback': 'false'}, **fields))
        request.game_version = 'dofus2'
        seen = []

        def combo(char, solution, game_version, *args, **kwargs):
            seen.append(kwargs.get('target_states'))
            return {'total': 1}

        with mock.patch.object(spells_view, 'get_solution', return_value=object()), \
                mock.patch.object(spells_view, '_best_combo', combo):
            response = spells_view._best_combo_response(request, mock.Mock())
        self.assertEqual(200, response.status_code)
        self.assertEqual({'best_combo': {'total': 1}}, json.loads(response.content))
        return seen[0]

    def test_the_panel_request_passes_the_ticked_states_and_none_without_the_field(self):
        self.assertEqual({PAINT: True},
                         self._post(target_states='{"4244": true, "x": true, "516": 1}'))
        self.assertEqual({PAINT: False, PREY: True},
                         self._post(target_states='{"4244": false, "516": true}'))
        self.assertEqual({}, self._post(target_states='not json'))
        self.assertEqual({PAINT: True},
                         self._post(target_states='{"\u00b2": true, "4244": true}'))
        self.assertIsNone(self._post())
