# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solver dresses a build only in pieces its class, level and other pieces let it wear."""

from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version

OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
           'dofus': True, 'trophies': True, 'dragoturkey': True,
           'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
           'shields': True}


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


class _Solve(SimpleTestCase):
    version = 'dofus3'

    def setUp(self):
        if not _solver_available():
            self.skipTest('no pulp solver available')
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(self.version)
        self.structure = get_structure(self.version)

    def piece(self, ankama_id):
        item = self.structure.get_item_by_ankama_id(ankama_id)
        self.assertIsNotNone(item)
        return item

    def model(self, level, weights, char_class='Iop', locked=None, model=None):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7 if level >= 100 else 6, 'MP': 3, 'Summon': 1,
                     'Prospecting': 100, 'Pods': 1000})
        model = model or Model()
        model.setup(ModelInput(level, base, {}, dict(locked or {}), set(),
                               dict(weights), dict(OPTIONS), char_class,
                               5 * (level - 1)))
        return model

    def solve(self, level, weights, char_class='Iop', locked=None):
        model = self.model(level, weights, char_class, locked)
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return model

    def worn(self, model):
        return set(model.get_result_minimal().item_per_slot.values())

    def stat(self, model, name):
        stat_id = self.structure.get_stat_by_name(name).id
        return model.get_search_state()['values'].get('stat_%d' % stat_id, 0)

    @staticmethod
    def right_hand_side(restriction):
        return -restriction.constant


class ATouchClassRingTests(_Solve):
    version = 'touch'
    WEIGHTS = {'cha': 10, 'pp': 3, 'vit': 1}

    def test_the_enutrofion_goes_to_an_enutrof_and_never_to_an_iop(self):
        ring = self.piece(1499)
        self.assertIn(ring.id, self.worn(self.solve(60, self.WEIGHTS, 'Enutrof')))
        self.assertNotIn(ring.id, self.worn(self.solve(60, self.WEIGHTS, 'Iop')))


class ATouchUnusablePieceTests(_Solve):
    version = 'touch'
    WEIGHTS = {'vit': 3, 'range': 150, 'lock': 5, 'heals': 3}

    def test_the_worn_koolich_headgear_is_never_worn(self):
        headgear = self.piece(7887)
        self.assertNotIn(headgear.id, self.worn(self.solve(90, self.WEIGHTS)))

    def test_the_same_weights_pick_it_once_it_is_no_longer_marked(self):
        headgear = self.piece(7887)
        with mock.patch.object(headgear, 'unusable', False):
            self.assertIn(headgear.id, self.worn(self.solve(90, self.WEIGHTS)))


class ADofus2OrConditionTests(_Solve):
    version = 'dofus2'
    WEIGHTS = {'ap': 1000, 'mp': 800, 'range': 300, 'neutdam': 20,
               'earthdam': 20, 'firedam': 20, 'waterdam': 20, 'vit': 1}

    def test_professor_xas_ring_is_left_out_of_a_twelve_ap_six_mp_build(self):
        ring = self.piece(12109)
        model = self.solve(200, self.WEIGHTS)
        self.assertEqual((12, 6), (self.stat(model, 'AP'), self.stat(model, 'MP')))
        self.assertNotIn(ring.id, self.worn(model))

    def test_without_its_condition_the_same_solve_wears_it(self):
        ring = self.piece(12109)
        with mock.patch.object(ring, 'or_conditions', []):
            model = self.solve(200, self.WEIGHTS)
        self.assertEqual((12, 6), (self.stat(model, 'AP'), self.stat(model, 'MP')))
        self.assertIn(ring.id, self.worn(model))


class ADofus2PairNotWornTogetherTests(_Solve):
    version = 'dofus2'
    WEIGHTS = {'crires': 20, 'summon': 300, 'mpres': 10, 'vit': 1}
    BLACK_SPOTTED, DOMAKURO, DORIGAMI = 7112, 23237, 23408

    def test_the_black_spotted_dofus_is_never_worn_with_the_two_it_came_from(self):
        pieces = {self.piece(number).id for number
                  in (self.BLACK_SPOTTED, self.DOMAKURO, self.DORIGAMI)}
        worn = self.worn(self.solve(200, self.WEIGHTS))
        self.assertIn(self.piece(self.BLACK_SPOTTED).id, worn)
        self.assertEqual(1, len(worn & pieces))

    def test_without_the_rule_the_same_solve_wears_two_of_them(self):
        items = [self.piece(number) for number
                 in (self.BLACK_SPOTTED, self.DOMAKURO, self.DORIGAMI)]
        patches = [mock.patch.object(item, 'not_worn_with', ()) for item in items]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        worn = self.worn(self.solve(200, self.WEIGHTS))
        self.assertEqual(2, len(worn & {item.id for item in items}))

    def test_two_locked_pieces_of_a_pair_stay_worn(self):
        cruelty, bitterness = self.piece(27547), self.piece(27548)
        model = self.model(200, self.WEIGHTS, locked={'ring1': cruelty.id,
                                                      'ring2': bitterness.id})
        pair = (min(cruelty.id, bitterness.id), max(cruelty.id, bitterness.id))
        self.assertEqual(2, self.right_hand_side(model._not_worn_together[pair]))
        model = self.model(200, self.WEIGHTS, locked={'ring1': cruelty.id}, model=model)
        self.assertEqual(1, self.right_hand_side(model._not_worn_together[pair]))


