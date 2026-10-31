from django.test import SimpleTestCase

from fashionistapulp import wakfu_sublimations
from chardata.wakfu_invented_sublimation_model import ALPHA, block, state, use_block

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None

SUBLIMATION = wakfu_sublimations.SUBLIMATION
TWO_HANDED = state(
    lines=[('B', 'mp', -2, 0, (0, 1)), ('B', 'ap', 2, 0, (0, 1))],
    conditions=[('HasWeaponType', None, '==', (101, 111)), ('GetCharac', 'ap', '<=', 12)])
NO_HEAVY = state(shares=[('B', 'dmg_in_percent', 0, 25, (0,))],
                 conditions=[('HasWeaponType', None, '!=', (101, 112))])


class AWeaponConditionReadsEveryTypeItNamesTests(SimpleTestCase):
    def lines(self, found, weapons, totals=None, level=200):
        use_block(self, block(states={1: found}, sublimations={10: (1, 1, 'normal', ())}))
        return wakfu_sublimations.fight_lines(
            [(SUBLIMATION, 10)], totals or {}, level, ALPHA, None, weapons)[0]

    def test_any_of_the_listed_types_worn_opens_the_condition(self):
        self.assertEqual({'mp': -2, 'ap': 2}, self.lines(TWO_HANDED, {111}, {'ap': 6}))
        self.assertEqual({'mp': -2, 'ap': 2}, self.lines(TWO_HANDED, {101, 5}, {'ap': 6}))

    def test_a_type_not_listed_leaves_it_closed(self):
        self.assertEqual({}, self.lines(TWO_HANDED, {5}, {'ap': 6}))
        self.assertEqual({}, self.lines(TWO_HANDED, set(), {'ap': 6}))

    def test_the_other_condition_of_the_state_still_counts(self):
        self.assertEqual({}, self.lines(TWO_HANDED, {111}, {'ap': 13}))

    def test_a_negated_weapon_condition_holds_when_none_of_the_types_is_worn(self):
        self.assertEqual({'dmg_in_percent': 50}, self.lines(NO_HEAVY, {5}))
        self.assertEqual({'dmg_in_percent': 50}, self.lines(NO_HEAVY, set()))
        self.assertEqual({}, self.lines(NO_HEAVY, {112}))


class TheLiveBlockCountsTheActionPointsOfTheStartOfTheFightTests(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def test_a_passive_that_takes_power_away_at_the_start_is_a_counted_line(self):
        patience = next(found for found in live.PASSIVES.values() if found['name'] == 'Patience')
        self.assertIn(('A', 'wp', -2, 0, ()), [tuple(line) for line in patience['lines']])

    def test_a_shield_gives_a_point_of_movement_only_with_a_shield_worn(self):
        shield = next(ident for ident, found in live.STATES.items()
                      if found['name'] == 'Wield type: Shield')
        item = next(ident for ident, row in live.SUBLIMATIONS.items() if row[0] == shield)
        shield_type = live.STATES[shield]['conditions'][0][3][0]
        worn = wakfu_sublimations.fight_lines([(SUBLIMATION, item)], {}, 245, 1, None,
                                              {shield_type})[0]
        self.assertEqual({'mp': 1}, worn)
        self.assertEqual({}, wakfu_sublimations.fight_lines(
            [(SUBLIMATION, item)], {}, 245, 1, None, set())[0])
