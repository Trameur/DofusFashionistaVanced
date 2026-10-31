import math

from django.test import SimpleTestCase

from fashionistapulp import wakfu_sublimations
from chardata.tests_a_guarded_epic_state_is_read_on_the_sheet_totals import BASE_HP, WEIGHTS
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, LEVEL, SublimationModelCase, block, use_block)

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None


def passive(conversions):
    return {'name': 'Share', 'breed': ALPHA, 'unlock': 1, 'family': 'C', 'lines': [],
            'conditions': [], 'conversions': conversions, 'uncounted': []}


class ACapStopsAConversionAtAShareOfTheLevelTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block(passives={1: passive([('dodge', 'ranged_dmg', 0.5, 0, 1, (), 2)])}))

    def lines(self, dodge, level):
        return wakfu_sublimations.fight_lines(
            [(wakfu_sublimations.PASSIVE, 1)], {'dodge': dodge}, level, ALPHA)[0]

    def test_a_share_under_the_cap_is_floored_and_the_source_is_kept(self):
        self.assertEqual({'ranged_dmg': 50}, self.lines(101, 155))

    def test_a_share_over_the_cap_is_cut_to_the_cap(self):
        self.assertEqual({'ranged_dmg': 310}, self.lines(926, 155))

    def test_a_share_equal_to_the_cap_is_kept(self):
        self.assertEqual({'ranged_dmg': 490}, self.lines(981, 245))

    def test_a_negative_source_moves_nothing(self):
        self.assertEqual({}, self.lines(-40, 155))


class TheSolvedModelHonoursTheCapTests(SublimationModelCase):
    def solved(self, cap):
        passives = {1: passive([('hp', 'ferocity', 0.5, 0, 1, (), cap)])}
        use_block(self, block(passives=passives))
        build, worn = self.sublimate(WEIGHTS, sublimations=None, passives='solve')
        return build, worn, worn.totals['ferocity'] - worn.sheet_totals['ferocity']

    def test_a_cap_under_the_share_is_what_the_model_moves(self):
        build, worn, gain = self.solved(0.5)
        self.assertEqual([1], worn.passives)
        self.assertEqual(math.floor(0.5 * LEVEL), gain)
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)

    def test_a_cap_over_the_share_leaves_the_floor_of_the_share(self):
        build, worn, gain = self.solved(1000)
        self.assertEqual(math.floor((worn.sheet_totals['hp'] + BASE_HP) * 0.5), gain)
        self.assertLess(gain, 1000 * LEVEL)
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)


class TheLiveBlockCapsTheShareOfAStatAddedToAnotherTests(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def capped(self):
        return {ident: entry for ident, entry in live.PASSIVES.items()
                if any(len(conversion) > 6 for conversion in entry['conversions'])}

    def test_the_two_passives_that_add_half_of_a_stat_to_a_mastery_are_counted(self):
        found = {(entry['name'], conversion[0], conversion[1], conversion[2], conversion[6])
                 for entry in self.capped().values() for conversion in entry['conversions']}
        self.assertEqual(
            {('Artful Dodger', 'dodge', 'ranged_dmg', 0.5, 2),
             ('Artful Locker', 'tackle', 'melee_dmg', 0.5, 2)}, found)
        for entry in self.capped().values():
            self.assertEqual([], entry['uncounted'])

    def test_a_capped_conversion_is_cut_at_its_share_of_the_level(self):
        for ident in self.capped():
            source = live.PASSIVES[ident]['conversions'][0][0]
            target = live.PASSIVES[ident]['conversions'][0][1]
            for level, have in ((155, 926), (245, 981), (245, 100)):
                with self.subTest(passive=ident, level=level):
                    lines, _reports = wakfu_sublimations.fight_lines(
                        [(wakfu_sublimations.PASSIVE, ident)], {source: have}, level, None)
                    self.assertEqual({target: min(have // 2, 2 * level)}, lines)
