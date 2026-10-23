import os
import sqlite3
import sys

from django.test import SimpleTestCase

from fashionistapulp import wakfu_aptitudes as apt
from fashionistapulp.wakfu_criteria import CriteriaError
from fashionistapulp.wakfu_db import EffectRow

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import get_items_wakfu  # noqa: E402

LEVEL = 245

ONE_PER_POINT = {
    1: [('hp_percent', 4)], 16: [('res_in_percent', 10)], 23: [('dmg_in_percent', 5)],
    26: [('melee_dmg', 8)], 30: [('ranged_dmg', 8)], 31: [('hp', 20)],
    18: [('tackle', 6)], 19: [('dodge', 6)], 20: [('init', 4)],
    21: [('dodge', 4), ('tackle', 4)], 37: [('willpower', 1)], 9: [('ferocity', 1)],
    10: [('block', 1)], 11: [('critical_bonus', 4)], 12: [('backstab_bonus', 6)],
    13: [('berserk_dmg', 8)], 14: [('heal_in_percent', 6)], 15: [('res_backstab', 4)],
    34: [('critical_res', 4)], 2: [('ap', 1)], 3: [('mp', 1), ('dmg_in_percent', 20)],
    4: [('range', 1), ('dmg_in_percent', 40)], 5: [('wp', 2)],
    6: [('armor_given_percent', 20)], 8: [('final_dmg_in_percent', 10)],
    35: [('res_in_percent', 50)], 38: [('final_heal_in_percent', 10)],
    39: [('dmg_in_percent', 40)],
}
COUNT_NOTHING = (17, 27, 36)
BATTLEGROUND_SETS = range(620, 635)

_cache = {}


def structure():
    if 'structure' not in _cache:
        from fashionistapulp.fashionista_config import get_items_db_path
        found = None
        if os.path.exists(get_items_db_path('wakfu')):
            from fashionistapulp.structure import Structure
            found = Structure('wakfu')
            if not found.aptitude_abilities:
                found = None
        _cache['structure'] = found
    return _cache['structure']


def query(sql, *args):
    from fashionistapulp.fashionista_config import get_items_db_path
    conn = sqlite3.connect('file:%s?mode=ro' % get_items_db_path('wakfu'), uri=True)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


class Fake:
    """A structure with invented raw rows."""

    def __init__(self, effects, groups=(), texts=None, states=None):
        self.aptitude_effects = {effect.id: effect for effect in effects}
        self.aptitude_effect_groups = dict(groups)
        self.aptitude_action_texts = dict(texts or {})
        self.aptitude_state_roots = dict(states or {})
        self.aptitude_abilities = {}
        self.aptitude_categories = {}
        self.items_dict = {}

    def get_stat_by_key(self, key):
        return None

    def get_type_positions(self):
        return []


def raw(ident, action, params=(0, 1), criterion='', container_type='GROUP'):
    return EffectRow(ident, action, container_type, 1, 'NORMAL', list(params), criterion)


STAT_TEXT = {120: '[#charac AP] [#1] Action Points'}


