# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The E1a gate counts the cells the blind gate lets run: a blind class keeps the engine whatever the tuner finds."""
from django.test import SimpleTestCase

from chardata import weight_tuning as tuning


def _entry(first=1.4, second=1.5, engine=1.0):
    return {'folds': [first, second], 'engine': engine}


def _live(gained=True, reason=None, converged=4, total=4, ratios=None, notes=()):
    """The record of a cell that ran: it gained at both ends of lambda on its dev median and on its test, or not."""
    record = {'cell': 'Iop/str/glasscannon/200', 'status': 'shipped' if gained else 'engine', 'reason': reason,
              'blind_share': 0.9, 'instances': [{'converged': index < converged} for index in range(total)],
              'ratios': {'pow': _entry(), 'hp': _entry()} if ratios is None else ratios, 'notes': list(notes)}
    if gained:
        record.update(u_acc_gain={'lo': 0.03, 'hi': 0.03}, test_gain={'lo': 0.02, 'hi': 0.04})
    return record


def _blind(share=None):
    return {'cell': 'Osamodas/cha/glasscannon/200', 'status': 'engine', 'reason': 'blind', 'blind_share': share}


def _eight(gaining, blind=3):
    """The eight cells of E1a: `blind` classes the blind gate keeps out and the others, `gaining` of which gain."""
    live = 8 - blind
    return [_blind() for _ in range(blind)] + [_live(index < gaining) for index in range(live)]


class TheGateIsReadOnTheLiveCellsTests(SimpleTestCase):

    def test_the_thresholds_are_the_specs(self):
        self.assertEqual((0.70, 0.75, 1), (tuning.E1A_CONVERGED, tuning.E1A_FOLDS_AGREE, tuning.E1A_CEILING_CELLS))

    def test_five_live_cells_that_gain_pass_beside_three_blind_ones(self):
        verdict = tuning.e1a_verdict(_eight(5))
        self.assertEqual((5, 3, 5, 4), (verdict['live'], verdict['blind'], verdict['gained'], verdict['needed']))
        self.assertTrue(all(verdict['checks'].values()), verdict['checks'])
        self.assertTrue(verdict['passed'])

    def test_seven_of_eight_cannot_be_met_when_three_of_them_are_blind(self):
        verdict = tuning.e1a_verdict(_eight(5))
        self.assertLess(verdict['gained'], 7)

    def test_all_but_one_of_the_live_cells_must_gain(self):
        self.assertTrue(tuning.e1a_verdict(_eight(4))['passed'])
        failing = tuning.e1a_verdict(_eight(3))
        self.assertFalse(failing['passed'])
        self.assertFalse(failing['checks']['gains'])

    def test_with_every_class_live_it_is_seven_of_eight(self):
        self.assertTrue(tuning.e1a_verdict(_eight(7, blind=0))['passed'])
        self.assertFalse(tuning.e1a_verdict(_eight(6, blind=0))['passed'])

    def test_a_single_live_cell_has_to_gain(self):
        self.assertTrue(tuning.e1a_verdict([_live()])['passed'])
        self.assertFalse(tuning.e1a_verdict([_live(gained=False)])['passed'])

    def test_no_live_cell_fails_the_gate(self):
        verdict = tuning.e1a_verdict([_blind(), _blind(0.5)])
        self.assertFalse(verdict['checks']['live'])
        self.assertFalse(verdict['passed'])

    def test_a_cell_gains_only_when_the_dev_median_and_the_test_gain_at_both_ends(self):
        for name, change in (('dev lo', {'u_acc_gain': {'lo': 0.0, 'hi': 0.03}}),
                             ('dev hi', {'u_acc_gain': {'lo': 0.03, 'hi': -0.01}}),
                             ('test lo', {'test_gain': {'lo': -0.001, 'hi': 0.03}}),
                             ('test hi', {'test_gain': {'lo': 0.03, 'hi': None}}),
                             ('no dev gain read', {'u_acc_gain': None}),
                             ('no test gain read', {'test_gain': None})):
            with self.subTest(name):
                self.assertFalse(tuning._cell_gained(dict(_live(), **change)))
        self.assertTrue(tuning._cell_gained(_live()))

    def test_a_cell_that_gained_but_failed_a_later_check_still_counts_as_a_gain(self):
        self.assertTrue(tuning._cell_gained(dict(_live(), status='engine', reason='ceiling')))


class TheBlindCellsMustKeepTheEngineTests(SimpleTestCase):

    def test_a_blind_cell_that_ran_fails_the_gate(self):
        ran = dict(_blind(), instances=[{'converged': True}])
        self.assertFalse(tuning.e1a_verdict([ran, _live()])['checks']['blind'])

    def test_a_blind_cell_that_shipped_fails_the_gate(self):
        shipped = dict(_blind(), status='shipped')
        self.assertFalse(tuning.e1a_verdict([shipped, _live()])['checks']['blind'])

    def test_a_live_cell_the_blind_gate_could_not_vouch_for_fails_the_gate(self):
        for share in (None, 0.5):
            with self.subTest(share=share):
                self.assertFalse(tuning.e1a_verdict([dict(_live(), blind_share=share)])['checks']['blind'])


class TheOtherCountsTests(SimpleTestCase):

    def test_seven_in_ten_instances_have_to_converge(self):
        records = [_live(converged=7, total=10)]
        self.assertTrue(tuning.e1a_verdict(records)['checks']['converged'])
        self.assertFalse(tuning.e1a_verdict([_live(converged=6, total=10)])['checks']['converged'])

    def test_the_instances_of_a_blind_cell_do_not_count(self):
        records = _eight(5) + [dict(_blind(), instances=[{'converged': False}] * 40)]
        self.assertTrue(tuning.e1a_verdict(records)['checks']['converged'])

    def test_three_in_four_fold_pairs_have_to_agree(self):
        agree = _entry(1.4, 1.5)
        disagree = _entry(1.2, 2.0)
        three = {'a': agree, 'b': agree, 'c': agree, 'd': disagree}
        two = {'a': agree, 'b': agree, 'd': disagree, 'e': disagree}
        self.assertTrue(tuning.e1a_verdict([_live(ratios=three)])['checks']['folds'])
        self.assertFalse(tuning.e1a_verdict([_live(ratios=two)])['checks']['folds'])

    def test_a_stat_both_folds_weigh_at_zero_is_no_pair(self):
        ratios = {'pow': _entry(1.4, 1.5), 'neutdam': _entry(0.0, 0.0, 0.0), 'earthdam': _entry(0.0, 0.0, 0.0)}
        verdict = tuning.e1a_verdict([_live(ratios=ratios)])
        self.assertEqual(1.0, verdict['folds_agree'])

    def test_a_fold_with_no_run_is_a_pair_that_disagrees(self):
        ratios = {'pow': _entry(None, None), 'hp': _entry(1.4, 1.5)}
        self.assertEqual(0.5, tuning.e1a_verdict([_live(ratios=ratios)])['folds_agree'])

    def test_the_ceiling_may_be_breached_in_one_cell_only(self):
        self.assertTrue(tuning.e1a_verdict(_eight(4) + [_live(False, 'ceiling')])['checks']['ceiling'])
        self.assertFalse(tuning.e1a_verdict(_eight(4) + [_live(False, 'ceiling')] * 2)['checks']['ceiling'])

    def test_the_cells_whose_folds_shared_a_set_are_reported(self):
        records = _eight(5) + [_live(notes=['repeated_dev_sets'])]
        self.assertEqual(1, tuning.e1a_verdict(records)['repeated_sets'])
        self.assertEqual(0, tuning.e1a_verdict(_eight(5))['repeated_sets'])
