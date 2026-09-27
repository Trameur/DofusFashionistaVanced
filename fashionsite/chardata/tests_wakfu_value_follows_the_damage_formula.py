import collections
import math

from django.test import SimpleTestCase

from fashionistapulp import wakfu_value as value_model
from fashionistapulp.wakfu_value_rules import CHOICE, FACT, FAN, RULES, STATUSES

LEVEL = 200


def totals(**stats):
    out = value_model.bare_totals()
    for key, number in stats.items():
        out[key] = number
    return out


def operating_point():
    """A level-200 stat line inside every band: crit under 100, resistances under the cap."""
    return totals(ap=12, dmg_fire_percent=1400, dmg_water_percent=1100,
                  dmg_in_percent=150, ranged_dmg=500, melee_dmg=80,
                  critical_bonus=120, ferocity=37, hp=3900, block=12,
                  res_fire_percent=180, res_water_percent=260,
                  res_earth_percent=90, res_air_percent=-40, res_in_percent=60)


def slope(role, point, key, step=0.01):
    """100 x d(value)/d(key), central difference."""
    up, down = collections.Counter(point), collections.Counter(point)
    up[key] += step
    down[key] -= step
    return 100 * (value_model.value(role, LEVEL, up)
                  - value_model.value(role, LEVEL, down)) / (2 * step)


def slope_above(role, point, key, step=0.001):
    """100 x the right-hand derivative of the value along key."""
    up = collections.Counter(point)
    up[key] += step
    return 100 * (value_model.value(role, LEVEL, up)
                  - value_model.value(role, LEVEL, point)) / step


class AWakfuHitFollowsTheDamageFormulaTests(SimpleTestCase):
    def test_a_hit_reproduces_the_methodwakfu_worked_example(self):
        damage = value_model.hit_damage(
            108, 6000 + 960, critical=True, critical_mastery=800,
            damage_inflicted=89, orientation=1.1, resistance=63,
            base_multiplier=1.5)
        self.assertAlmostEqual(12213.218556, damage, places=6)

    def test_a_critical_hit_rounds_its_base_down_before_the_masteries(self):
        self.assertEqual(12 * 2, value_model.hit_damage(10, 100, critical=True))
        self.assertEqual(10 * 2, value_model.hit_damage(10, 100))

    def test_critical_mastery_counts_only_on_a_critical_hit(self):
        self.assertEqual(value_model.hit_damage(100, 300),
                         value_model.hit_damage(100, 300, critical_mastery=500))
        self.assertEqual(125 * 9, value_model.hit_damage(
            100, 300, critical=True, critical_mastery=500))

    def test_damage_inflicted_never_counts_below_minus_fifty(self):
        self.assertEqual(50, value_model.hit_damage(100, 0, damage_inflicted=-50))
        self.assertEqual(50, value_model.hit_damage(100, 0, damage_inflicted=-80))
        self.assertAlmostEqual(170, value_model.hit_damage(100, 0, damage_inflicted=70))

    def test_the_expected_factor_weighs_the_critical_hit_by_its_chance(self):
        self.assertEqual(11, value_model.expected_factor(1000, 400, 0))
        self.assertEqual(1.25 * 15, value_model.expected_factor(1000, 400, 1))
        self.assertAlmostEqual(0.7 * 11 + 0.3 * 1.25 * 15,
                               value_model.expected_factor(1000, 400, 0.3))


class TheWakfuResistanceCurveTests(SimpleTestCase):
    def test_the_curve_gives_the_percents_methodwakfu_lists(self):
        listed = {1: 0, 101: 20, 201: 36, 301: 48, 851: 85, 951: 88,
                  -100: -25, -200: -56}
        self.assertEqual(listed, {raw: value_model.resistance_percent(raw)
                                  for raw in listed})

    def test_one_hundred_resistance_is_twenty_percent(self):
        self.assertEqual(20, value_model.resistance_percent(100))
        self.assertEqual(10, value_model.resistance_percent(50))

    def test_ninety_percent_is_reached_at_1032_and_never_passed(self):
        self.assertEqual(89, value_model.resistance_percent(1031))
        self.assertEqual(90, value_model.resistance_percent(1032))
        self.assertEqual(90, value_model.resistance_percent(5000))

    def test_the_share_taken_stops_at_the_cap(self):
        self.assertAlmostEqual(0.8, value_model.share_taken(100))
        self.assertAlmostEqual(0.1, value_model.share_taken(1100))
        self.assertAlmostEqual(1.25, value_model.share_taken(-100))


class TheWakfuCriticalChanceTests(SimpleTestCase):
    def test_the_base_chance_comes_on_top_of_the_gear(self):
        self.assertAlmostEqual(0.03, value_model.critical_chance(0))
        self.assertAlmostEqual(0.33, value_model.critical_chance(30))

    def test_a_chance_past_one_hundred_adds_nothing(self):
        self.assertEqual(1, value_model.critical_chance(97))
        self.assertEqual(1, value_model.critical_chance(150))

    def test_a_negative_total_counts_as_no_chance(self):
        self.assertEqual(0, value_model.critical_chance(-9))


