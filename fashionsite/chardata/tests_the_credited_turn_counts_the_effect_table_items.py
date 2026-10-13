# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The credited turn is the panel's best turn plus what the worn effect-table items are worth."""
import math
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.weapon_terms import CHARACTERISTIC_STEP
from fashionistapulp.item_effects import CLASS_BOUND_RULES, is_valued, load_effect_table

CHAR = SimpleNamespace(id=1, level=200, game_version='dofus3', char_class='Iop')
WEIGHTS = {'str': 100, 'int': 100, 'cha': 0, 'agi': 20, 'permedam': 10, 'perrandam': 5}
TOTALS = {'pow': 250, 'str': 700, 'int': 650, 'dam': 40, 'hp': 3000, 'ch': 30, 'ap': 12, 'neutresper': 0,
          'earthresper': 0, 'fireresper': 0, 'waterresper': 0, 'airresper': 0}
BASE = 1000.0


def _panel(char, solution):
    """A turn that grows by 2 per power, 3 per strength, 1 per fixed damage, 5 per AP and 0.5 per crit."""
    totals = solution.get_stats_total()
    return (BASE + 2.0 * totals.get('pow', 0) + 3.0 * totals.get('str', 0) + totals.get('dam', 0)
            + 5.0 * totals.get('ap', 0) + 0.5 * totals.get('ch', 0))


def _solution(ids=(), added=True, **totals):
    return SimpleNamespace(item_list=[SimpleNamespace(id=item_id, item_added=added) for item_id in ids],
                           get_stats_total=lambda: dict(TOTALS, **totals), marker='kept')


def _table(**entries):
    """{'items': ...} whose entry `name` is worn as the item whose site id is its position."""
    items = {}
    for position, (name, entry) in enumerate(sorted(entries.items()), 1):
        items[name] = dict({'site_ids': [position], 'status': 'measured', 'rule': 'x'}, **entry)
    return {'items': items}


def _id(table, name):
    return table['items'][name]['site_ids'][0]


def _turn(table, ids, weights=WEIGHTS, **kwargs):
    with mock.patch('chardata.presets._panel_turn', side_effect=_panel):
        return tuning.credited_turn(CHAR, _solution(ids), table, weights, **kwargs)


class WithNothingWornTheCreditedTurnIsThePanelsTests(SimpleTestCase):

    def _same(self, table, ids=(1,), solution=None):
        solution = solution or _solution(ids)
        with mock.patch('chardata.presets._panel_turn', return_value=1234.5) as panel:
            turn = tuning.credited_turn(CHAR, solution, table, WEIGHTS)
        self.assertEqual(1234.5, turn)
        panel.assert_called_once()
        self.assertIs(solution, panel.call_args[0][1])

    def test_no_table_gives_the_panels_turn_on_the_solution_itself(self):
        for table in (None, {}, {'items': {}}):
            with self.subTest(table=table):
                self._same(table)

    def test_an_item_that_is_not_valued_counts_for_nothing(self):
        self._same(_table(a={'equivalents': {}}, b={'equivalents': None}, c={}), ids=(1, 2, 3))

    def test_an_item_that_is_bound_to_a_class_counts_for_nothing(self):
        bound = _table(a={'equivalents': {'pow': 50}, 'rule': sorted(CLASS_BOUND_RULES)[0]})
        self._same(bound)

    def test_an_item_the_set_does_not_wear_counts_for_nothing(self):
        table = _table(a={'equivalents': {'pow': 50}})
        self._same(table, ids=(99,))

    def test_an_item_that_was_not_added_counts_for_nothing(self):
        table = _table(a={'equivalents': {'pow': 50}})
        self._same(table, solution=_solution((1,), added=False))

    def test_equivalents_the_credit_does_not_carry_count_for_nothing(self):
        table = _table(a={'equivalents': {'wis': 100, 'apres': 5, 'lock': 20, 'sets': 3}})
        self._same(table)

    def test_the_real_table_with_a_piece_it_does_not_hold(self):
        table = load_effect_table('dofus3')
        known = {item_id for entry in table['items'].values() for item_id in entry.get('site_ids') or ()}
        self._same(table, ids=(max(known) + 1,))


