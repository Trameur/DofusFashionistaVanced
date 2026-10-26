import math
import random

from django.test import SimpleTestCase

from fashionistapulp import wakfu_defense, wakfu_value
from fashionistapulp.wakfu_value_rules import (
    ANKAMA_1_68, ASSUMPTION, CHOICE, FAN, METHODWAKFU, RULES)

LEVEL = 200
DEFENSE = 0.25


def totals(**stats):
    return dict(stats)


def hits(totals_, content='pvm'):
    """Share through of every cell of the mix, one element, from the stats alone."""
    return [(critical, rear, wakfu_defense.share_taken(
                wakfu_defense._raw(totals_, 'fire', critical, rear)))
            for critical, rear, _, _ in wakfu_defense.hit_mix(content)]


class TheCurveFollowsTheCreditedSourcesTests(SimpleTestCase):
    def test_ninety_percent_is_reached_at_1032_as_patch_1_68_and_methodwakfu_say(self):
        self.assertIn(ANKAMA_1_68, RULES['resistance_cap_percent'].source)
        self.assertIn(METHODWAKFU, RULES['resistance_cap_percent'].source)
        self.assertEqual(89, wakfu_defense.resistance_percent(1031))
        self.assertEqual(90, wakfu_defense.resistance_percent(1032))
        self.assertEqual(90, wakfu_defense.resistance_percent(4000))

    def test_one_hundred_resistance_takes_twenty_percent_of_a_hit_as_methodwakfu_says(self):
        self.assertIn(METHODWAKFU, RULES['resistance_base'].source)
        self.assertEqual(20, wakfu_defense.resistance_percent(100))
        self.assertAlmostEqual(0.8, wakfu_defense.share_taken(100))

    def test_block_multiplies_the_hit_by_eight_tenths_as_methodwakfu_says(self):
        self.assertIn(METHODWAKFU, RULES['block_multiplier'].source)
        self.assertAlmostEqual(0.8, wakfu_defense.block_factor(totals(block=100)))
        self.assertAlmostEqual(
            wakfu_defense.effective_life(LEVEL, totals()) / 0.8,
            wakfu_defense.effective_life(LEVEL, totals(block=100)))

    def test_every_new_rule_names_its_source_and_status(self):
        fan = ('critical_resistance_adds_to_raw', 'rear_resistance_adds_to_raw',
               'armor_cap_share_of_life')
        for name in fan:
            with self.subTest(name=name):
                self.assertEqual(FAN, RULES[name].status)
                self.assertIn(METHODWAKFU, RULES[name].source)
        for name, status in (('received_critical_share', ASSUMPTION),
                             ('received_rear_share', CHOICE),
                             ('received_side_share', CHOICE),
                             ('armor_turns_held', CHOICE)):
            with self.subTest(name=name):
                self.assertEqual(status, RULES[name].status)
                self.assertTrue(RULES[name].source.strip())

    def test_the_received_hit_shares_are_the_designs(self):
        self.assertEqual({'pvm': 0.03, 'pvp': 0.25}, RULES['received_critical_share'].value)
        self.assertEqual({'pvm': 0.10, 'pvp': 0.20}, RULES['received_rear_share'].value)
        self.assertEqual(0.20, RULES['received_side_share'].value)
        self.assertEqual(0.5, RULES['armor_cap_share_of_life'].value)
        self.assertEqual(1, RULES['armor_turns_held'].value)


class TheHitMixTests(SimpleTestCase):
    def test_the_shares_sum_to_one_and_every_kind_of_hit_is_there(self):
        for content in wakfu_defense.CONTENTS:
            with self.subTest(content=content):
                mix = wakfu_defense.hit_mix(content)
                self.assertEqual(6, len(mix))
                self.assertAlmostEqual(1, sum(share for _, _, share, _ in mix))
                self.assertEqual({(False, False), (False, True), (True, False),
                                  (True, True)}, {(c, r) for c, r, _, _ in mix})

    def test_the_multipliers_are_side_rear_and_critical(self):
        by_kind = {(critical, rear, multiplier)
                   for critical, rear, _, multiplier in wakfu_defense.hit_mix('pvm')}
        self.assertIn((False, False, 1), by_kind)
        self.assertIn((False, False, 1.10), by_kind)
        self.assertIn((False, True, 1.25), by_kind)
        self.assertIn((True, False, 1.25), by_kind)
        self.assertIn((True, True, 1.25 * 1.25), by_kind)

    def test_pvp_receives_more_critical_and_rear_hits_than_pvm(self):
        def share(content, critical=None, rear=None):
            return sum(s for c, r, s, _ in wakfu_defense.hit_mix(content)
                       if (critical is None or c == critical) and (rear is None or r == rear))
        self.assertAlmostEqual(0.03, share('pvm', critical=True))
        self.assertAlmostEqual(0.25, share('pvp', critical=True))
        self.assertAlmostEqual(0.10, share('pvm', rear=True))
        self.assertAlmostEqual(0.20, share('pvp', rear=True))

    def test_an_unknown_content_is_refused(self):
        with self.assertRaises(KeyError):
            wakfu_defense.hit_mix('arena')


