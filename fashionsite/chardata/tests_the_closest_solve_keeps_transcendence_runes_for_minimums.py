# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The closest solve keeps the transcendence runes a minimum needs, through the shortfall and the tie break."""

import time
from types import SimpleNamespace
from unittest import mock

from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import runes_by_stat

from chardata import fashion_action
from chardata.dracorune_fixtures import (NOT_ASKED, VERSION, BetaModelTestCase, SmallModel,
                                         element_move, piece)
from chardata.transcendence_fixtures import trans_columns, trans_input


class AMinimumOnlyATranscendenceRuneReachesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.rune = runes_by_stat(load_runes(VERSION))['init'][0]
        source, _target = element_move()
        self.hat = piece('Hat', {source: 50, 'vit': 100})
        self.amulet = piece('Amulet', {source: 50, 'vit': 300})
        self.minimums = {'Initiative': int(self.rune['bonus'])}

    def closest(self, allowed, dracorunes=None):
        model_input = trans_input({'vit': 1}, allowed, dracorunes, self.minimums)
        built = []

        def small_model(**_kwargs):
            built.append(SmallModel([self.hat, self.amulet]))
            return built[-1]

        with mock.patch.object(fashion_action, 'Model', side_effect=small_model), \
                mock.patch.dict(fashion_action._BUILD_SECONDS, {}, clear=True):
            found = fashion_action._closest_solve(SimpleNamespace(id=0), model_input, 'proof',
                                                  time.monotonic() + 600)
        self.assertEqual(1, len(built))
        self.assertEqual('found', found['state'])
        return found, built[-1]

    def test_one_rune_closes_the_shortfall(self):
        for dracorunes in (None, 1):
            with self.subTest(dracorunes=dracorunes):
                found, model = self.closest(1, dracorunes)
                self.assertEqual(bool(dracorunes), bool(model.dracorune_columns))
                self.assertAlmostEqual(0, found['shortfall'])
                self.assertTrue(found['meets_all'])
                stat_of = {rune['id']: rune['stat_key'] for rune in load_runes(VERSION)}
                self.assertEqual(['init'], [stat_of[rune_id]
                                           for _number, rune_id in model.chosen_transcendences()])

    def test_without_the_option_the_minimum_stays_short(self):
        for allowed in (NOT_ASKED, 0):
            with self.subTest(allowed=allowed):
                found, model = self.closest(allowed)
                self.assertGreater(found['shortfall'], 0)
                self.assertFalse(found['meets_all'])
                self.assertEqual([], model.chosen_transcendences())
                self.assertEqual([], trans_columns(model))

    def test_every_closest_step_keeps_the_rune_columns(self):
        for dracorunes in (None, 1):
            with self.subTest(dracorunes=dracorunes):
                model = SmallModel([self.hat, self.amulet])
                model_input = trans_input({'vit': 1}, 1, dracorunes, self.minimums)
                model.setup(model_input)
                self.assertEqual(bool(dracorunes), bool(model.dracorune_columns))
                before = trans_columns(model)
                self.assertTrue(before)
                shortfalls = model.add_elastic_minimums(model_input.minimum_stats,
                                                        model_input.char_level)
                self.assertEqual(before, trans_columns(model))
                model.minimise_shortfall(shortfalls)
                self.assertEqual(before, trans_columns(model))
                model.run(0, change_of=True)
                self.assertEqual(before, trans_columns(model))
                model.hold_shortfall(shortfalls, model.get_shortfall(shortfalls))
                self.assertEqual(before, trans_columns(model))
