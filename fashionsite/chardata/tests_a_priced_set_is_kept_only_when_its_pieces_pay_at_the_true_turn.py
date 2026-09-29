# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A priced set replaces the unpriced set of the same input only when both are proven and its priced pieces add their credit to the panel's best turn."""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from chardata import fashion_action
from chardata import spell_modifier_values as values
from chardata.char_blobs import read_char_blob
from chardata.tests_a_priority_keeps_the_safeguard_share_of_the_balanced_build import (
    _answer, _BuildMixin)
from chardata.tests_a_spell_modifier_piece_is_priced_by_its_best_turn_gain import (
    CRA_SET, CRA_WEIGHTS, HONOH_RING, _Solution, _turn)
from fashionistapulp.model import EFFECTIVE_HP_MINIMUM
from fashionistapulp.structure import get_structure, set_current_game_version

PRICED = {1: {12: 500}}


class ThePanelDecidesWhetherAPricedPieceIsKeptTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('dofus3')
        self.ring = get_structure('dofus3').get_item_by_ankama_id(HONOH_RING).id
        self.char = SimpleNamespace(char_class='Cra', level=200)
        self.reference = _Solution(CRA_SET)

    def priced(self, factor=1):
        priced, overlaps = values.modifier_values('dofus3', 'Cra', 200, CRA_WEIGHTS, CRA_SET)
        return SimpleNamespace(char_class='Cra', char_level=200, objective_values=CRA_WEIGHTS,
                               options={}, modifier_overlaps=overlaps,
                               modifier_values={item_id: {ap: value * factor
                                                          for ap, value in per_ap.items()}
                                                for item_id, per_ap in priced.items()})

    def test_the_true_gain_is_the_panel_turn_less_the_same_set_without_the_piece_modifiers(self):
        self.assertEqual(_turn('Cra', CRA_SET, HONOH_RING) - _turn('Cra', CRA_SET),
                         values.true_gain(self.char, _Solution(CRA_SET, HONOH_RING), 'dofus3',
                                          {self.ring}))

    def test_a_piece_whose_panel_gain_covers_its_credit_pays(self):
        self.assertTrue(values.pays_at_the_true_turn(
            self.char, self.priced(), _Solution(CRA_SET, HONOH_RING), self.reference))

    def test_a_credit_twice_the_panel_gain_does_not_pay(self):
        self.assertFalse(values.pays_at_the_true_turn(
            self.char, self.priced(2), _Solution(CRA_SET, HONOH_RING), self.reference))

    def test_a_set_wearing_no_priced_piece_does_not_replace_the_unpriced_one(self):
        self.assertFalse(values.pays_at_the_true_turn(
            self.char, self.priced(), _Solution(CRA_SET), self.reference))


class TheCreditIsWhatTheSolverCountsTests(SimpleTestCase):

    def test_a_piece_counts_at_the_ap_reached_and_a_pair_only_when_both_are_worn(self):
        priced = {1: {11: 30, 12: 50}, 2: {12: 40}, 3: {12: 7}}
        overlaps = {(1, 2): {12: -20}, (1, 3): {12: -5}}
        self.assertEqual(50 + 40 - 20, values.credited(priced, overlaps, {1, 2, 9}, 12))
        self.assertEqual(30, values.credited(priced, overlaps, {1, 2}, 11))
        self.assertEqual(0, values.credited(priced, overlaps, {9}, 12))


def _hats(version):
    structure = get_structure(version)
    vitality = structure.get_stat_by_key('vit').id
    hats = sorted(structure.get_unique_items_by_type_and_level('Hat', 200),
                  key=lambda item: (dict(item.stats).get(vitality, 0), item.id))
    return hats[0], hats[-1]