class CriticalAndRearResistanceTests(SimpleTestCase):
    def test_critical_resistance_joins_the_raw_resistance_on_a_critical_hit_only(self):
        sheet = totals(res_fire_percent=100, critical_res=50)
        for critical, rear, share in hits(sheet):
            with self.subTest(critical=critical, rear=rear):
                self.assertAlmostEqual(
                    wakfu_defense.share_taken(150 if critical else 100), share)

    def test_rear_resistance_joins_the_raw_resistance_on_a_rear_hit_only(self):
        sheet = totals(res_fire_percent=100, res_backstab=40)
        for critical, rear, share in hits(sheet):
            with self.subTest(critical=critical, rear=rear):
                self.assertAlmostEqual(
                    wakfu_defense.share_taken(140 if rear else 100), share)

    def test_a_rear_critical_hit_gets_both(self):
        sheet = totals(res_fire_percent=100, critical_res=50, res_backstab=40)
        both = [share for critical, rear, share in hits(sheet) if critical and rear]
        self.assertAlmostEqual(wakfu_defense.share_taken(190), both[0])

    def test_the_cap_applies_after_the_two_are_added(self):
        sheet = totals(res_fire_percent=900, critical_res=200)
        critical = [share for c, r, share in hits(sheet) if c and not r][0]
        self.assertAlmostEqual(0.1, critical)
        self.assertGreater(wakfu_defense.share_taken(900), 0.1)

    def test_a_negative_rear_resistance_makes_a_rear_hit_hurt_more(self):
        plain = wakfu_defense.taken(totals(res_fire_percent=200))
        weak = wakfu_defense.taken(totals(res_fire_percent=200, res_backstab=-200))
        self.assertGreater(weak, plain)

    def test_rear_resistance_is_worth_more_in_pvp_than_in_pvm(self):
        sheet = totals(res_fire_percent=100)
        gain = {}
        for content in wakfu_defense.CONTENTS:
            with_rear = dict(sheet, res_backstab=100)
            gain[content] = (wakfu_defense.effective_life(LEVEL, with_rear, content)
                             / wakfu_defense.effective_life(LEVEL, sheet, content))
        self.assertGreater(gain['pvp'], gain['pvm'])
        self.assertGreater(gain['pvm'], 1)

    def test_critical_resistance_is_worth_more_in_pvp_than_in_pvm(self):
        sheet = totals(res_fire_percent=100)
        gain = {}
        for content in wakfu_defense.CONTENTS:
            with_critical = dict(sheet, critical_res=100)
            gain[content] = (wakfu_defense.effective_life(LEVEL, with_critical, content)
                             / wakfu_defense.effective_life(LEVEL, sheet, content))
        self.assertGreater(gain['pvp'], gain['pvm'])


