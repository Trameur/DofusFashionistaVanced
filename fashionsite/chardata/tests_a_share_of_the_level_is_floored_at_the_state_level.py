from django.test import SimpleTestCase

from fashionistapulp import wakfu_sublimations
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, LEVEL, SublimationModelCase, block, state, use_block)

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None

SUBLIMATION = wakfu_sublimations.SUBLIMATION


def entry(shares, conditions=()):
    return {'name': 'Share', 'breed': ALPHA, 'unlock': 1, 'family': 'A', 'lines': [],
            'shares': shares, 'conditions': list(conditions), 'conversions': [],
            'uncounted': []}


class AShareOfTheLevelIsFlooredTests(SimpleTestCase):
    def lines(self, level, state_level, shares=None, totals=None, conditions=()):
        shares = shares or [('A', 'melee_dmg', 0, 5, ())]
        use_block(self, block(states={1: state(shares=shares, conditions=conditions, cap=6)},
                              sublimations={10: (1, state_level, 'normal', ())}))
        return wakfu_sublimations.fight_lines(
            [(SUBLIMATION, 10)], totals or {}, level, ALPHA)[0]

    def test_five_percent_a_level_of_a_level_245_character_keeps_the_whole_part(self):
        self.assertEqual({'melee_dmg': 36}, self.lines(245, 3))

    def test_a_half_is_dropped_not_rounded_up(self):
        self.assertEqual({'melee_dmg': 34}, self.lines(230, 3))

    def test_a_whole_share_is_exact(self):
        self.assertEqual({'melee_dmg': 8}, self.lines(80, 2))

    def test_a_share_with_no_state_level_term_is_the_same_at_every_level(self):
        shares = [('A', 'dodge', 150, 0, ())]
        self.assertEqual(self.lines(200, 1, shares), self.lines(200, 3, shares))
        self.assertEqual({'dodge': 300}, self.lines(200, 1, shares))

    def test_a_negative_share_takes_from_the_total(self):
        self.assertEqual({'tackle': -20}, self.lines(200, 1, [('A', 'tackle', -10, 0, ())]))

    def test_a_share_behind_a_condition_that_fails_gives_nothing(self):
        shares = [('B', 'dodge', 100, 0, (0,))]
        conditions = [('GetCharac', 'ap', '<=', 12)]
        self.assertEqual({'dodge': 200}, self.lines(200, 1, shares, {'ap': 12}, conditions))
        self.assertEqual({}, self.lines(200, 1, shares, {'ap': 13}, conditions))


class TheSolvedModelReadsAShareOfTheLevelTests(SublimationModelCase):
    def test_the_set_totals_and_the_objective_agree_on_the_share(self):
        self.invent(passives={1: entry([('A', 'hp', 10, 0, ())])})
        build, worn = self.sublimate({'hp': 1}, sublimations=None, passives='solve')
        self.assertEqual([1], worn.passives)
        self.assertEqual(LEVEL // 10, worn.totals['hp'] - worn.sheet_totals['hp'])
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)


class TheLiveBlockCountsTheMasteryPartOfRavageTests(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def ravage(self):
        return next(found for found in live.STATES.values()
                    if found['shares'] and found['name'] in ('Devastate', 'Ravage'))

    def test_every_mastery_it_names_is_a_share_of_the_level_with_no_condition(self):
        found = self.ravage()
        self.assertEqual(
            {'dmg_in_percent', 'melee_dmg', 'ranged_dmg', 'berserk_dmg', 'critical_bonus',
             'backstab_bonus', 'heal_in_percent'}, {line[1] for line in found['shares']})
        self.assertEqual({(0, 5, ())}, {tuple(line[2:]) for line in found['shares']})
        self.assertFalse(found['conditions'])

    def test_the_recomputed_effect_is_no_longer_left_uncounted(self):
        self.assertNotIn(999, {action for _family, action, _reason in self.ravage()['uncounted']})

    def test_every_share_the_block_counts_is_a_family_a_or_b_line(self):
        for ident, found in live.STATES.items():
            self.assertTrue(all(line[0] in 'AB' for line in found['shares']), ident)