class _Flow(_BuildMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.plain_hat, self.priced_hat = _hats(self.version)

    def rule(self, proven=True, priced_proven=True):
        def answer(model_input):
            if model_input.modifier_values:
                return _answer(model_input, {'hat': self.priced_hat.id}, priced_proven)
            return _answer(model_input, {'hat': self.plain_hat.id}, proven)
        return answer

    def fashion(self, char, rule, pays=True):
        references = []

        def priced(game_version, char_class, level, weights, stats, temporix=False, weapon=None):
            references.append(stats)
            return dict(PRICED), {}
        with mock.patch('chardata.fashion_action.modifier_values', side_effect=priced), \
                mock.patch('chardata.fashion_action.pays_at_the_true_turn',
                           return_value=pays) as checked:
            asked, _response = self.solve(char, rule)
        return asked, references, checked, self.worn_hat(char)

    def worn_hat(self, char):
        worn = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        return worn.item_per_slot.get('hat')

    def stats_of(self, char, model_input, hat):
        return dict(fashion_action._solution_of(
            char, _answer(model_input, {'hat': hat.id})[2]).get_stats_total())


class WithoutTheSettingNoSetIsPricedTests(_Flow):

    def test_a_build_is_solved_once_and_wears_the_unpriced_set(self):
        asked, references, checked, hat = self.fashion(self.build({'str'}), self.rule())
        self.assertEqual(1, len(asked))
        self.assertEqual([], references)
        self.assertEqual(0, checked.call_count)
        self.assertEqual(self.plain_hat.id, hat)


@override_settings(PRICE_SPELL_MODIFIERS=True)
class APricedSetIsKeptOnlyWhenItPaysTests(_Flow):

    def test_a_priced_set_that_pays_is_kept(self):
        asked, _references, checked, hat = self.fashion(self.build({'str'}), self.rule())
        self.assertEqual([{}, PRICED], [model_input.modifier_values for model_input in asked])
        self.assertEqual(1, checked.call_count)
        self.assertEqual(self.priced_hat.id, hat)

    def test_a_priced_set_that_does_not_pay_gives_way_to_the_unpriced_one(self):
        _asked, _references, _checked, hat = self.fashion(self.build({'str'}), self.rule(),
                                                          pays=False)
        self.assertEqual(self.plain_hat.id, hat)

    def test_an_unproven_priced_set_gives_way_to_the_proven_unpriced_one(self):
        _asked, _references, checked, hat = self.fashion(
            self.build({'str'}), self.rule(priced_proven=False))
        self.assertEqual(0, checked.call_count)
        self.assertEqual(self.plain_hat.id, hat)

    def test_an_unproven_unpriced_set_is_not_priced(self):
        asked, references, _checked, hat = self.fashion(self.build({'str'}),
                                                        self.rule(proven=False))
        self.assertEqual(1, len(asked))
        self.assertEqual([], references)
        self.assertEqual(self.plain_hat.id, hat)

    def test_a_check_that_fails_keeps_the_unpriced_set(self):
        char = self.build({'str'})
        with mock.patch('chardata.fashion_action.pays_at_the_true_turn',
                        side_effect=RuntimeError('panel')), \
                mock.patch('chardata.fashion_action.modifier_values',
                           return_value=(dict(PRICED), {})), \
                self.assertLogs('chardata.fashion_action', 'ERROR'):
            self.solve(char, self.rule())
        self.assertEqual(self.plain_hat.id, self.worn_hat(char))

    def test_a_pricing_that_fails_keeps_the_unpriced_set(self):
        char = self.build({'str'})
        with mock.patch('chardata.fashion_action.modifier_values',
                        side_effect=RuntimeError('pricing')), \
                self.assertLogs('chardata.fashion_action', 'ERROR'):
            asked, _response = self.solve(char, self.rule())
        self.assertEqual(1, len(asked))
        self.assertEqual(self.plain_hat.id, self.worn_hat(char))


@override_settings(PRICE_SPELL_MODIFIERS=True)
class ThePiecesArePricedOnTheUnpricedSetOfTheSameInputTests(_Flow):

    def test_the_set_the_build_wore_before_plays_no_part(self):
        char = self.build({'str'})
        with override_settings(PRICE_SPELL_MODIFIERS=False):
            self.solve(char, lambda model_input: _answer(model_input,
                                                         {'hat': self.priced_hat.id}))
        self.assertEqual(self.priced_hat.id, self.worn_hat(char))
        asked, first, _checked, _hat = self.fashion(char, self.rule(), pays=False)
        _asked, second, _checked, _hat = self.fashion(char, self.rule(), pays=False)
        self.assertEqual([self.stats_of(char, asked[0], self.plain_hat)], first)
        self.assertNotEqual(self.stats_of(char, asked[0], self.priced_hat), first[0])
        self.assertEqual(first, second)

    def test_a_guarded_solve_is_priced_on_its_own_guarded_set(self):
        char = self.build({'str'}, 'damage')

        def answer(model_input):
            if model_input.modifier_values or EFFECTIVE_HP_MINIMUM in model_input.minimum_stats:
                return self.rule()(model_input)
            return _answer(model_input, {'hat': self.priced_hat.id})
        asked, references, _checked, hat = self.fashion(char, answer, pays=False)
        self.assertEqual(3, len(asked))
        self.assertNotIn(EFFECTIVE_HP_MINIMUM, asked[0].minimum_stats)
        self.assertEqual({}, asked[1].modifier_values)
        self.assertIn(EFFECTIVE_HP_MINIMUM, asked[2].minimum_stats)
        self.assertEqual(PRICED, asked[2].modifier_values)
        self.assertEqual([self.stats_of(char, asked[1], self.plain_hat)], references)
        self.assertEqual(self.plain_hat.id, hat)