class TheAptitudeLinesFollowTheEffectWalkTests(SimpleTestCase):
    def setUp(self):
        self.structure = structure()
        if self.structure is None:
            self.skipTest('no Wakfu database with the aptitude tables')

    def test_the_per_point_table_is_the_designed_one(self):
        table = apt.table(self.structure, LEVEL, False)
        counted = {ident: lines for ident, (_c, _cap, lines, _n) in table.abilities.items()
                   if lines}
        self.assertEqual(ONE_PER_POINT, counted)
        self.assertEqual(sorted(COUNT_NOTHING), sorted(
            ident for ident, entry in table.abilities.items() if not entry[2]))
        self.assertEqual(31, len(table.abilities))

    def test_a_characteristic_the_client_does_not_name_is_reported_not_counted(self):
        notes = apt.table(self.structure, LEVEL, False).abilities[39][3]
        self.assertEqual(['action 39: characteristic 101 is not named'], notes)

    def test_every_line_is_a_whole_number_per_point(self):
        for ident, (_category, _cap, lines, _notes) in apt.table(
                self.structure, LEVEL, False).abilities.items():
            for key, value in lines:
                self.assertIsInstance(value, int, (ident, key))
        walked = [apt.walk(self.structure, apt._ability_roots(self.structure, ident), 1,
                           LEVEL, False) for ident in self.structure.aptitude_abilities]
        for one in walked:
            for line in one.lines:
                params = self.structure.aptitude_effects[line.effect].params
                self.assertEqual(0, params[0], line)
                self.assertEqual(params[1], int(params[1]), line)

    def test_a_line_scales_exactly_with_the_points_up_to_the_cap(self):
        table = apt.table(self.structure, LEVEL, False)
        for ident, (_category, cap, lines, _notes) in table.abilities.items():
            roots = apt._ability_roots(self.structure, ident)
            for points in range(cap + 1):
                got = [(line.key.lower(), line.value) for line in apt.walk(
                    self.structure, roots, points, LEVEL, False).lines]
                want = [(key, per * points) for key, per in lines]
                self.assertEqual(want, got, (ident, points))

    def test_budgets_count_the_unlock_levels_reached(self):
        wanted = {20: (5, 5, 5, 4, 0), 110: (28, 27, 27, 27, 2),
                  200: (50, 50, 50, 49, 4), 245: (62, 62, 62, 62, 5)}
        for level, counts in wanted.items():
            got = apt.budgets(self.structure, level)
            self.assertEqual(counts, tuple(got[category] for category in (2, 3, 4, 5, 6)))

    def test_an_ability_with_no_record_has_no_cap(self):
        listed = {24, 25, 32, 33}
        caps = apt.caps(self.structure, LEVEL)
        self.assertEqual(set(), listed & set(caps))
        self.assertEqual(set(self.structure.aptitude_abilities), set(caps))
        self.assertEqual(1, caps[2])
        self.assertEqual(10, caps[16])
        self.assertEqual(62, caps[23])

    def test_every_stored_criterion_classifies_at_every_level(self):
        texts = {effect.criterion for effect in self.structure.aptitude_effects.values()
                 if effect.criterion.strip()}
        stored = query("SELECT COUNT(*) FROM effects WHERE root_container_type"
                       " IN ('ABILITY', 'SET') AND criterion != ''")[0][0]
        self.assertEqual(58, stored)
        self.assertGreater(len(texts), 10)
        for level in range(1, LEVEL + 1):
            bound = apt.hp_bound(self.structure, level)
            for battleground in (True, False):
                for text in texts:
                    verdict = apt.criterion_holds(text, level, battleground, bound)
                    self.assertIn(verdict, (True, False, apt.FIGHT), (level, text))

    def test_the_untagged_leaves_are_exactly_the_reviewed_ones(self):
        self.assertEqual(set(apt.REVIEWED_UNTAGGED) | set(apt.NOT_A_STAT),
                         apt.untagged_actions(self.structure))

    def test_every_counted_leaf_names_the_stat_the_scraper_names(self):
        texts = self.structure.aptitude_action_texts
        checked = 0
        for effect in self.structure.aptitude_effects.values():
            if effect.action in apt.REVIEWED_UNTAGGED:
                continue
            ours, _sign = apt._characteristic(self.structure, effect)
            theirs, _value = get_items_wakfu.characteristic(
                effect.action, texts.get(effect.action), effect.params)
            self.assertEqual(theirs, ours, effect)
            checked += ours is not None
        self.assertGreater(checked, 40)

    def test_the_hp_bound_stays_under_the_threshold_of_ability_36(self):
        self.assertEqual(52819, apt.hp_bound(self.structure, LEVEL))
        self.assertLess(apt.hp_bound(self.structure, LEVEL), 80000)

    def test_no_set_tier_gives_hp(self):
        for level in (80, 110, 140, 170, 200):
            tiers = apt.table(self.structure, level, True).tiers
            self.assertTrue(tiers, level)
            for lines in tiers.values():
                self.assertNotIn('hp', [key for key, _value in lines])
                self.assertNotIn('hp_percent', [key for key, _value in lines])

    def test_the_client_set_members_are_the_items_of_the_battleground_sets(self):
        total = 0
        for item_set in BATTLEGROUND_SETS:
            ours = sorted(self.structure.aptitude_set_members[item_set])
            held = sorted(row[0] for row in query(
                'SELECT id FROM items WHERE item_set = ?', item_set))
            self.assertEqual(held, ours, item_set)
            total += len(ours)
        self.assertEqual(228, total)

    def test_no_battleground_set_member_carries_a_stat_gate(self):
        for item_set in BATTLEGROUND_SETS:
            for item_id in self.structure.aptitude_set_members[item_set]:
                item = self.structure.get_item_by_id(item_id)
                self.assertEqual([], list(item.max_stats_to_equip), item_id)
                self.assertEqual([], list(item.min_stats_to_equip), item_id)

    def test_a_battleground_bracket_gives_its_tiers_only_inside_a_battleground(self):
        inside = apt.table(self.structure, 80, True)
        self.assertEqual({(set_id, pieces) for set_id in (620, 621, 622)
                          for pieces in (3, 6)}, set(inside.tiers))
        self.assertEqual({}, apt.table(self.structure, 80, False).tiers)
        beyond = apt.table(self.structure, 81, True)
        self.assertEqual(set(), {key[0] for key in beyond.tiers} & {620, 621, 622})

    def test_a_tier_carries_the_lines_of_its_bracket(self):
        tiers = apt.table(self.structure, 80, True).tiers
        self.assertEqual([('ferocity', 10), ('backstab_bonus', 50), ('dodge', 50)],
                         tiers[(620, 3)])
        self.assertEqual([('final_dmg_in_percent', 10), ('dmg_in_percent', 50),
                          ('dodge', 50)], tiers[(620, 6)])
        self.assertEqual([('range', 1), ('willpower', 10)], tiers[(621, 3)])
        self.assertEqual([('tackle', 50)], tiers[(622, 6)])

    def test_a_set_lists_its_members_by_title(self):
        members = apt.table(self.structure, 80, True).members
        self.assertEqual(8, len(members[620]))
        self.assertEqual(sorted(self.structure.aptitude_set_members[620]),
                         sorted(item for one in members[620] for item in one))