class AHighestLevelTests(_Solve):
    version = 'dofus3'

    def test_the_pilgrim_staff_is_open_up_to_level_five_and_closed_after(self):
        staff = self.piece(9627)
        self.assertEqual(5, staff.max_level)
        model = None
        for level, allowed in ((1, 1), (5, 1), (6, 0), (200, 0)):
            with self.subTest(level=level):
                model = self.model(level, {'vit': 1}, model=model)
                self.assertEqual(allowed, self.right_hand_side(
                    model.restrictions.level_constraints[staff.id]))

    def test_a_locked_pilgrim_staff_stays_past_level_five(self):
        staff = self.piece(9627)
        model = self.model(6, {'vit': 1}, locked={'weapon': staff.id})
        self.assertEqual(1, self.right_hand_side(
            model.restrictions.level_constraints[staff.id]))


class ATouchLockedUnusablePieceTests(_Solve):
    version = 'touch'
    WEIGHTS = {'vit': 3, 'range': 150, 'lock': 5, 'heals': 3}

    def test_a_locked_worn_koolich_headgear_stays_worn(self):
        headgear = self.piece(7887)
        forbidden = self.model(90, self.WEIGHTS).restrictions.forbidden_items_constraints
        self.assertEqual(0, self.right_hand_side(forbidden[headgear.id]))
        model = self.solve(90, self.WEIGHTS, locked={'hat': headgear.id})
        self.assertEqual(1, self.right_hand_side(
            model.restrictions.forbidden_items_constraints[headgear.id]))
        self.assertIn(headgear.id, self.worn(model))


class ADofus3ExactStatTests(_Solve):
    version = 'dofus3'
    WEIGHTS = {'cha': 10, 'vit': 1}

    def test_a_locked_tatty_bim_bonnet_keeps_chance_at_zero(self):
        bonnet = self.piece(11603)
        model = self.solve(200, self.WEIGHTS, locked={'hat': bonnet.id})
        self.assertIn(bonnet.id, self.worn(model))
        self.assertEqual(0, self.stat(model, 'Chance'))

    def test_without_its_condition_the_same_solve_raises_chance(self):
        bonnet = self.piece(11603)
        with mock.patch.object(bonnet, 'max_stats_to_equip', []):
            model = self.solve(200, self.WEIGHTS, locked={'hat': bonnet.id})
        self.assertIn(bonnet.id, self.worn(model))
        self.assertGreater(self.stat(model, 'Chance'), 0)


class ARetroMpGateTests(_Solve):
    version = 'retro'
    WEIGHTS = {'vit': 1, 'mp': -5000}

    def test_a_locked_sword_hikk_brings_the_build_to_six_mp(self):
        sword = self.piece(8695)
        model = self.solve(200, self.WEIGHTS, locked={'weapon': sword.id})
        self.assertIn(sword.id, self.worn(model))
        self.assertGreaterEqual(self.stat(model, 'MP'), 6)

    def test_without_its_condition_the_same_solve_stays_below_six(self):
        sword = self.piece(8695)
        mp = self.structure.get_stat_by_name('MP').id
        gates = [(stat, value) for stat, value in sword.min_stats_to_equip if stat != mp]
        self.assertLess(len(gates), len(sword.min_stats_to_equip))
        with mock.patch.object(sword, 'min_stats_to_equip', gates):
            model = self.solve(200, self.WEIGHTS, locked={'weapon': sword.id})
        self.assertIn(sword.id, self.worn(model))
        self.assertLess(self.stat(model, 'MP'), 6)


class ARetroClassGateTests(_Solve):
    version = 'retro'

    def open_to(self, ankama_id, classes):
        piece = self.piece(ankama_id)
        model, out = None, {}
        for char_class in classes:
            model = self.model(200, {'vit': 1}, char_class, model=model)
            out[char_class] = self.right_hand_side(
                model.restrictions.forbidden_items_constraints[piece.id])
        return out

    def test_korko_klako_is_open_to_the_sadida_only(self):
        self.assertEqual({'Sadida': 1, 'Iop': 0, 'Cra': 0},
                         self.open_to(710, ('Sadida', 'Iop', 'Cra')))

    def test_a_hat_barred_to_the_sadida_is_open_to_the_others(self):
        self.assertEqual({'Sadida': 0, 'Iop': 1, 'Cra': 1},
                         self.open_to(700, ('Sadida', 'Iop', 'Cra')))

    def test_the_hammer_for_two_classes_is_open_to_both_only(self):
        self.assertEqual({'Osamodas': 1, 'Xelor': 1, 'Iop': 0},
                         self.open_to(7156, ('Osamodas', 'Xelor', 'Iop')))
