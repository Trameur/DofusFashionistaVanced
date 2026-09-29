# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solver earns a piece's spell-modifier value only when it wears it at the AP it is priced for."""

import copy

import pulp
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import fashion_action
from chardata.coaching_view import create_build
from chardata.stats_weights import get_stats_weights
from chardata.tests_a_touch_build_saved_before_the_seals_still_loads import _OPTIONS
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import ModelInput, _stable_digest
from fashionistapulp.model_pool import borrow_model, return_model
from fashionistapulp.structure import get_structure, set_current_game_version

HONOH_RING = 8714
ROBBIE_HOODIE_CAP = 8636
# Forgelance cape, leggings and gloves, priced at 12 AP on a solved balanced earth set
FORGELANCE_PRICES = {27552: {12: 15112}, 27554: {12: 3906}, 27555: {12: 23668}}
FORGELANCE_OVERLAPS = {(27552, 27554): {12: -3906}, (27552, 27555): {12: -2183},
                       (27554, 27555): {12: -3906}}
WEIGHTS = {'vit': 1, 'str': 3, 'ap': 400, 'mp': 300}
PRICE = 1000000.0


def _base():
    base = {name: 0 for name, _key in STATS_NAMES}
    base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100, 'Pods': 1000})
    return base


def _input(char_class, modifier_values=None, minimum=None, overlaps=None):
    return ModelInput(200, _base(), dict(minimum or {}), {}, [], dict(WEIGHTS), dict(_OPTIONS),
                      char_class, 995, [], {}, modifier_values, overlaps)


class _Solve(TestCase):
    version = 'dofus3'

    def setUp(self):
        set_current_game_version(self.version)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.structure = get_structure(self.version)

    def solve(self, char_class, modifier_values=None, minimum=None, overlaps=None):
        model = borrow_model()
        try:
            model.setup(_input(char_class, modifier_values, minimum, overlaps))
            model.run()
            self.assertEqual('Optimal', model.get_solved_status())
            return model.get_result_minimal().item_per_slot
        finally:
            return_model(model)


class AClassItemIsWornAtTheApItPaysTests(_Solve):

    def setUp(self):
        super().setUp()
        self.ring = self.structure.get_item_by_ankama_id(HONOH_RING)

    def test_the_ring_priced_at_the_ap_the_set_reaches_is_worn(self):
        worn = self.solve('Cra', {self.ring.id: {12: PRICE}}, {'AP': 12})
        self.assertIn(self.ring.id, worn.values())

    def test_the_ring_priced_only_below_the_ap_floor_is_not_worn(self):
        worn = self.solve('Cra', {self.ring.id: {7: PRICE}}, {'AP': 12})
        self.assertNotIn(self.ring.id, worn.values())


class TwoOverlappingPiecesAreNotPaidTwiceTests(_Solve):

    def setUp(self):
        super().setUp()
        self.ring = self.structure.get_item_by_ankama_id(HONOH_RING).id
        self.cap = self.structure.get_item_by_ankama_id(ROBBIE_HOODIE_CAP).id
        self.priced = {self.ring: {12: PRICE}, self.cap: {12: PRICE}}

    def test_two_priced_pieces_are_both_worn(self):
        worn = set(self.solve('Cra', self.priced, {'AP': 12}).values())
        self.assertLessEqual({self.ring, self.cap}, worn)

    def test_pieces_whose_pair_loses_most_of_their_value_are_not_both_worn(self):
        overlap = {(self.ring, self.cap): {12: -1.5 * PRICE}}
        worn = set(self.solve('Cra', self.priced, {'AP': 12}, overlap).values())
        self.assertEqual(1, len({self.ring, self.cap} & worn))


class ASealIsWornWhenPricedForItsClassTests(_Solve):
    version = 'touch'

    def setUp(self):
        super().setUp()
        self.power = self.structure.get_item_by_name('Iop Seal: Power')
        self.heroism = self.structure.get_item_by_name('Feca Seal: Heroism')

    def emblems(self, worn):
        return {worn.get('emblem1'), worn.get('emblem2')} - {None}

    def test_an_iop_wears_its_priced_seal_in_an_emblem_slot(self):
        worn = self.solve('Iop', {self.power.id: {ap: PRICE for ap in range(7, 13)}})
        self.assertEqual({self.power.id}, self.emblems(worn))

    def test_an_unpriced_seal_stays_out_as_before(self):
        self.assertEqual(set(), self.emblems(self.solve('Iop')))

    def test_a_seal_of_another_class_is_not_worn_even_when_priced(self):
        worn = self.solve('Iop', {self.heroism.id: {ap: PRICE for ap in range(7, 13)}})
        self.assertNotIn(self.heroism.id, worn.values())