class TheWakfuEffectiveLifeTests(SimpleTestCase):
    def test_life_is_fifty_plus_ten_per_level_plus_the_gear(self):
        self.assertEqual(2050, value_model.life(200, totals()))
        self.assertEqual(3050, value_model.life(200, totals(hp=1000)))

    def test_one_hundred_resistance_on_every_element_divides_hits_by_one_and_a_quarter(self):
        self.assertAlmostEqual(2050 / 0.8, value_model.effective_life(
            200, totals(res_in_percent=100)))
        self.assertAlmostEqual(2050 / 0.8, value_model.effective_life(
            200, totals(res_fire_percent=100, res_water_percent=100,
                        res_earth_percent=100, res_air_percent=100)))

    def test_one_element_counts_for_a_quarter_of_the_hits(self):
        self.assertAlmostEqual(2050 / ((0.8 + 3) / 4), value_model.effective_life(
            200, totals(res_fire_percent=100)))

    def test_full_block_weighs_like_one_hundred_resistance(self):
        self.assertAlmostEqual(
            value_model.effective_life(200, totals(res_in_percent=100)),
            value_model.effective_life(200, totals(block=100)))
        self.assertEqual(value_model.effective_life(200, totals(block=100)),
                         value_model.effective_life(200, totals(block=180)))