class AWornItemAddsItsEquivalentsToTheTotalsTests(SimpleTestCase):

    def test_a_stat_of_the_totals_is_raised_by_the_item(self):
        table = _table(a={'equivalents': {'pow': 30}})
        self.assertEqual(_panel(CHAR, _solution(pow=280)), _turn(table, [_id(table, 'a')]))

    def test_every_stat_the_turn_reads_is_credited(self):
        table = _table(a={'equivalents': {'pow': 30, 'dam': 5, 'ap': 1, 'ch': 10, 'str': 20}})
        wanted = _solution(pow=280, dam=45, ap=13, ch=40, str=720)
        self.assertEqual(_panel(CHAR, wanted), _turn(table, [_id(table, 'a')]))

    def test_two_items_add_up(self):
        table = _table(a={'equivalents': {'pow': 30}}, b={'equivalents': {'pow': 12, 'dam': 3}})
        wanted = _solution(pow=292, dam=43)
        self.assertEqual(_panel(CHAR, wanted), _turn(table, [_id(table, 'a'), _id(table, 'b')]))

    def test_a_negative_equivalent_lowers_the_turn(self):
        table = _table(a={'equivalents': {'pow': -30}})
        self.assertEqual(_panel(CHAR, _solution(pow=220)), _turn(table, [_id(table, 'a')]))

    def test_a_cost_only_item_counts_only_what_it_costs(self):
        table = _table(a={'equivalents': {'pow': 30, 'dam': -5}, 'status': 'estimated'})
        self.assertEqual(_panel(CHAR, _solution(dam=35)), _turn(table, [_id(table, 'a')]))

    def test_the_equivalents_by_number_of_elements_replace_the_general_ones(self):
        table = _table(a={'equivalents': {'pow': 30}, 'equivalents_by_elements': {'2': {'pow': 50, 'sets': 4}}})
        self.assertEqual(_panel(CHAR, _solution(pow=300)), _turn(table, [_id(table, 'a')]))
        one_element = dict(WEIGHTS, int=0)
        self.assertEqual(_panel(CHAR, _solution(pow=280)), _turn(table, [_id(table, 'a')], one_element))

    def test_an_explicit_delta_is_added_after_the_items(self):
        table = _table(a={'equivalents': {'pow': 30}})
        self.assertEqual(_panel(CHAR, _solution(pow=300)), _turn(table, [_id(table, 'a')], deltas={'pow': 20}))
        self.assertEqual(_panel(CHAR, _solution(pow=270)), _turn(_table(), [], deltas={'pow': 20}))

    def test_the_proxy_the_panel_reads_delegates_what_it_does_not_change(self):
        proxy = tuning._CreditedSolution(_solution((1,)), {'pow': 5, 'wis': 2})
        self.assertEqual(255, proxy.get_stats_total()['pow'])
        self.assertEqual(2, proxy.get_stats_total()['wis'])
        self.assertEqual('kept', proxy.marker)
        self.assertEqual(1, len(proxy.item_list))


class ThePlayedCharacteristicIsExpandedTests(SimpleTestCase):

    def test_it_is_credited_to_each_played_characteristic(self):
        table = _table(a={'equivalents': {'played_char': 10}})
        extra, final, hp = tuning.worn_equivalents(CHAR, _solution((_id(table, 'a'),)), table, WEIGHTS)
        self.assertEqual(({'str': 10, 'int': 10}, 0, 0), (extra, final, hp))

    def test_a_characteristic_far_below_the_heaviest_is_not_played(self):
        table = _table(a={'equivalents': {'played_char': 10}})
        weights = dict(WEIGHTS, agi=70)
        extra, _final, _hp = tuning.worn_equivalents(CHAR, _solution((_id(table, 'a'),)), table, weights)
        self.assertEqual({'str': 10, 'int': 10, 'agi': 10}, extra)
        weights = dict(WEIGHTS, int=60)
        extra, _final, _hp = tuning.worn_equivalents(CHAR, _solution((_id(table, 'a'),)), table, weights)
        self.assertEqual({'str': 10}, extra)

    def test_the_turn_reads_the_expanded_characteristics(self):
        table = _table(a={'equivalents': {'played_char': 10}})
        self.assertEqual(_panel(CHAR, _solution(str=710, int=660)), _turn(table, [_id(table, 'a')]))