class WithoutCriticalAndRearResistanceTheLifeIsTheOldFormulaTests(SimpleTestCase):
    def random_totals(self, generator):
        sheet = {'hp': generator.randint(0, 6000),
                 'hp_percent': generator.randint(0, 40),
                 'block': generator.randint(-20, 130),
                 'res_in_percent': generator.randint(-100, 500)}
        for key in wakfu_defense.RESISTANCE_OF.values():
            sheet[key] = generator.randint(-300, 1300)
        return sheet

    def test_effective_life_equals_life_over_mean_share_and_block_on_fifty_random_sheets(self):
        generator = random.Random(9)
        for index in range(50):
            sheet = self.random_totals(generator)
            level = generator.randint(1, 245)
            for content in wakfu_defense.CONTENTS:
                with self.subTest(index=index, content=content):
                    old = (wakfu_defense.life(level, sheet)
                           / (wakfu_defense.mean_share_taken(sheet)
                              * wakfu_defense.block_factor(sheet)))
                    self.assertEqual(old, wakfu_defense.effective_life(level, sheet, content))

    def test_taken_equals_the_mean_share_taken_exactly(self):
        generator = random.Random(10)
        for _ in range(50):
            sheet = self.random_totals(generator)
            self.assertEqual(wakfu_defense.mean_share_taken(sheet),
                             wakfu_defense.taken(sheet))

    def test_a_zero_value_in_the_two_keys_changes_nothing(self):
        generator = random.Random(11)
        sheet = self.random_totals(generator)
        self.assertEqual(wakfu_defense.effective_life(LEVEL, sheet),
                         wakfu_defense.effective_life(
                             LEVEL, dict(sheet, critical_res=0, res_backstab=0)))

    def test_the_weights_keep_the_old_slopes(self):
        generator = random.Random(12)
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        for _ in range(20):
            sheet = dict(self.random_totals(generator), ap=12, mp=4, wp=6)
            weights = wakfu_value.linear_weights(role, LEVEL, sheet)
            raw = wakfu_defense.raw_life(LEVEL, sheet)
            self.assertAlmostEqual(100 * DEFENSE / raw, weights['hp'])
            slope = math.log(1 / 0.8) / 100
            plain = sheet['res_in_percent']
            through = wakfu_defense.mean_share_taken(sheet)
            for element, key in wakfu_defense.RESISTANCE_OF.items():
                share = 0.8 ** ((sheet[key] + plain) / 100)
                if share > 0.1:
                    self.assertAlmostEqual(
                        100 * DEFENSE * slope * share / 4 / through, weights[key])
                else:
                    self.assertNotIn(key, weights)

    def test_wakfu_value_re_exports_the_same_functions(self):
        for name in ('raw_life', 'life', 'share_taken', 'resistance_percent',
                     'mean_share_taken', 'block_factor', 'effective_life'):
            with self.subTest(name=name):
                self.assertIs(getattr(wakfu_defense, name), getattr(wakfu_value, name))


class ArmorTests(SimpleTestCase):
    def test_no_armor_turn_holds_no_armor(self):
        self.assertEqual(0, wakfu_defense.armor(LEVEL, totals(hp=2000)))

    def test_one_turn_of_armor_adds_to_the_life_before_the_hits(self):
        sheet = totals(hp=2000)
        life = wakfu_defense.life(LEVEL, sheet)
        self.assertEqual(500, wakfu_defense.armor(LEVEL, sheet, 500))
        self.assertAlmostEqual(
            (life + 500) / life,
            wakfu_defense.effective_life(LEVEL, sheet, armor_turn=500)
            / wakfu_defense.effective_life(LEVEL, sheet))

    def test_the_gear_percents_multiply_the_armor(self):
        sheet = totals(hp=6000, armor_given_percent=40, armor_received_percent=15)
        self.assertAlmostEqual(1000 * 1.4 * 1.15, wakfu_defense.armor(LEVEL, sheet, 1000))

    def test_armor_stops_at_half_of_the_life_as_methodwakfu_says(self):
        self.assertEqual(0.5, RULES['armor_cap_share_of_life'].value)
        self.assertIn(METHODWAKFU, RULES['armor_cap_share_of_life'].source)
        sheet = totals(hp=1000)
        life = wakfu_defense.life(LEVEL, sheet)
        self.assertEqual(life * 0.5, wakfu_defense.armor(LEVEL, sheet, 10 ** 6))
        self.assertEqual(life * 0.5, wakfu_defense.armor(LEVEL, sheet, life))
        self.assertAlmostEqual(
            1.5, wakfu_defense.effective_life(LEVEL, sheet, armor_turn=10 ** 6)
            / wakfu_defense.effective_life(LEVEL, sheet))

    def test_a_gear_that_takes_all_the_armor_away_leaves_none_not_a_negative(self):
        self.assertEqual(0, wakfu_defense.armor(
            LEVEL, totals(armor_given_percent=-150), 1000))