class TheWalkOnInventedRowsTests(SimpleTestCase):
    def walk(self, effects, groups, texts=None, level=50, battleground=False):
        fake = Fake(effects, groups, texts if texts is not None else STAT_TEXT)
        return apt.walk(fake, [effects[0].id], 3, level, battleground)

    def test_a_false_criterion_skips_its_whole_subtree(self):
        for criterion, expected in (('False', 0), ('', 3)):
            walked = self.walk([raw(1, 330, criterion=criterion), raw(2, 120, (0, 1))],
                               {1: [2]})
            self.assertEqual(expected, sum(line.value for line in walked.lines), criterion)

    def test_a_criterion_on_the_level_and_the_option_is_evaluated(self):
        text = 'IsBattleground() and GetLevel("target") <= 80'
        rows = [raw(1, 330, criterion=text), raw(2, 120, (0, 1))]
        held = self.walk(rows, {1: [2]}, level=80, battleground=True)
        self.assertEqual([3], [line.value for line in held.lines])
        self.assertEqual([], self.walk(rows, {1: [2]}, level=81, battleground=True).lines)
        self.assertEqual([], self.walk(rows, {1: [2]}, level=80, battleground=False).lines)

    def test_a_fight_time_criterion_counts_nothing_below_it(self):
        text = 'GetTeamId("triggeringTarget") == GetTeamId("triggeringCaster")'
        walked = self.walk([raw(1, 330, criterion=text), raw(2, 120, (0, 1))], {1: [2]})
        self.assertEqual([], walked.lines)
        self.assertEqual(1, len(walked.notes))

    def test_an_unknown_criterion_function_raises(self):
        with self.assertRaises(CriteriaError):
            self.walk([raw(1, 330, criterion='Frobnicate()'), raw(2, 120)], {1: [2]})

    def test_an_untagged_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            self.walk([raw(1, 330), raw(2, 777)], {1: [2]})

    def test_a_leaf_counts_its_value_at_the_points(self):
        walked = self.walk([raw(1, 330), raw(2, 120, (0, 4))], {1: [2]})
        self.assertEqual([('AP', 12)], [(line.key, line.value) for line in walked.lines])

    def test_a_malus_template_counts_negative(self):
        walked = self.walk([raw(1, 120, (0, 4))], {}, {120: '-[#charac AP] [#1]'})
        self.assertEqual([('AP', -12)], [(line.key, line.value) for line in walked.lines])

    def test_an_action_that_never_counts_and_a_dropped_subtree_count_nothing(self):
        rows = [raw(1, 330), raw(2, 400), raw(3, 999), raw(4, 120, (0, 1))]
        walked = self.walk(rows, {1: [2, 3], 3: [4]})
        self.assertEqual([], walked.lines)
        self.assertEqual(['action 999: recomputes its level in the fight'], walked.notes)

    def test_an_applied_state_is_walked(self):
        fake = Fake([raw(1, 304, (55, 0)), raw(2, 120, (0, 2))], texts=STAT_TEXT,
                    states={55: [2]})
        walked = apt.walk(fake, [1], 3, 50, False)
        self.assertEqual([('AP', 6)], [(line.key, line.value) for line in walked.lines])

    def test_an_hp_criterion_that_depends_on_the_build_raises(self):
        with self.assertRaises(CriteriaError):
            apt.criterion_holds('GetCharac("HP", "target") < 1000', 50, False, 5000)
        self.assertTrue(apt.criterion_holds('GetCharac("HP", "target") < 80000', 50, False,
                                            5000))
        self.assertFalse(apt.criterion_holds('GetCharac("HP", "target") >= 80000', 50,
                                             False, 5000))