class TheFinalDamageIsAMultiplierOnTheTurnTests(SimpleTestCase):

    def test_a_percent_of_final_damage_multiplies_the_turn(self):
        table = _table(a={'equivalents': {'final': 10}})
        self.assertAlmostEqual(_panel(CHAR, _solution()) * 1.10, _turn(table, [_id(table, 'a')]))

    def test_it_multiplies_the_turn_with_the_other_equivalents_in(self):
        table = _table(a={'equivalents': {'final': 5, 'pow': 30}})
        self.assertAlmostEqual(_panel(CHAR, _solution(pow=280)) * 1.05, _turn(table, [_id(table, 'a')]))

    def test_two_items_add_their_percents(self):
        table = _table(a={'equivalents': {'final': 5}}, b={'equivalents': {'final': 2.5}})
        self.assertAlmostEqual(_panel(CHAR, _solution()) * 1.075, _turn(table, [_id(table, 'a'), _id(table, 'b')]))

    def test_it_is_not_added_to_the_totals(self):
        table = _table(a={'equivalents': {'final': 10}})
        extra, final, _hp = tuning.worn_equivalents(CHAR, _solution((_id(table, 'a'),)), table, WEIGHTS)
        self.assertEqual(({}, 10), (extra, final))

    def test_a_negative_final_lowers_the_turn(self):
        table = _table(a={'equivalents': {'final': -10}})
        self.assertAlmostEqual(_panel(CHAR, _solution()) * 0.90, _turn(table, [_id(table, 'a')]))

    def test_a_turn_of_zero_stays_zero(self):
        table = _table(a={'equivalents': {'final': 10}})
        with mock.patch('chardata.presets._panel_turn', return_value=0):
            self.assertEqual(0, tuning.credited_turn(CHAR, _solution((1,)), table, WEIGHTS))


class TheLifeEquivalentGoesToTheEffectiveHpTests(SimpleTestCase):

    def _parts(self, table, ids, char=CHAR, **totals):
        with mock.patch('chardata.presets._panel_turn', side_effect=_panel), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(WEIGHTS)):
            return tuning.credited_parts(char, _solution(ids, **totals), table)

    def test_hp_is_not_in_the_turn_but_in_the_effective_hp(self):
        table = _table(a={'equivalents': {'hp': 600}})
        credit = self._parts(table, [_id(table, 'a')])
        self.assertEqual(_panel(CHAR, _solution()), credit.turn)
        self.assertAlmostEqual((3000 + 600) / 1.0, credit.ehp)

    def test_hp_is_scaled_by_the_level_over_200(self):
        table = _table(a={'equivalents': {'hp': 600}})
        char = SimpleNamespace(**dict(CHAR.__dict__, level=100))
        credit = self._parts(table, [_id(table, 'a')], char=char)
        self.assertAlmostEqual(3000 + 300, credit.ehp)

    def test_the_effective_hp_counts_the_resistances(self):
        table = _table(a={'equivalents': {'hp': 600}})
        credit = self._parts(table, [_id(table, 'a')], neutresper=20, earthresper=20, fireresper=20,
                             waterresper=20, airresper=20)
        self.assertAlmostEqual(3600 / 0.8, credit.ehp)

    def test_nothing_worn_gives_the_panels_turn_and_the_plain_effective_hp(self):
        credit = self._parts(_table(), [])
        self.assertEqual((_panel(CHAR, _solution()), 3000.0), (credit.turn, credit.ehp))

    def test_a_set_with_no_turn_has_no_credit(self):
        table = _table(a={'equivalents': {'hp': 600}})
        with mock.patch('chardata.presets._panel_turn', return_value=None), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(WEIGHTS)):
            self.assertIsNone(tuning.credited_parts(CHAR, _solution((1,)), table))

    def test_a_set_with_no_life_has_no_credit(self):
        credit = self._parts(_table(), [], hp=0)
        self.assertIsNone(credit)