class ThePooledModelGoesBackToItsColumnsTests(_Solve):

    def shape(self, model):
        return ([variable.name for variable in model.problem.pulp_lp.variables()],
                sorted(model.problem.pulp_lp.constraints), sorted(model.problem.pulp_vars))

    def test_a_solve_after_a_priced_one_reads_the_same_problem(self):
        ring = self.structure.get_item_by_ankama_id(HONOH_RING)
        model = borrow_model()
        try:
            model.setup(_input('Cra'))
            before = self.shape(model)
            cap = self.structure.get_item_by_ankama_id(ROBBIE_HOODIE_CAP)
            model.setup(_input('Cra', {ring.id: {11: 50.0, 12: 20.0}, cap.id: {12: 10.0}},
                               overlaps={(ring.id, cap.id): {12: -5.0}}))
            priced = self.shape(model)
            model.setup(_input('Cra'))
            after = self.shape(model)
        finally:
            return_model(model)
        self.assertEqual(before, after)
        self.assertEqual(len(before[0]) + 2 + 3 + 1, len(priced[0]))
        self.assertIn('modpick_%d_12' % ring.id, priced[0])
        self.assertIn('modboth_%d_%d_12' % (ring.id, cap.id), priced[0])


class AnInputWithoutValuesKeepsItsKeyTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')

    def test_no_values_digest_the_parts_they_always_did(self):
        plain = _input('Cra')
        self.assertEqual(_stable_digest([
            'dofus3', 200, plain.base_stats_by_attr, {}, None, {}, [], plain.objective_values,
            plain.options, 'Cra', 995, [], {}]), plain.cache_key())
        self.assertEqual(plain.cache_key(), _input('Cra', {}).cache_key())
        self.assertEqual(hash(plain), hash(_input('Cra', {})))

    def test_values_make_another_key(self):
        priced = _input('Cra', {5: {12: 10.0}, 6: {12: 3.0}})
        self.assertNotEqual(_input('Cra').cache_key(), priced.cache_key())
        self.assertNotEqual(hash(_input('Cra')), hash(priced))
        self.assertNotEqual(priced.cache_key(),
                            _input('Cra', {5: {12: 11.0}, 6: {12: 3.0}}).cache_key())
        overlapping = _input('Cra', {5: {12: 10.0}, 6: {12: 3.0}}, overlaps={(5, 6): {12: -2.0}})
        self.assertNotEqual(priced.cache_key(), overlapping.cache_key())
        self.assertNotEqual(hash(priced), hash(overlapping))


class APricedSolveNeverScoresBelowTheUnpricedOneTests(_Solve):

    def objective(self, model_input):
        model = borrow_model()
        try:
            model.setup(model_input)
            model.run()
            self.assertEqual('Optimal', model.get_solved_status())
            self.assertTrue(model.solution_is_proven())
            return pulp.value(model.problem.pulp_lp.objective)
        finally:
            return_model(model)

    def test_a_forgelance_keeps_at_least_its_unpriced_optimum(self):
        request = RequestFactory().get('/')
        request.user = User.objects.create_user('priced', 'priced@test.local', 'pw-42-solid')
        char = create_build(request, 'Forgelance', 200, {'str'}, 'dofus3')
        plain = fashion_action._model_input(request, char, get_stats_weights(char))
        priced = copy.copy(plain)
        priced.modifier_values = {self.structure.get_item_by_ankama_id(ankama_id).id: per_ap
                                  for ankama_id, per_ap in FORGELANCE_PRICES.items()}
        priced.modifier_overlaps = {
            tuple(self.structure.get_item_by_ankama_id(ankama_id).id for ankama_id in pair):
            per_ap for pair, per_ap in FORGELANCE_OVERLAPS.items()}
        self.assertGreaterEqual(self.objective(priced), self.objective(plain) - 1e-6)