class TheWeightsAreTheSlopesOfTheEffectiveLifeTests(SimpleTestCase):
    SHEET = dict(hp=3000, res_fire_percent=180, res_water_percent=260,
                 res_earth_percent=90, res_air_percent=-40, res_in_percent=30,
                 block=12, critical_res=40, res_backstab=25,
                 armor_given_percent=10, armor_received_percent=5)
    STEP = 1e-3

    def slope(self, key, content, armor_turn):
        low = dict(self.SHEET)
        high = dict(self.SHEET, **{key: self.SHEET.get(key, 0) + self.STEP})
        gain = (math.log(wakfu_defense.effective_life(LEVEL, high, content, armor_turn))
                - math.log(wakfu_defense.effective_life(LEVEL, low, content, armor_turn)))
        return 100 * DEFENSE * gain / self.STEP

    def test_each_weight_is_the_finite_difference_of_the_log(self):
        for content in wakfu_defense.CONTENTS:
            for armor_turn in (0, 800):
                weights = wakfu_defense.defense_weights(
                    DEFENSE, LEVEL, self.SHEET, content, armor_turn)
                keys = ['critical_res', 'res_backstab', 'block', 'res_fire_percent',
                        'res_air_percent']
                if armor_turn:
                    keys += ['armor_given_percent', 'armor_received_percent']
                for key in keys:
                    with self.subTest(content=content, armor_turn=armor_turn, key=key):
                        self.assertAlmostEqual(
                            self.slope(key, content, armor_turn), weights[key], places=3)

    def test_armor_weights_exist_only_with_an_armor_turn(self):
        without = wakfu_defense.defense_weights(DEFENSE, LEVEL, self.SHEET)
        self.assertNotIn('armor_given_percent', without)
        self.assertNotIn('armor_received_percent', without)
        held = wakfu_defense.defense_weights(DEFENSE, LEVEL, self.SHEET, armor_turn=800)
        self.assertGreater(held['armor_given_percent'], 0)
        self.assertGreater(held['armor_received_percent'], 0)

    def test_armor_at_its_cap_carries_no_weight(self):
        weights = wakfu_defense.defense_weights(
            DEFENSE, LEVEL, self.SHEET, armor_turn=10 ** 6)
        self.assertNotIn('armor_given_percent', weights)
        self.assertNotIn('armor_received_percent', weights)

    def test_a_cap_reached_on_every_cell_removes_the_weight(self):
        weights = wakfu_defense.defense_weights(
            DEFENSE, LEVEL, dict(self.SHEET, res_fire_percent=1100, critical_res=0,
                                 res_backstab=0))
        self.assertNotIn('res_fire_percent', weights)

    def test_critical_resistance_is_worth_nothing_where_the_cap_is_reached_on_critical_hits(self):
        sheet = dict(self.SHEET, res_fire_percent=1100, res_water_percent=1100,
                     res_earth_percent=1100, res_air_percent=1100)
        weights = wakfu_defense.defense_weights(DEFENSE, LEVEL, sheet)
        self.assertNotIn('critical_res', weights)
        self.assertNotIn('res_backstab', weights)

    def test_the_solver_weights_carry_the_new_keys(self):
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        sheet = dict(self.SHEET, ap=12, mp=4, wp=6)
        weights = wakfu_value.linear_weights(role, LEVEL, sheet)
        self.assertGreater(weights['critical_res'], 0)
        self.assertGreater(weights['res_backstab'], 0)
        held = wakfu_value.linear_weights(role, LEVEL, sheet, armor_turn=800)
        self.assertGreater(held['armor_given_percent'], 0)
        self.assertLess(held['hp'], weights['hp'])

    def test_value_takes_the_armor_into_the_log(self):
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        sheet = dict(self.SHEET, ap=12, mp=4, wp=6)
        self.assertAlmostEqual(
            DEFENSE * math.log(wakfu_defense.effective_life(LEVEL, sheet, 'pvp', 800)
                               / wakfu_defense.effective_life(LEVEL, sheet)),
            wakfu_value.value(role, LEVEL, sheet, content='pvp', armor_turn=800)
            - wakfu_value.value(role, LEVEL, sheet))


class TheCapIsAppliedAfterTheCriticalAndRearResistanceTests(SimpleTestCase):
    def test_taken_caps_each_hit_after_critical_resistance_is_added(self):
        sheet = totals(res_in_percent=900, critical_res=200)
        mix = wakfu_defense.hit_mix('pvp')
        expected = (sum(share * multiplier
                        * max(RULES['resistance_base'].value ** ((900 + 200 * critical) / 100),
                              1 - RULES['resistance_cap_percent'].value / 100)
                        for critical, _, share, multiplier in mix)
                    / sum(share * multiplier for _, _, share, multiplier in mix))
        self.assertAlmostEqual(expected, wakfu_defense.taken(sheet, 'pvp'), 12)
        self.assertAlmostEqual(0.124154, wakfu_defense.taken(sheet, 'pvp'), 6)

    def test_a_critical_hit_through_the_cap_takes_the_cap_and_not_less(self):
        sheet = totals(res_in_percent=1100, critical_res=300, res_backstab=300)
        self.assertAlmostEqual(0.1, wakfu_defense.taken(sheet, 'pvp'), 12)

    def test_taken_with_the_cap_in_play_is_above_the_uncapped_product_of_both_resistances(self):
        sheet = totals(res_in_percent=900, critical_res=200)
        below = sum(share * multiplier
                    * RULES['resistance_base'].value ** ((900 + 200 * critical) / 100)
                    for critical, _, share, multiplier in wakfu_defense.hit_mix('pvp'))
        norm = sum(share * multiplier for _, _, share, multiplier in wakfu_defense.hit_mix('pvp'))
        self.assertGreater(wakfu_defense.taken(sheet, 'pvp'), below / norm)