class TheCreditedScoreTests(SimpleTestCase):

    def test_it_is_the_log_of_the_credited_turn_plus_lambda_times_the_log_of_the_effective_hp(self):
        table = _table(a={'equivalents': {'pow': 30, 'hp': 600}})
        solution = _solution((_id(table, 'a'),))
        with mock.patch('chardata.presets._panel_turn', side_effect=_panel), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(WEIGHTS)):
            score = tuning.credited_score(CHAR, solution, 0.25, table)
        turn = _panel(CHAR, _solution(pow=280))
        self.assertAlmostEqual(math.log(turn) + 0.25 * math.log(3600), score)

    def test_it_is_none_without_a_credited_turn(self):
        with mock.patch('chardata.presets._panel_turn', return_value=0), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(WEIGHTS)):
            self.assertIsNone(tuning.credited_score(CHAR, _solution(), 0.25, _table()))

    def test_the_table_of_the_version_is_the_default(self):
        with mock.patch('chardata.weight_tuning.load_effect_table', return_value=_table()) as loaded, \
                mock.patch('chardata.presets._panel_turn', side_effect=_panel), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(WEIGHTS)):
            tuning.credited_score(CHAR, _solution(), 0.25)
        loaded.assert_called_once_with('dofus3')


class ThePowerShareTests(SimpleTestCase):

    def test_it_is_the_credited_gain_per_point_of_power_times_the_power_worn_over_the_turn(self):
        table = _table(a={'equivalents': {'pow': 30}})
        solution = _solution((_id(table, 'a'),))
        with mock.patch('chardata.presets._panel_turn', side_effect=_panel), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(WEIGHTS)):
            share = tuning.power_share(CHAR, solution, table)
        turn = _panel(CHAR, _solution(pow=280))
        self.assertAlmostEqual(2.0 * 250 / turn, share)

    def test_the_gain_is_read_over_the_step(self):
        self.assertEqual(20, CHARACTERISTIC_STEP)
        self.assertEqual(CHARACTERISTIC_STEP, tuning.STEP)

    def test_it_is_none_without_a_turn(self):
        with mock.patch('chardata.presets._panel_turn', return_value=0), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(WEIGHTS)):
            self.assertIsNone(tuning.power_share(CHAR, _solution(), _table()))


class TheRealTableIsReadTheSameWayTests(SimpleTestCase):

    def test_every_valued_item_gives_equivalents_the_credit_carries(self):
        table = load_effect_table('dofus3')
        valued = [entry for entry in table['items'].values() if is_valued(entry) and entry.get('site_ids')]
        self.assertGreater(len(valued), 0)
        for entry in valued:
            item_id = entry['site_ids'][0]
            extra, final, hp = tuning.worn_equivalents(CHAR, _solution((item_id,)), table, WEIGHTS)
            with self.subTest(item=item_id):
                self.assertLessEqual(set(extra), set(tuning.CREDITED_STATS))
                self.assertNotIn('sets', extra)
                if set(entry['equivalents']) == {'final'}:
                    self.assertEqual(({}, 0), (extra, hp))

    def test_an_item_of_final_damage_alone_is_a_multiplier_on_the_real_table(self):
        table = load_effect_table('dofus3')
        entry = next(entry for entry in table['items'].values() if is_valued(entry) and entry.get('site_ids')
                     and set(entry['equivalents']) == {'final'} and entry.get('status') != 'estimated')
        item_id = entry['site_ids'][0]
        by_count = (entry.get('equivalents_by_elements') or {}).get('2', entry['equivalents'])
        with mock.patch('chardata.presets._panel_turn', side_effect=_panel):
            turn = tuning.credited_turn(CHAR, _solution((item_id,)), table, WEIGHTS)
        self.assertAlmostEqual(_panel(CHAR, _solution()) * (1 + by_count['final'] / 100.0), turn)