class TheWakfuLinearWeightsTests(SimpleTestCase):
    def test_each_weight_is_the_slope_of_the_value(self):
        for role in (value_model.DamageDealer(('fire',)),
                     value_model.DamageDealer(('fire', 'water'), 'melee', 1.0)):
            point = operating_point()
            weights = value_model.linear_weights(role, LEVEL, point)
            self.assertGreater(len(weights), 8)
            for key, weight in weights.items():
                with self.subTest(role=role, key=key):
                    self.assertAlmostEqual(1, weight / slope(role, point, key), places=4)

    def test_elemental_lines_are_worth_the_sum_of_the_element_weights(self):
        role = value_model.DamageDealer(('fire', 'water'))
        point = operating_point()
        weights = value_model.linear_weights(role, LEVEL, point)
        self.assertNotIn('dmg_in_percent', weights)
        self.assertNotIn('res_in_percent', weights)
        for generic, family in (('dmg_in_percent', value_model.MASTERY_OF),
                                ('res_in_percent', value_model.RESISTANCE_OF)):
            with self.subTest(generic=generic):
                summed = sum(weights.get(key, 0) for key in family.values())
                self.assertAlmostEqual(1, summed / slope(role, point, generic), places=4)

    def test_a_single_element_role_gives_the_other_elements_no_mastery_weight(self):
        weights = value_model.linear_weights(
            value_model.DamageDealer(('air',)), LEVEL, operating_point())
        self.assertGreater(weights['dmg_air_percent'], 0)
        for element in ('fire', 'water', 'earth'):
            self.assertNotIn(value_model.MASTERY_OF[element], weights)

    def test_two_elements_cast_equally_split_the_mastery_weight(self):
        point = totals(ap=11, dmg_fire_percent=900, dmg_water_percent=900, ferocity=20)
        single = value_model.linear_weights(value_model.DamageDealer(('fire',)), LEVEL, point)
        double = value_model.linear_weights(value_model.DamageDealer(('fire', 'water')), LEVEL, point)
        self.assertAlmostEqual(single['dmg_fire_percent'] / 2, double['dmg_fire_percent'])
        self.assertAlmostEqual(double['dmg_fire_percent'], double['dmg_water_percent'])
        self.assertAlmostEqual(single['ranged_dmg'], double['ranged_dmg'])

    def test_the_reach_picks_melee_or_distance_mastery(self):
        point = operating_point()
        distance = value_model.linear_weights(value_model.DamageDealer(), LEVEL, point)
        melee = value_model.linear_weights(
            value_model.DamageDealer(reach='melee'), LEVEL, point)
        self.assertIn('ranged_dmg', distance)
        self.assertNotIn('melee_dmg', distance)
        self.assertIn('melee_dmg', melee)
        self.assertNotIn('ranged_dmg', melee)

    def test_crit_past_the_cap_is_worth_nothing(self):
        role = value_model.DamageDealer()
        self.assertIn('ferocity', value_model.linear_weights(role, LEVEL, totals(ferocity=96)))
        self.assertNotIn('ferocity', value_model.linear_weights(role, LEVEL, totals(ferocity=97)))

    def test_crit_or_block_below_zero_on_the_sheet_is_worth_nothing(self):
        role = value_model.DamageDealer()
        for key, below in (('ferocity', -8), ('ferocity', -5), ('ferocity', -3.5),
                           ('block', -20), ('block', -10)):
            point = operating_point()
            point[key] = below
            with self.subTest(key=key, total=below):
                self.assertEqual(0, slope(role, point, key))
                self.assertNotIn(key, value_model.linear_weights(role, LEVEL, point))

    def test_at_zero_crit_or_block_the_weight_is_the_slope_above(self):
        role = value_model.DamageDealer()
        base = RULES['base_critical_hit_percent'].value
        for key, edge in (('ferocity', -base), ('block', 0)):
            point = operating_point()
            point[key] = edge
            with self.subTest(key=key):
                above = slope_above(role, point, key)
                self.assertGreater(above, 0)
                weight = value_model.linear_weights(role, LEVEL, point)[key]
                self.assertAlmostEqual(1, weight / above, places=4)

    def test_resistance_past_the_cap_is_worth_nothing(self):
        weights = value_model.linear_weights(
            value_model.DamageDealer(), LEVEL,
            totals(res_fire_percent=1040, res_water_percent=1020))
        self.assertNotIn('res_fire_percent', weights)
        self.assertGreater(weights['res_water_percent'], 0)

    def test_one_ap_is_worth_one_more_share_of_the_turn(self):
        weights = value_model.linear_weights(value_model.DamageDealer(), LEVEL, totals(ap=12))
        self.assertAlmostEqual(100 / 12, weights['ap'])

    def test_damage_inflicted_changes_no_weight(self):
        point = operating_point()
        plain = value_model.linear_weights(value_model.DamageDealer(), LEVEL, point)
        boosted = value_model.linear_weights(
            value_model.DamageDealer(damage_inflicted=40), LEVEL, point)
        self.assertEqual(plain.keys(), boosted.keys())
        for key in plain:
            self.assertAlmostEqual(plain[key], boosted[key])

    def test_a_role_without_defense_values_no_life_resistance_or_block(self):
        weights = value_model.linear_weights(
            value_model.DamageDealer(defense=0), LEVEL, operating_point())
        self.assertEqual(set(), {'hp', 'block'} & set(weights))
        self.assertEqual(set(), set(value_model.RESISTANCE_OF.values()) & set(weights))

    def test_the_defense_weight_scales_every_defensive_weight(self):
        point = operating_point()
        quarter = value_model.linear_weights(value_model.DamageDealer(defense=0.25), LEVEL, point)
        whole = value_model.linear_weights(value_model.DamageDealer(defense=1), LEVEL, point)
        for key in ['hp', 'block'] + list(value_model.RESISTANCE_OF.values()):
            self.assertAlmostEqual(4 * quarter[key], whole[key])
        self.assertAlmostEqual(quarter['ap'], whole['ap'])

    def test_a_distance_role_keeps_range_and_every_role_keeps_base_mp_and_wp(self):
        self.assertEqual({'mp': 3, 'wp': 6, 'range': 0},
                         value_model.DamageDealer(reach='distance').minimums())
        self.assertEqual({'mp': 3, 'wp': 6},
                         value_model.DamageDealer(reach='melee').minimums())

    def test_a_role_refuses_an_element_no_gear_sells(self):
        with self.assertRaises(ValueError):
            value_model.DamageDealer(('fire', 'light'))
        with self.assertRaises(ValueError):
            value_model.DamageDealer(reach='rear')


class TheWakfuValueRulesNameTheirSourcesTests(SimpleTestCase):
    def test_every_rule_has_a_status_and_a_source(self):
        for name, rule in RULES.items():
            with self.subTest(name=name):
                self.assertIn(rule.status, STATUSES)
                self.assertTrue(rule.source.strip())

    def test_every_first_party_or_fan_rule_links_its_page(self):
        for name, rule in RULES.items():
            if rule.status in (FACT, FAN):
                with self.subTest(name=name):
                    self.assertIn('https://', rule.source)

    def test_the_cap_the_crit_multiplier_and_the_damage_floor_are_ankamas(self):
        for name in ('resistance_cap_percent', 'critical_multiplier',
                     'damage_inflicted_floor_percent'):
            with self.subTest(name=name):
                self.assertEqual(FACT, RULES[name].status)
                self.assertIn('wakfu.com', RULES[name].source)

    def test_the_defense_weight_is_marked_as_a_choice(self):
        self.assertEqual(CHOICE, RULES['defense_weight'].status)
        self.assertEqual(RULES['defense_weight'].value,
                         value_model.DamageDealer().defense)

    def test_the_curve_reaches_the_first_party_cap_where_the_fan_source_says(self):
        base = RULES['resistance_base'].value
        cap = RULES['resistance_cap_percent'].value / 100
        self.assertLess(1 - base ** 10.31, cap)
        self.assertGreaterEqual(1 - base ** 10.32, cap)
        self.assertTrue(math.isclose(1 - base, 0.2))
