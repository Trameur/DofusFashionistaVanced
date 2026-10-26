import collections
import math
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import wakfu_defense, wakfu_family, wakfu_turn, wakfu_value
from fashionistapulp.wakfu_value_rules import RULES, Rule, CHOICE

LEVEL = 200
BASE = {'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)}
FIRE = ('fire',)
NONE = frozenset()


def totals(**stats):
    out = wakfu_value.bare_totals(BASE)
    out.update(stats)
    return out


def sheet(**more):
    return totals(ap=11, dmg_fire_percent=400, melee_dmg=50, ranged_dmg=90, ferocity=27,
                  critical_bonus=30, hp=1800, hp_percent=12, res_in_percent=90,
                  res_fire_percent=140, block=8, heal_in_percent=60, willpower=10,
                  tackle=120, dodge=80, init=20, wisdom=7, prospection=11, **more)


def row(position, base, critical, area=False, element='fire'):
    return wakfu_turn.Row(position, element, base, critical, 'client', NONE, NONE, 'hit', 1,
                          None, '', collections.Counter(), 'client', area)


def spell(ident, low, high, *rows, ap=3):
    return wakfu_turn.Spell(ident, 'spell %d' % ident, 'fire', ap, 0, 0, low, high, tuple(rows),
                            (), True, (), 1, None)


MELEE = spell(1, 1, 1, row(0, 100, 125), row(1, 40, 50, area=True))
FAR = spell(2, 3, 6, row(0, 80, 100))
SPELLS = [MELEE, FAR]


def family(action, element, amount, ap=3):
    found = wakfu_family.FamilyRow(action, action, element, amount, None, 'none')
    return wakfu_family.FamilySpell(10 + action, 'x', 5, None, ap, 0, 0, 1, 5, 1, LEVEL,
                                    (found,), ())


HEAL = wakfu_family.FamilySpell(
    20, 'heal', 7, None, 3, 0, 0, 1, 5, 1, LEVEL,
    (wakfu_family.FamilyRow(1, 258, 'water', 100, 125, 'client'),), ())
ARMOR = family(1013, 'armor', 200)
PLACEMENT = family(300, 'push', 3)
HINDRANCE = family(55, wakfu_family.REMOVED[55], 4)
FAMILY_SPELLS = {'heal': HEAL, 'armor': ARMOR, 'placement': PLACEMENT, 'hindrance': HINDRANCE}
SCALES = {'tackle': 2000, 'dodge': 1500, 'init': 60}


def role(reach='distance', shares=None, **options):
    return wakfu_value.Role(FIRE, reach, shares=shares, **options)


def turns(the_role, scales=SCALES):
    models = {}
    reaches = ('melee', 'distance') if the_role.reach == 'mixed' else (the_role.reach,)
    if 'damage' in the_role.shares:
        for reach in reaches:
            models['damage' if the_role.reach != 'mixed' else reach] = wakfu_turn.TurnModel(
                SPELLS, the_role._replace(reach=reach), casts_per_spell=1)
    side = the_role._replace(reach='distance' if the_role.reach == 'mixed' else the_role.reach)
    for name, found in FAMILY_SPELLS.items():
        if name in the_role.shares or (name == 'armor' and 'life' in the_role.shares):
            models[name] = wakfu_turn.TurnModel([found], side, name, casts_per_spell=1)
    return wakfu_turn.RoleTurns(the_role, LEVEL, models, scales)


class TheDamageDealerIsTheRoleOfDamageAndLifeTests(SimpleTestCase):
    def setUp(self):
        self.dealer = wakfu_value.DamageDealer(('fire', 'water'), 'distance', 0.25, 15)
        self.model = wakfu_turn.TurnModel(SPELLS, self.dealer, casts_per_spell=1)

    def test_it_builds_the_role_with_a_damage_share_of_one_and_a_life_share_of_its_defense(self):
        found = self.dealer.role()
        self.assertEqual({'damage': 1.0, 'life': 0.25}, found.shares)
        self.assertEqual((('fire', 'water'), 'distance', 'single', 'pvm', False, None, 15),
                         found[:7])
        self.assertEqual(0.25, found.defense)
        self.assertEqual({'damage': 1.0}, wakfu_value.DamageDealer(FIRE, 'melee', 0).role().shares)

    def test_value_and_weights_are_those_of_its_role_with_and_without_a_turn(self):
        for turn in (None, self.model):
            for content in ('pvm', 'pvp'):
                with self.subTest(turn=turn is not None, content=content):
                    self.assertEqual(
                        wakfu_value.value(self.dealer, LEVEL, sheet(), turn, content),
                        wakfu_value.value(self.dealer.role(), LEVEL, sheet(), turn, content))
                    self.assertEqual(
                        wakfu_value.linear_weights(self.dealer, LEVEL, sheet(), turn, content),
                        wakfu_value.linear_weights(self.dealer.role(), LEVEL, sheet(), turn,
                                                   content))

    def test_value_is_the_log_of_the_damage_plus_defense_times_the_log_of_effective_life(self):
        expected = (math.log(wakfu_value.turn_damage(self.dealer, sheet()))
                    + self.dealer.defense * math.log(wakfu_defense.effective_life(
                        LEVEL, sheet())))
        self.assertEqual(expected, wakfu_value.value(self.dealer, LEVEL, sheet()))
        best = self.model.damage(sheet())
        self.assertEqual(
            math.log(best) + self.dealer.defense * math.log(wakfu_defense.effective_life(
                LEVEL, sheet(), 'pvp', 90.0)),
            wakfu_value.value(self.dealer, LEVEL, sheet(), self.model, 'pvp', 90.0))

    def test_the_numbers_of_the_model_before_roles_are_unchanged(self):
        self.assertEqual(6.819631809789243, wakfu_value.value(self.dealer, LEVEL, self.pinned()))
        expected = {
            'ap': 5.882352941176471, 'block': 0.05081300813008129,
            'critical_bonus': 0.07575757575757576, 'critical_res': 0.0020763978099957487,
            'dmg_fire_percent': 0.10858585858585858, 'dmg_water_percent': 0.10858585858585858,
            'ferocity': 0.30303030303030304, 'final_dmg_in_percent': 0.8,
            'hp': 0.006493506493506494, 'hp_percent': 0.22321428571428573,
            'ranged_dmg': 0.21717171717171715, 'res_air_percent': 0.014949236534917773,
            'res_backstab': 0.006672953089539767, 'res_earth_percent': 0.014949236534917773,
            'res_fire_percent': 0.01093817822379913, 'res_water_percent': 0.014949236534917773}
        self.assertEqual(expected, wakfu_value.linear_weights(self.dealer, LEVEL, self.pinned()))

    @staticmethod
    def pinned():
        return totals(ap=11, dmg_fire_percent=400, dmg_water_percent=120, melee_dmg=50,
                      ranged_dmg=90, ferocity=27, critical_bonus=30, hp=1800, hp_percent=12,
                      res_in_percent=90, res_fire_percent=140, block=8,
                      final_dmg_in_percent=10)


class TheRoleIsValidatedTests(SimpleTestCase):
    def test_a_role_names_known_components_with_shares_that_are_not_negative(self):
        with self.assertRaisesMessage(ValueError, 'components are'):
            role(shares={'damage': 1, 'tanking': 1})
        with self.assertRaisesMessage(ValueError, 'cannot be negative'):
            role(shares={'damage': 1, 'life': -0.1})
        with self.assertRaisesMessage(ValueError, 'needs a share'):
            role(shares={'damage': 0})

    def test_a_role_with_a_damage_share_needs_an_element_and_the_mule_needs_none(self):
        with self.assertRaisesMessage(ValueError, 'elements are'):
            wakfu_value.Role((), 'distance', shares={'damage': 1})
        with self.assertRaisesMessage(ValueError, 'elements are'):
            wakfu_value.Role(('shadow',), 'distance')
        mule = wakfu_value.Role((), 'distance', shares={'mule': 1})
        self.assertEqual({'mule': 1.0}, mule.shares)
        self.assertEqual((), mule.elements)

    def test_reach_target_and_content_are_one_of_their_words(self):
        for field, word in (('reach', 'far'), ('target', 'crowd'), ('content', 'pve')):
            with self.subTest(field=field):
                options = {'target': 'single', 'content': 'pvm'}
                reach = 'distance'
                if field == 'reach':
                    reach = word
                else:
                    options[field] = word
                with self.assertRaisesMessage(ValueError, '%s is' % field):
                    wakfu_value.Role(FIRE, reach, **options)

    def test_the_movement_is_a_share_of_mp(self):
        with self.assertRaisesMessage(ValueError, 'share of MP'):
            role(movement=1.5)
        self.assertEqual(0.5, role(movement=0.5).movement)

    def test_the_range_floor_holds_for_a_distance_role_with_a_damage_share_only(self):
        base = {'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)}
        self.assertIn('range', role('distance').minimums(base))
        self.assertNotIn('range', role('melee').minimums(base))
        self.assertNotIn('range', role('mixed').minimums(base))
        self.assertNotIn('range', wakfu_value.Role((), 'distance',
                                                   shares={'mule': 1}).minimums(base))


class TheComponentsAreTheQuantitiesTheLogIsTakenOfTests(SimpleTestCase):
    def test_the_value_is_the_sum_of_share_times_log_of_each_component(self):
        found = role('mixed', {'damage': 1, 'life': 0.5, 'heal': 0.3, 'armor': 0.2,
                               'placement': 0.1, 'hindrance': 0.1, 'lock': 0.1, 'dodge': 0.1,
                               'initiative': 0.1, 'mule': 0.1})
        every = turns(found)
        worth = wakfu_value.components(found, LEVEL, sheet(), every)
        self.assertEqual(set(wakfu_value.COMPONENTS), set(worth))
        expected = sum(found.shares[name] * math.log(worth[name]) for name in wakfu_value.COMPONENTS)
        self.assertAlmostEqual(expected, wakfu_value.value(found, LEVEL, sheet(), every), 12)

    def test_a_mixed_reach_is_half_a_melee_turn_and_half_a_distance_turn(self):
        mixed = role('mixed')
        every = turns(mixed)
        melee = wakfu_turn.TurnModel(SPELLS, role('melee'), casts_per_spell=1).damage(sheet())
        far = wakfu_turn.TurnModel(SPELLS, role('distance'), casts_per_spell=1).damage(sheet())
        self.assertNotEqual(melee, far)
        self.assertEqual(0.5 * melee + 0.5 * far,
                         wakfu_value.components(mixed, LEVEL, sheet(), every)['damage'])

    def test_the_closed_form_prices_a_mixed_reach_the_same_way(self):
        mixed = role('mixed')
        expected = 0.5 * wakfu_value.turn_damage(role('melee'), sheet()) \
            + 0.5 * wakfu_value.turn_damage(role('distance'), sheet())
        self.assertEqual(expected, wakfu_value.components(mixed, LEVEL, sheet())['damage'])

    def test_a_mixed_reach_needs_the_turns_of_both_reaches(self):
        lone = wakfu_turn.TurnModel(SPELLS, role('melee'), casts_per_spell=1)
        with self.assertRaisesMessage(ValueError, 'mixed reach needs'):
            wakfu_value.value(role('mixed'), LEVEL, sheet(), lone)

    def test_an_area_role_counts_the_area_rows_area_targets_times(self):
        single = wakfu_turn.TurnModel([MELEE], role('melee'), casts_per_spell=1).damage(sheet())
        area = wakfu_turn.TurnModel([MELEE], role('melee', target='area'),
                                    casts_per_spell=1)
        plain_row = wakfu_turn.TurnModel([spell(1, 1, 1, row(0, 100, 125))], role('melee'),
                                         casts_per_spell=1)
        only_area = wakfu_turn.TurnModel([spell(1, 1, 1, row(0, 40, 50, area=True))],
                                         role('melee'), casts_per_spell=1)
        targets = RULES['area_targets'].value
        extra = only_area.damage(sheet())
        self.assertEqual(single, plain_row.damage(sheet()) + extra)
        self.assertAlmostEqual(plain_row.damage(sheet()) + targets * extra, area.damage(sheet()))

    def test_area_targets_is_a_choice_and_moves_the_area_turn(self):
        self.assertEqual(CHOICE, RULES['area_targets'].status)
        found = wakfu_turn.TurnModel([MELEE], role('melee', target='area'), casts_per_spell=1)
        before = found.damage(sheet())
        patched = dict(RULES, area_targets=Rule(3, CHOICE, 'test'))
        with mock.patch.dict(RULES, patched):
            self.assertGreater(found.damage(sheet()), before)

    def test_life_is_the_effective_life_of_the_roles_content(self):
        for content in ('pvm', 'pvp'):
            found = role(shares={'damage': 1, 'life': 1}, content=content)
            stats = sheet(critical_res=60, res_backstab=40)
            self.assertEqual(
                wakfu_defense.effective_life(LEVEL, stats, content),
                wakfu_value.components(found, LEVEL, stats)['life'])
        pvm = wakfu_value.components(role(shares={'damage': 1, 'life': 1}), LEVEL,
                                     sheet(critical_res=60, res_backstab=40))['life']
        pvp = wakfu_value.components(role(shares={'damage': 1, 'life': 1}, content='pvp'),
                                     LEVEL, sheet(critical_res=60, res_backstab=40))['life']
        self.assertGreater(pvp, pvm)

    def test_life_holds_the_class_armor_turn_of_the_armor_model(self):
        found = role(shares={'damage': 1, 'life': 1})
        every = turns(found)
        armor = wakfu_defense.class_armor_turn(every.models['armor'].best(sheet()))[0]
        self.assertGreater(armor, 0)
        self.assertEqual(wakfu_defense.effective_life(LEVEL, sheet(), 'pvm', armor),
                         wakfu_value.components(found, LEVEL, sheet(), every)['life'])
        self.assertGreater(wakfu_value.components(found, LEVEL, sheet(), every)['life'],
                           wakfu_value.components(found, LEVEL, sheet())['life'])

    def test_heal_is_the_best_heal_turn_and_the_others_are_one_plus_their_turn(self):
        found = role(shares={'damage': 1, 'heal': 1, 'armor': 1, 'placement': 1,
                             'hindrance': 1})
        every = turns(found)
        worth = wakfu_value.components(found, LEVEL, sheet(), every)
        heal = every.models['heal'].damage(sheet())
        armor = every.models['armor'].damage(sheet())
        self.assertGreater(heal, 0)
        self.assertEqual(heal, worth['heal'])
        self.assertEqual(1 + armor, worth['armor'])
        self.assertEqual(1 + every.models['placement'].damage(sheet()), worth['placement'])
        self.assertEqual(1 + every.models['hindrance'].damage(sheet()), worth['hindrance'])

    def test_armor_is_multiplied_by_the_armor_given_percent(self):
        found = role(shares={'damage': 1, 'armor': 1})
        every = turns(found)
        plain = wakfu_value.components(found, LEVEL, sheet(), every)['armor']
        more = wakfu_value.components(found, LEVEL, sheet(armor_given_percent=40), every)['armor']
        armor = every.models['armor'].damage(sheet())
        self.assertEqual(1 + armor, plain)
        self.assertEqual(1 + armor * 1.4, more)

    def test_lock_dodge_and_initiative_are_one_plus_the_total_over_the_scale(self):
        found = role(shares={'damage': 1, 'lock': 1, 'dodge': 1, 'initiative': 1})
        worth = wakfu_value.components(found, LEVEL, sheet(), turns(found))
        self.assertEqual(1 + 120 / 2000, worth['lock'])
        self.assertEqual(1 + 80 / 1500, worth['dodge'])
        self.assertEqual(1 + 20 / 60, worth['initiative'])

    def test_a_stat_nothing_in_the_game_gives_is_a_flat_component(self):
        found = role(shares={'damage': 1, 'lock': 1})
        every = turns(found, {'tackle': 0})
        self.assertEqual(1.0, wakfu_value.components(found, LEVEL, sheet(), every)['lock'])
        self.assertNotIn('tackle', wakfu_value.linear_weights(found, LEVEL, sheet(), every))

    def test_the_mule_is_one_plus_wisdom_plus_prospection(self):
        mule = wakfu_value.Role((), 'distance', shares={'mule': 1})
        self.assertEqual(1 + 7 + 11, wakfu_value.components(mule, LEVEL, sheet())['mule'])
        self.assertEqual(1.0, wakfu_value.components(mule, LEVEL, totals())['mule'])

    def test_without_turns_the_components_that_need_spells_or_scales_are_left_out(self):
        found = role(shares={'damage': 1, 'life': 1, 'heal': 1, 'lock': 1, 'mule': 1})
        self.assertEqual({'damage', 'life', 'mule'},
                         set(wakfu_value.components(found, LEVEL, sheet())))

    def test_a_family_component_without_its_model_is_refused(self):
        found = role(shares={'damage': 1, 'heal': 1})
        lone = wakfu_turn.RoleTurns(found, LEVEL, {'damage': wakfu_turn.TurnModel(
            SPELLS, found, casts_per_spell=1)}, SCALES)
        with self.assertRaisesMessage(ValueError, 'no heal turn'):
            wakfu_value.value(found, LEVEL, sheet(), lone)

    def test_a_stat_component_without_scales_is_refused(self):
        found = role(shares={'damage': 1, 'lock': 1})
        lone = wakfu_turn.TurnModel(SPELLS, found, casts_per_spell=1)
        with self.assertRaisesMessage(ValueError, 'needs the scales'):
            wakfu_value.value(found, LEVEL, sheet(), lone)


class TheWeightsAreTheSlopesOfTheValueTests(SimpleTestCase):
    STEP = 1e-4

    def slopes(self, found, stats):
        every = turns(found)
        weights = wakfu_value.linear_weights(found, LEVEL, stats, every)
        here = wakfu_value.value(found, LEVEL, stats, every)
        out = {}
        for key in weights:
            moved = collections.Counter(stats)
            moved[key] += self.STEP
            out[key] = 100 * (wakfu_value.value(found, LEVEL, moved, every) - here) / self.STEP
        return weights, out

    def check(self, shares, skip=('ap', 'mp', 'wp', 'hp', 'hp_percent', wakfu_value.ELEMENTAL_MASTERY),
              **options):
        found = role(options.pop('reach', 'distance'), shares, **options)
        weights, slopes = self.slopes(found, sheet(armor_given_percent=10))
        self.assertTrue(weights)
        checked = 0
        for key, weight in weights.items():
            if key in skip or key.startswith('res_') or key in ('block', 'critical_res'):
                continue
            checked += 1
            self.assertAlmostEqual(weight, slopes[key], delta=max(1e-3 * abs(weight), 1e-7),
                                   msg=key)
        self.assertGreater(checked, 2)

    def test_damage_alone(self):
        self.check({'damage': 1})

    def test_a_mixed_reach(self):
        self.check({'damage': 1, 'lock': 0.3}, reach='mixed')

    def test_an_area_role(self):
        self.check({'damage': 1}, reach='melee', target='area')

    def test_heal(self):
        self.check({'damage': 0.5, 'heal': 0.5})

    def test_heal_alone_with_the_mastery_every_element_gives(self):
        self.check({'heal': 1}, skip=('ap', 'mp', 'wp'))

    def test_armor_and_placement_and_hindrance(self):
        self.check({'damage': 0.4, 'armor': 0.3, 'placement': 0.2, 'hindrance': 0.2})

    def test_lock_dodge_initiative_and_the_mule(self):
        found = role(shares={'damage': 0.5, 'lock': 0.2, 'dodge': 0.2, 'initiative': 0.2,
                             'mule': 0.3})
        weights, slopes = self.slopes(found, sheet())
        for key in ('tackle', 'dodge', 'init', 'wisdom', 'prospection'):
            self.assertAlmostEqual(weights[key], slopes[key], delta=1e-3 * weights[key], msg=key)
        self.assertEqual(100 * 0.2 / (2000 + 120), weights['tackle'])
        self.assertEqual(100 * 0.3 / (1 + 7 + 11), weights['wisdom'])

    def test_the_weights_grow_with_the_shares_and_nothing_else(self):
        one = role(shares={'damage': 1, 'life': 0.5, 'heal': 0.5, 'lock': 0.1})
        two = role(shares={'damage': 2, 'life': 1, 'heal': 1, 'lock': 0.2})
        small = wakfu_value.linear_weights(one, LEVEL, sheet(), turns(one))
        large = wakfu_value.linear_weights(two, LEVEL, sheet(), turns(two))
        self.assertEqual(set(small), set(large))
        for key, weight in small.items():
            self.assertAlmostEqual(2 * weight, large[key], places=12, msg=key)


class TheTurnsPriceEveryApTotalByTheWholeValueTests(SimpleTestCase):
    def test_each_ap_total_is_worth_the_gain_in_the_value(self):
        found = role(shares={'damage': 1, 'heal': 0.5, 'lock': 0.2})
        every = turns(found)
        stats = sheet()
        priced = every.ap_values(stats, 12)
        here = wakfu_value.value(found, LEVEL, stats, every)
        self.assertEqual(set(range(13)), set(priced))
        for ap in (3, 6, 9, 11, 12):
            moved = collections.Counter(stats, ap=ap)
            self.assertAlmostEqual(
                100 * (wakfu_value.value(found, LEVEL, moved, every) - here), priced[ap], 9)
        self.assertEqual(0.0, priced[11])
        self.assertEqual(wakfu_turn.NO_DAMAGE, priced[0])

    def test_the_damage_of_the_turns_is_the_damage_component(self):
        found = role('mixed', {'damage': 1, 'life': 0.5})
        every = turns(found)
        self.assertEqual(wakfu_value.components(found, LEVEL, sheet(), every)['damage'],
                         every.damage(sheet()))
        mule = wakfu_value.Role((), 'distance', shares={'mule': 1})
        self.assertEqual(1.0, wakfu_turn.RoleTurns(mule, LEVEL, {}).damage(sheet()))


Stat = collections.namedtuple('Stat', 'id key')
Piece = collections.namedtuple('Piece', 'id level type stats removed', defaults=(False,))
HELMET, RING, CAPE = 1, 2, 3
STAT_ID = {'tackle': 1, 'dodge': 2, 'init': 3, 'hp': 4}


class Catalogue:
    """The part of a Wakfu structure the scales read: a head, two ring slots and a back slot."""

    def __init__(self, *pieces):
        self.pieces = pieces

    def get_type_positions(self):
        return [(HELMET, 'HEAD'), (RING, 'LEFT_HAND'), (RING, 'RIGHT_HAND'), (CAPE, 'BACK')]

    def get_available_items_list(self):
        return list(self.pieces)

    def get_stat_by_key(self, key):
        return Stat(STAT_ID[key], key) if key in STAT_ID else None


def piece(item_id, type_id, level=50, removed=False, **stats):
    return Piece(item_id, level, type_id,
                 tuple((STAT_ID[key], value) for key, value in stats.items()), removed)


class TheScalesAreMeasuredFromTheItemsTests(SimpleTestCase):
    def catalogue(self):
        return Catalogue(
            piece(1, HELMET, tackle=30), piece(2, HELMET, tackle=50, dodge=10),
            piece(3, HELMET, level=90, tackle=500), piece(4, HELMET, removed=True, tackle=900),
            piece(5, RING, tackle=20), piece(6, RING, tackle=15),
            piece(7, CAPE, dodge=40, hp=300))

    def test_a_scale_is_the_sum_over_positions_of_the_highest_value_among_items_up_to_the_top(self):
        self.assertEqual(50 + 20 + 20, wakfu_value.stat_scale(self.catalogue(), 'tackle', 50))
        self.assertEqual(500 + 20 + 20, wakfu_value.stat_scale(self.catalogue(), 'tackle', 90))

    def test_a_removed_item_and_an_item_above_the_top_never_count(self):
        self.assertEqual(90, wakfu_value.stat_scale(self.catalogue(), 'tackle', 89))
        self.assertEqual(0, wakfu_value.stat_scale(Catalogue(piece(1, HELMET, level=60,
                                                                   tackle=5)), 'tackle', 50))

    def test_a_type_that_sits_in_two_positions_counts_in_both(self):
        self.assertEqual(40, wakfu_value.stat_scale(self.catalogue(), 'tackle', 50) - 50)

    def test_a_stat_the_game_does_not_have_has_no_scale(self):
        self.assertEqual(0, wakfu_value.stat_scale(self.catalogue(), 'wisdom', 50))

    def test_the_scales_of_a_bracket_are_those_of_lock_dodge_and_initiative(self):
        self.assertEqual({'tackle': 90, 'dodge': 50, 'init': 0},
                         wakfu_value.stat_scales(self.catalogue(), 50))

    def test_a_higher_bracket_never_has_a_smaller_scale(self):
        found = [wakfu_value.stat_scale(self.catalogue(), 'tackle', top) for top in (20, 50, 90)]
        self.assertEqual(sorted(found), found)
