import collections
import contextlib
import inspect
import io
import json
import os
import pickle
from pathlib import Path
import sys
import tempfile
import types
from unittest import SkipTest, mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'itemscraper'))
import build_wakfu_db as builder

LEVEL = 100

HELMET, AMULET, CHEST, SHOULDERS, CLOAK, BELT, BOOTS, RING = range(9001, 9009)
SWORD, GREATSWORD, SHIELD, EMBLEM = 9009, 9010, 9011, 9012

TYPES = {
    HELMET: ('Helmet', ['HEAD']),
    AMULET: ('Amulet', ['NECK']),
    CHEST: ('Breastplate', ['CHEST']),
    SHOULDERS: ('Epaulettes', ['SHOULDERS']),
    CLOAK: ('Cloak', ['BACK']),
    BELT: ('Belt', ['BELT']),
    BOOTS: ('Boots', ['LEGS']),
    RING: ('Ring', ['LEFT_HAND', 'RIGHT_HAND']),
    SWORD: ('One-handed weapon', ['FIRST_WEAPON']),
    GREATSWORD: ('Two-handed weapon', ['FIRST_WEAPON']),
    SHIELD: ('Off hand', ['SECOND_WEAPON']),
    EMBLEM: ('Emblem', ['ACCESSORY']),
}

HELM_A, HELM_B, HELM_OVER, HELM_REMOVED = 1001, 1002, 1003, 1004
AMULET_A, AMULET_B, CHEST_A, SHOULDERS_A, CLOAK_A, BELT_A, BOOTS_A = (
    1010, 1011, 1020, 1030, 1040, 1050, 1060)
ALPHA_RARE, ALPHA_LEGENDARY, BETA, GAMMA = 1070, 1071, 1072, 1073
SWORD_A, SWORD_B, GREAT, SHIELD_A, DAGGER, EMBLEM_A = 1080, 1081, 1082, 1090, 1091, 1095
RELIC_HELM, RELIC_AMULET, EPIC_CHEST, EPIC_SHOULDERS = 1101, 1102, 1111, 1112
AP_HELM, AP_AMULET, AP_CHEST, MP_BELT, MP_BOOTS, WP_SHOULDERS, WP_CLOAK = (
    1201, 1202, 1203, 1211, 1212, 1221, 1222)
CRIT_HELM, CRIT_AMULET, CRIT_CHEST = 1301, 1302, 1303

RELICS = (RELIC_HELM, RELIC_AMULET)
EPICS = (EPIC_CHEST, EPIC_SHOULDERS)
CRIT_ITEMS = (CRIT_HELM, CRIT_AMULET, CRIT_CHEST)


def item(ident, type_id, name, level=50, rarity=3, french=None, two_handed=False,
         exclusive=None, **stats):
    return {
        'id': ident, 'name': {'en': name, 'fr': french or name + ' fr'}, 'level': level,
        'type_id': type_id, 'type_name': {'en': TYPES[type_id][0], 'fr': TYPES[type_id][0] + ' fr'},
        'positions': TYPES[type_id][1], 'disables': ['SECOND_WEAPON'] if two_handed else [],
        'rarity': rarity, 'set_id': None, 'gfx_id': 5000 + ident, 'two_handed': two_handed,
        'exclusive': exclusive,
        'lines': [{'stat': key.upper(), 'value': value} for key, value in stats.items()],
    }


CATALOGUE = [
    item(HELM_A, HELMET, 'Helm A', hp=100),
    item(HELM_B, HELMET, 'Helm B', hp=80),
    item(HELM_OVER, HELMET, 'Helm Over', level=LEVEL + 1, hp=900),
    item(HELM_REMOVED, HELMET, 'Helm Removed', hp=950),
    item(AMULET_A, AMULET, 'Amulet A', hp=90),
    item(AMULET_B, AMULET, 'Amulet B', hp=70),
    item(CHEST_A, CHEST, 'Chest A', hp=120),
    item(SHOULDERS_A, SHOULDERS, 'Shoulders A', hp=60),
    item(CLOAK_A, CLOAK, 'Cloak A', hp=50),
    item(BELT_A, BELT, 'Belt A', hp=40),
    item(BOOTS_A, BOOTS, 'Boots A', hp=45),
    item(ALPHA_RARE, RING, 'Alpha Ring', rarity=2, french='Anneau Alpha', hp=100),
    item(ALPHA_LEGENDARY, RING, 'Alpha Ring', rarity=4, french='Anneau Alpha', hp=120),
    item(BETA, RING, 'Beta Ring', french='Anneau Beta', hp=30),
    item(GAMMA, RING, 'Gamma Ring', french='Anneau Gamma', hp=20),
    item(SWORD_A, SWORD, 'Sword A', hp=100),
    item(SWORD_B, SWORD, 'Sword B', hp=90),
    item(GREAT, GREATSWORD, 'Great Sword', two_handed=True, hp=250),
    item(SHIELD_A, SHIELD, 'Shield A', hp=40),
    item(DAGGER, SHIELD, 'Dagger', hp=35),
    item(EMBLEM_A, EMBLEM, 'Emblem A', hp=30),
    item(RELIC_HELM, HELMET, 'Relic Helm', rarity=5, exclusive='relic', hp=400),
    item(RELIC_AMULET, AMULET, 'Relic Amulet', rarity=5, exclusive='relic', hp=380),
    item(EPIC_CHEST, CHEST, 'Epic Chest', rarity=7, exclusive='epic', hp=500),
    item(EPIC_SHOULDERS, SHOULDERS, 'Epic Shoulders', rarity=7, exclusive='epic', hp=450),
    item(AP_HELM, HELMET, 'Ap Helm', hp=1, ap=5),
    item(AP_AMULET, AMULET, 'Ap Amulet', hp=1, ap=5),
    item(AP_CHEST, CHEST, 'Ap Chest', hp=1, ap=5),
    item(MP_BELT, BELT, 'Mp Belt', hp=1, mp=5),
    item(MP_BOOTS, BOOTS, 'Mp Boots', hp=1, mp=5),
    item(WP_SHOULDERS, SHOULDERS, 'Wp Shoulders', hp=1, wp=14),
    item(WP_CLOAK, CLOAK, 'Wp Cloak', hp=1, wp=14),
    item(CRIT_HELM, HELMET, 'Crit Helm', hp=300, ferocity=-6),
    item(CRIT_AMULET, AMULET, 'Crit Amulet', hp=300, ferocity=-6),
    item(CRIT_CHEST, CHEST, 'Crit Chest', hp=300, ferocity=-6),
]


def ids(worn):
    return {one.id for one in worn.values()}


class InventedItemsCase(SimpleTestCase):
    """A Wakfu database of the items above, built the way update_data_wakfu builds the real one."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not builder.DOFUS_DB.exists():
            raise SkipTest('items.db absent, the Wakfu schema is copied from it')
        from fashionistapulp import structure as structure_module
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        cls.db = directory / 'items_wakfu.db'
        cls.build_db(directory, CATALOGUE)
        # A second build without the removed helm flags it removed, keeping its id
        cls.build_db(directory, [one for one in CATALOGUE if one['id'] != HELM_REMOVED])
        with mock.patch.object(structure_module, 'get_items_db_path', return_value=str(cls.db)):
            cls.structure = structure_module.Structure('wakfu')

    @classmethod
    def build_db(cls, directory, items):
        dump = directory / 'transformed_wakfu.json'
        dump.write_text(json.dumps({'version': '1.0', 'equipment': items}), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            builder.main(['--dump', str(dump), '--db', str(cls.db), '--out', str(directory / 'raw')])

    def solve(self, weights, forbidden=(), locked=(), minimums=None, full_set=True, level=LEVEL):
        from fashionistapulp.wakfu_model import WakfuBuild
        build = WakfuBuild(self.structure, level, weights, forbidden, full_set,
                           minimums=minimums, locked=locked)
        return build, build.build().solve()

    def by_id(self, ident):
        return self.structure.get_item_by_id(ident)

    def best_per_slot(self, weights, forbidden=(), level=LEVEL):
        """The item each slot would hold if no rule linked the slots."""
        from fashionistapulp.wakfu_model import WakfuBuild
        build = WakfuBuild(self.structure, level, weights, forbidden)
        best = {}
        for one, position in build._candidates():
            worth = build._worth(one)
            if position not in best or worth > best[position][0]:
                best[position] = (worth, one)
        return {position: one for position, (_worth, one) in best.items()}

    def stat(self, one, key):
        stat_id = self.structure.get_stat_by_key(key).id
        return sum(value for number, value in one.stats if number == stat_id)


class TheWakfuSolveObeysEverySlotAndItemRuleTests(InventedItemsCase):
    def test_every_worn_item_sits_in_a_slot_its_type_allows(self):
        _build, worn = self.solve({'hp': 1})
        allowed = collections.defaultdict(set)
        for type_id, position in self.structure.get_type_positions():
            allowed[type_id].add(position)
        self.assertGreaterEqual(len(worn), 11)
        for position, one in worn.items():
            self.assertIn(position, allowed[one.type], '%s in %s' % (one.name, position))

    def test_no_slot_holds_two_items(self):
        build, worn = self.solve({'hp': 1})
        result = build.problem.get_result()
        chosen = [name.split('_', 2)[2] for name, value in result.items() if (value or 0) > 0.5]
        self.assertEqual(len(chosen), len(set(chosen)), chosen)
        self.assertEqual(set(chosen), set(worn))

    def test_no_item_above_the_build_level_is_worn(self):
        self.assertGreater(self.by_id(HELM_OVER).level, LEVEL)
        self.assertEqual(HELM_OVER, self.best_per_slot({'hp': 1}, RELICS, LEVEL + 1)['HEAD'].id)
        _build, worn = self.solve({'hp': 1})
        self.assertNotIn(HELM_OVER, ids(worn))
        self.assertTrue(all(one.level <= LEVEL for one in worn.values()))

    def test_a_removed_item_is_never_worn_even_when_best(self):
        self.assertTrue(self.by_id(HELM_REMOVED).removed)
        self.assertGreater(self.stat(self.by_id(HELM_REMOVED), 'hp'),
                           max(self.stat(one, 'hp') for one in self.structure.get_available_items_list()
                               if one.level <= LEVEL and one.type == HELMET))
        _build, worn = self.solve({'hp': 1})
        self.assertNotIn(HELM_REMOVED, ids(worn))

    def test_a_forbidden_item_is_never_worn(self):
        _build, worn = self.solve({'hp': 1})
        taken = worn['HEAD'].id
        _build, again = self.solve({'hp': 1}, forbidden=[taken])
        self.assertNotIn(taken, ids(again))
        self.assertIn('HEAD', again)

    def test_two_rarities_of_one_ring_are_never_worn_together(self):
        self.assertEqual(self.by_id(ALPHA_RARE).localized_names['fr'],
                         self.by_id(ALPHA_LEGENDARY).localized_names['fr'])
        _build, worn = self.solve({'hp': 1})
        self.assertEqual({ALPHA_LEGENDARY, BETA}, {worn['LEFT_HAND'].id, worn['RIGHT_HAND'].id})

    def test_a_two_handed_weapon_leaves_the_second_weapon_slot_empty(self):
        _build, worn = self.solve({'hp': 1})
        self.assertEqual(GREAT, worn['FIRST_WEAPON'].id)
        self.assertNotIn('SECOND_WEAPON', worn)
        _build, one_handed = self.solve({'hp': 1}, forbidden=[GREAT])
        self.assertIn('SECOND_WEAPON', one_handed)

    def test_at_most_one_relic_and_one_epic_are_worn(self):
        best = self.best_per_slot({'hp': 1})
        self.assertEqual(2, sum('relic' in (one.flags or ()) for one in best.values()))
        self.assertEqual(2, sum('epic' in (one.flags or ()) for one in best.values()))
        _build, worn = self.solve({'hp': 1})
        self.assertEqual(1, sum('relic' in (one.flags or ()) for one in worn.values()))
        self.assertEqual(1, sum('epic' in (one.flags or ()) for one in worn.values()))


class TheWakfuSolveObeysTheStatRulesTests(InventedItemsCase):
    def test_ap_mp_and_wp_stay_at_or_under_their_caps(self):
        from fashionistapulp.wakfu_stats import BASE_VALUES, OUT_OF_COMBAT_CAPS
        weights = {'ap': 1, 'mp': 1, 'wp': 1}
        best = self.best_per_slot(weights)
        for name, cap in OUT_OF_COMBAT_CAPS.items():
            stacked = BASE_VALUES[name] + sum(self.stat(one, name.lower()) for one in best.values())
            self.assertGreater(stacked, cap, '%s would not reach its cap if stacked' % name)
        build, worn = self.solve(weights)
        totals = build.totals(worn)
        for name, cap in OUT_OF_COMBAT_CAPS.items():
            self.assertEqual(cap, totals[name.lower()], name)

    def test_the_gear_critical_hit_sum_stays_at_or_above_the_floor(self):
        from fashionistapulp.wakfu_stats import CRITICAL_HIT_FLOOR_PERCENT
        forbidden = RELICS + EPICS
        best = self.best_per_slot({'hp': 1}, forbidden)
        self.assertEqual(3, sum(one.id in CRIT_ITEMS for one in best.values()))
        build, worn = self.solve({'hp': 1}, forbidden=forbidden)
        gear = sum(self.stat(one, 'ferocity') for one in worn.values())
        self.assertGreaterEqual(gear, CRITICAL_HIT_FLOOR_PERCENT)
        self.assertEqual(1, sum(one.id in CRIT_ITEMS for one in worn.values()))


class TheWakfuSolveHonoursLocksTests(InventedItemsCase):
    def test_a_locked_item_is_worn(self):
        _build, worn = self.solve({'hp': 1}, locked=[(HELM_B, None)])
        self.assertEqual(HELM_B, worn['HEAD'].id)

    def test_a_locked_item_with_a_slot_sits_in_that_slot(self):
        _build, free = self.solve({'hp': 1})
        self.assertNotIn(GAMMA, ids(free))
        _build, worn = self.solve({'hp': 1}, locked=[(GAMMA, 'RIGHT_HAND')])
        self.assertEqual(GAMMA, worn['RIGHT_HAND'].id)

    def test_a_lock_above_the_level_is_refused_before_solving(self):
        from fashionistapulp.lpproblem import LpProblem2
        with mock.patch.object(LpProblem2, 'run', side_effect=AssertionError('solved')):
            with self.assertRaisesMessage(ValueError, 'locked item Helm Over is level 101, above the '
                                                      'build level 100'):
                self.solve({'hp': 1}, locked=[(HELM_OVER, None)])

    def test_a_lock_on_a_removed_a_forbidden_or_an_unknown_item_is_refused(self):
        for locked, forbidden, message in (
                ([(HELM_REMOVED, None)], (), 'is removed from the game'),
                ([(HELM_A, None)], [HELM_A], 'is forbidden'),
                ([(999999, None)], (), 'is not in the catalogue')):
            with self.subTest(message=message):
                with self.assertRaisesMessage(ValueError, message):
                    self.solve({'hp': 1}, forbidden=forbidden, locked=locked)

    def test_a_lock_in_a_slot_the_type_does_not_fit_is_refused(self):
        with self.assertRaisesMessage(ValueError, 'cannot sit in NECK'):
            self.solve({'hp': 1}, locked=[(HELM_A, 'NECK')])

    def test_two_locks_on_one_slot_are_refused(self):
        for locked in ([(HELM_A, 'HEAD'), (HELM_B, 'HEAD')], [(HELM_A, None), (HELM_B, None)]):
            with self.subTest(locked=locked):
                with self.assertRaisesMessage(ValueError, 'need the same slot'):
                    self.solve({'hp': 1}, locked=locked)

    def test_locking_two_rarities_of_one_ring_is_refused(self):
        with self.assertRaisesMessage(ValueError, 'one item in two rarities'):
            self.solve({'hp': 1}, locked=[(ALPHA_RARE, None), (ALPHA_LEGENDARY, None)])

    def test_locking_two_relics_or_a_two_handed_weapon_over_the_off_hand_is_refused(self):
        with self.assertRaisesMessage(ValueError, 'all relic items'):
            self.solve({'hp': 1}, locked=[(RELIC_HELM, None), (RELIC_AMULET, None)])
        with self.assertRaisesMessage(ValueError, 'is two-handed'):
            self.solve({'hp': 1}, locked=[(GREAT, None), (SHIELD_A, 'SECOND_WEAPON')])

    def test_locking_two_epics_is_refused(self):
        with self.assertRaisesMessage(ValueError, 'all epic items'):
            self.solve({'hp': 1}, locked=[(EPIC_CHEST, None), (EPIC_SHOULDERS, None)])

    def test_a_two_handed_lock_and_an_unpositioned_lock_of_an_off_hand_only_item_is_refused(self):
        for off_hand in (SHIELD_A, DAGGER):
            with self.subTest(off_hand=off_hand):
                with self.assertRaisesMessage(ValueError, 'is two-handed'):
                    self.solve({'hp': 1}, locked=[(GREAT, None), (off_hand, None)])

    def test_an_impossible_minimum_returns_no_set_and_says_infeasible(self):
        build, worn = self.solve({'hp': 1}, minimums={'hp': 10 ** 6})
        self.assertIsNone(worn)
        self.assertEqual('infeasible', build.reason)


def stopped_on_time(status):
    """LpProblem2.run that gives the solver's answer and then the status CBC leaves after its clock."""
    from fashionistapulp.lpproblem import LpProblem2
    real = LpProblem2.run
    calls = []

    def run(self, *args, **kwargs):
        calls.append(self)
        real(self, *args, **kwargs)
        status(self)

    return run, calls


class TheWakfuSolveDoesNotCallATimeoutAProofTests(InventedItemsCase):
    def test_a_search_that_closed_its_gap_is_proven(self):
        _build, worn = self.solve({'hp': 1})
        self.assertEqual('proven', worn.status)

    def test_a_timed_out_search_is_never_called_proven(self):
        import pulp
        from fashionistapulp.lpproblem import LpProblem2

        def found_not_proven(problem):
            problem.pulp_lp.sol_status = pulp.LpSolutionIntegerFeasible

        run, _calls = stopped_on_time(found_not_proven)
        with mock.patch.object(LpProblem2, 'run', run):
            build, worn = self.solve({'hp': 1})
        self.assertEqual('Solution Found', build.problem.get_solution_status())
        self.assertEqual('Optimal', build.problem.get_status(), 'PuLP relabels the timeout Optimal')
        self.assertEqual('time limit', worn.status)

    def test_a_timeout_without_a_set_is_not_reported_as_empty_slots(self):
        import pulp
        from fashionistapulp.lpproblem import LpProblem2

        def no_set(problem):
            problem.pulp_lp.status = pulp.LpStatusNotSolved

        run, calls = stopped_on_time(no_set)
        with mock.patch.object(LpProblem2, 'run', run):
            build, worn = self.solve({'hp': 1})
        self.assertIsNone(worn)
        self.assertEqual('time limit', build.reason)
        self.assertEqual(1, len(calls), 'the solve went on to a model that allows empty slots')
        self.assertTrue(build.full_set)
        self.assertIsNone(build.full_set_status)


class TheWakfuSolveBuildNeedsAnElementAndAReachTests(InventedItemsCase):
    def test_the_solve_refuses_to_run_without_an_element(self):
        from fashionistapulp import wakfu_solve
        for elements in (None, (), ''):
            with self.subTest(elements=elements):
                with self.assertRaisesMessage(ValueError, 'elements are required'):
                    wakfu_solve.solve_build(self.structure, level=LEVEL, elements=elements,
                                            reach='melee')
        with self.assertRaisesMessage(ValueError, 'reach is required'):
            wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',), reach=None)
        with self.assertRaisesMessage(ValueError, 'elements are fire, water, earth, air'):
            wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('light',), reach='melee')

    def test_the_solve_has_no_default_element_or_reach(self):
        from fashionistapulp import wakfu_solve
        parameters = inspect.signature(wakfu_solve.solve_build).parameters
        for name in ('elements', 'reach'):
            self.assertIs(inspect.Parameter.empty, parameters[name].default, name)

    def test_a_solve_returns_a_legal_set_with_its_status_and_what_it_does_not_count(self):
        from fashionistapulp import wakfu_legality, wakfu_solve
        result = wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',),
                                         reach='melee', seconds=60, allow_legacy=True)
        self.assertIsNotNone(result.worn)
        self.assertEqual([], wakfu_legality.violations(self.structure, LEVEL, result.worn))
        self.assertEqual('proven', result.status)
        self.assertIsNone(result.reason)
        self.assertLess(result.seconds, 60)
        for system in ('runes', 'sublimations', 'aptitudes', 'pets', 'mounts', 'lucky charms', 'states'):
            self.assertIn(system, result.not_counted)

    def test_a_solve_that_finds_no_set_says_why(self):
        from fashionistapulp import wakfu_solve
        # Three items of 5 AP each would put the character over the AP cap
        result = wakfu_solve.solve_build(
            self.structure, level=LEVEL, elements=('fire',), reach='melee', allow_legacy=True,
            locked=[(AP_HELM, None), (AP_AMULET, None), (AP_CHEST, None)])
        self.assertIsNone(result.worn)
        self.assertEqual('infeasible', result.reason)
        self.assertIsNone(result.status)

    def test_a_set_that_breaks_a_rule_is_never_returned(self):
        from fashionistapulp import wakfu_solve
        with mock.patch('fashionistapulp.wakfu_legality.violations',
                        return_value=[('level', 'made up')]):
            with self.assertRaises(wakfu_solve.WakfuIllegalSet) as caught:
                wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',),
                                        reach='melee', allow_legacy=True)
        self.assertEqual([('level', 'made up')], caught.exception.violations)

    def test_a_lock_beats_the_default_legacy_exclusion_and_a_forbid_beats_the_lock(self):
        from fashionistapulp import wakfu_solve
        with mock.patch('fashionistapulp.wakfu_solve.default_exclusions', return_value=[HELM_B]):
            result = wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',),
                                             reach='melee', locked=[(HELM_B, None)])
            self.assertEqual(HELM_B, result.worn['HEAD'].id)
            with self.assertRaisesMessage(ValueError, 'is forbidden'):
                wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',),
                                        reach='melee', locked=[(HELM_B, None)], forbidden=[HELM_B])


class TheWakfuModelStopsRoundsBeforeTheDeadlineTests(InventedItemsCase):
    ROLE_ELEMENTS = ('fire',)

    class FakeTime:
        def __init__(self):
            self.now = 1000.0

        def monotonic(self):
            return self.now

    def solve_with(self, seconds):
        import pulp  # noqa: F401
        from fashionistapulp import lpproblem, wakfu_value
        from fashionistapulp.lpproblem import LpProblem2
        clock = self.FakeTime()
        real = LpProblem2.run
        limits = []

        def run(problem, *args, **kwargs):
            limits.append(lpproblem.SOLVER.timeLimit)
            real(problem, *args, **kwargs)
            clock.now += 8

        role = wakfu_value.DamageDealer(self.ROLE_ELEMENTS, 'melee')
        before = lpproblem.SOLVER.timeLimit
        with mock.patch.object(wakfu_value, 'time', clock), \
                mock.patch.object(LpProblem2, 'run', run):
            deadline = None if seconds is None else clock.monotonic() + seconds
            model = wakfu_value.solve(self.structure, LEVEL, role, rounds=5, deadline=deadline)
        self.assertEqual(before, lpproblem.SOLVER.timeLimit, 'the solver limit was not restored')
        return model, limits

    def test_the_rounds_stop_before_the_deadline(self):
        free, limits = self.solve_with(None)
        self.assertGreaterEqual(len(free.rounds), 2, 'the catalogue settles in one round')
        self.assertEqual({90}, set(limits))
        model, limits = self.solve_with(15)
        self.assertEqual(1, len(model.rounds))
        self.assertFalse(model.converged)
        self.assertEqual([12], limits, 'CBC gets the time left minus the 3 s margin')

    def test_the_fallback_run_gets_the_time_left_and_not_the_first_run_limit(self):
        import pulp
        from fashionistapulp import lpproblem, wakfu_value
        from fashionistapulp.lpproblem import LpProblem2
        from fashionistapulp.wakfu_model import WakfuBuild
        clock = self.FakeTime()
        real = LpProblem2.run
        limits = []

        def run(problem, *args, **kwargs):
            limits.append(lpproblem.SOLVER.timeLimit)
            real(problem, *args, **kwargs)
            if len(limits) == 1:
                problem.pulp_lp.status = pulp.LpStatusInfeasible
                clock.now += 50

        build = WakfuBuild(self.structure, LEVEL, {'hp': 1})
        with mock.patch.object(wakfu_value, 'time', clock), \
                mock.patch.object(LpProblem2, 'run', run):
            worn = build.build().solve(clock.monotonic() + 60)
        self.assertIsNotNone(worn)
        self.assertFalse(build.full_set, 'the every-slot model was dropped')
        self.assertEqual([57, 7], limits)

    def test_a_deadline_with_room_for_every_round_changes_nothing(self):
        free, _limits = self.solve_with(None)
        model, _limits = self.solve_with(10 ** 6)
        self.assertEqual([one.ids for one in free.rounds], [one.ids for one in model.rounds])
        self.assertEqual(free.converged, model.converged)


class TheWakfuCheckerNamesEachRuleTests(InventedItemsCase):
    def violations(self, worn, **kwargs):
        from fashionistapulp import wakfu_legality
        return wakfu_legality.violations(self.structure, kwargs.pop('level', LEVEL), worn, **kwargs)

    def rules(self, worn, **kwargs):
        return {rule for rule, _text in self.violations(worn, **kwargs)}

    def test_the_checker_names_each_rule_on_a_hand_made_illegal_set(self):
        from fashionistapulp import wakfu_legality as rule
        one = self.by_id
        _build, legal = self.solve({'hp': 1})
        self.assertEqual([], self.violations(legal), 'the solver set is the control')
        cases = (
            (rule.SLOT, dict(legal, NECK=one(HELM_A)), {}),
            (rule.SLOT_COUNT, dict(legal, HEAD=[one(HELM_A), one(HELM_B)]), {}),
            (rule.LEVEL, dict(legal, HEAD=one(HELM_OVER)), {}),
            (rule.REMOVED, dict(legal, HEAD=one(HELM_REMOVED)), {}),
            (rule.FORBIDDEN, legal, {'forbidden': [legal['HEAD'].id]}),
            (rule.LOCK, legal, {'locked': [(HELM_B, None)]}),
            (rule.LOCK, legal, {'locked': [(legal['HEAD'].id, 'NECK')]}),
            (rule.SAME_ITEM, dict(legal, LEFT_HAND=one(ALPHA_RARE), RIGHT_HAND=one(ALPHA_LEGENDARY)), {}),
            (rule.TWO_HANDED, dict(legal, FIRST_WEAPON=one(GREAT), SECOND_WEAPON=one(SHIELD_A)), {}),
            (rule.RELIC, dict(legal, HEAD=one(RELIC_HELM), NECK=one(RELIC_AMULET)), {}),
            (rule.EPIC, dict(legal, CHEST=one(EPIC_CHEST), SHOULDERS=one(EPIC_SHOULDERS)), {}),
            (rule.CAP, dict(legal, HEAD=one(AP_HELM), NECK=one(AP_AMULET), CHEST=one(AP_CHEST)), {}),
            (rule.CAP, dict(legal, BELT=one(MP_BELT), LEGS=one(MP_BOOTS)), {}),
            (rule.CAP, dict(legal, SHOULDERS=one(WP_SHOULDERS), BACK=one(WP_CLOAK)), {}),
            (rule.CRITICAL_FLOOR, dict(legal, HEAD=one(CRIT_HELM), NECK=one(CRIT_AMULET)), {}),
            (rule.MINIMUM, legal, {'minimums': {'hp': 10 ** 6}}),
        )
        for name, worn, kwargs in cases:
            with self.subTest(rule=name, kwargs=sorted(kwargs)):
                found = self.violations(worn, **kwargs)
                self.assertIn(name, [rule_name for rule_name, _text in found], found)
                self.assertTrue(all(text for _rule, text in found))

    def test_a_legal_set_with_a_rule_met_exactly_at_its_limit_has_no_violation(self):
        one = self.by_id
        worn = {'HEAD': one(AP_HELM), 'NECK': one(AP_AMULET), 'BELT': one(MP_BELT),
                'SHOULDERS': one(WP_SHOULDERS), 'LEFT_HAND': one(BETA)}
        self.assertEqual([], self.violations(worn), 'AP 16, MP 8 and WP 20 are the caps themselves')
        worn['CHEST'] = one(CRIT_CHEST)
        self.assertEqual([], self.violations(worn), 'a crit sum of -6 is above the floor')

    def test_the_checker_does_not_import_the_solver(self):
        from fashionistapulp import wakfu_legality
        source = inspect.getsource(wakfu_legality)
        self.assertNotIn('WakfuBuild', source)
        self.assertNotIn('wakfu_model', source)

    def test_the_checker_reads_every_field_from_the_catalogue_and_not_from_the_object_given(self):
        from fashionistapulp import wakfu_legality as rule
        _build, legal = self.solve({'hp': 1})

        def posing_as(ident, **fields):
            real = self.by_id(ident)
            copy = types.SimpleNamespace(
                id=real.id, name=real.name, level=real.level, type=real.type, flags=real.flags,
                stats=real.stats, removed=real.removed, localized_names=real.localized_names)
            copy.__dict__.update(fields)
            return copy

        liars = (
            (rule.LEVEL, posing_as(HELM_OVER, level=1)),
            (rule.REMOVED, posing_as(HELM_REMOVED, removed=False)),
            (rule.SLOT, posing_as(AMULET_A, type=HELMET)),
        )
        for name, liar in liars:
            with self.subTest(rule=name):
                found = self.violations(dict(legal, HEAD=liar))
                self.assertIn(name, [one for one, _text in found], found)
        with self.subTest(rule=rule.RELIC):
            worn = dict(legal, HEAD=posing_as(RELIC_HELM, flags=()),
                        NECK=posing_as(RELIC_AMULET, flags=()))
            self.assertIn(rule.RELIC, self.rules(worn))
        with self.subTest(rule=rule.CAP):
            worn = dict(legal, HEAD=posing_as(AP_HELM, stats=[]), NECK=posing_as(AP_AMULET, stats=[]),
                        CHEST=posing_as(AP_CHEST, stats=[]))
            self.assertIn(rule.CAP, self.rules(worn))

    def test_an_item_id_missing_from_the_catalogue_is_a_violation(self):
        from fashionistapulp import wakfu_legality as rule
        _build, legal = self.solve({'hp': 1})
        stranger = types.SimpleNamespace(id=987654, name='Stranger', level=1, type=HELMET,
                                         flags=(), stats=[], removed=False, localized_names=None)
        found = self.violations(dict(legal, HEAD=stranger))
        self.assertIn(rule.UNKNOWN, [one for one, _text in found], found)
        self.assertTrue(all(text for _rule, text in found))


class TheWakfuIllegalSetSurvivesAProcessBoundaryTests(SimpleTestCase):
    def test_an_illegal_set_error_pickles_and_keeps_its_violations(self):
        from fashionistapulp import wakfu_solve
        error = wakfu_solve.WakfuIllegalSet([('cap', 'AP is 17'), ('lock', 'x is not worn')])
        again = pickle.loads(pickle.dumps(error))
        self.assertEqual(error.violations, again.violations)
        self.assertEqual(str(error), str(again))
        self.assertEqual('cap: AP is 17; lock: x is not worn', str(again))


class TheWakfuModelWritesTheSameProblemWithoutLocksTests(InventedItemsCase):
    def lp_bytes(self, **options):
        from fashionistapulp.wakfu_model import WakfuBuild
        build = WakfuBuild(self.structure, LEVEL, {'hp': 1, 'ap': 5, 'dmg_fire_percent': 2},
                           [HELM_B], minimums={'mp': 3}, **options)
        build.build()
        path = Path(self.temp.name) / 'case.lp'
        build.problem.pulp_lp.writeLP(str(path))
        return path.read_bytes()

    def test_no_lock_leaves_the_lp_file_unchanged(self):
        plain = self.lp_bytes()
        self.assertEqual(plain, self.lp_bytes(locked=()))
        self.assertEqual(plain, self.lp_bytes(locked=[]))

    def test_a_lock_adds_a_row_to_the_lp_file(self):
        plain = self.lp_bytes()
        locked = self.lp_bytes(locked=[(HELM_A, 'HEAD')])
        self.assertNotEqual(plain, locked)
        self.assertGreater(len(locked), len(plain))


class TheWakfuBuildCommandNeedsAnElementAndAReachTests(InventedItemsCase):
    def run_command(self, *args):
        out = io.StringIO()
        with mock.patch('fashionistapulp.fashionista_config.get_items_db_path',
                        return_value=str(self.db)), \
                mock.patch('fashionistapulp.structure.get_structure', return_value=self.structure):
            call_command('wakfu_build', *args, stdout=out, no_color=True)
        return out.getvalue()

    def test_the_command_refuses_to_run_without_elements_or_reach(self):
        for args, message in ((('--level', '100'), 'elements are required'),
                              (('--level', '100', '--elements', 'fire'), 'reach is required'),
                              (('--level', '100', '--reach', 'melee'), 'elements are required')):
            with self.subTest(args=args):
                with self.assertRaisesMessage(CommandError, message):
                    self.run_command(*args)

    def test_hand_weights_need_no_element_or_reach(self):
        out = self.run_command('--level', '100', '--weights', 'hp=1', '--allow-legacy')
        self.assertIn('proven best', out.splitlines())

    def test_the_command_prints_the_set_its_proof_and_what_it_leaves_out(self):
        out = self.run_command('--level', '100', '--elements', 'fire', '--reach', 'melee',
                               '--allow-legacy', '--lock', '%d@LEFT_HAND' % BETA)
        lines = out.splitlines()
        self.assertIn('proven best', lines)
        self.assertTrue(any(line.startswith('  LEFT_HAND') and 'Beta Ring' in line for line in lines), out)
        self.assertTrue(any(line.startswith('  systems the model leaves out: runes') for line in lines))

    def test_the_command_counts_the_legacy_items_the_solve_left_out_and_not_the_locked_one(self):
        with mock.patch('fashionistapulp.wakfu_solve.default_exclusions',
                        return_value=[HELM_B, AMULET_B]):
            out = self.run_command('--level', '100', '--elements', 'fire', '--reach', 'melee',
                                   '--lock', str(HELM_B))
        self.assertIn('leaving out 1 legacy items', out)

    def test_the_command_reports_a_set_that_missed_its_time_limit(self):
        import pulp
        from fashionistapulp.lpproblem import LpProblem2

        def found_not_proven(problem):
            problem.pulp_lp.sol_status = pulp.LpSolutionIntegerFeasible

        run, _calls = stopped_on_time(found_not_proven)
        with mock.patch.object(LpProblem2, 'run', run):
            out = self.run_command('--level', '100', '--weights', 'hp=1', '--allow-legacy')
        self.assertIn('best set found within the time limit', out.splitlines())
        self.assertNotIn('proven best', out)
        self.assertNotIn('optimal', out.lower())

    def test_the_command_refuses_a_lock_the_rules_cannot_honour_or_a_malformed_one(self):
        for lock, message in ((str(HELM_OVER), 'above the build level'),
                              ('x', '--lock takes an item id'),
                              ('%d@MOON' % HELM_A, 'not a slot')):
            with self.subTest(lock=lock):
                with self.assertRaisesMessage(CommandError, message):
                    self.run_command('--level', '100', '--weights', 'hp=1', '--lock', lock)


MIRROR_NEEDED = 'no Wakfu mirror: run update_data_wakfu.py'

# Properties Ankama does not name in itemProperties.json, reviewed by hand: id -> live gear items
# 4 sits on one epic and 9 on three relics (build 1.93.1.62); neither changes who may wear the item
REVIEWED_UNNAMED_PROPERTIES = {4: 1, 9: 3}

# Every key name anywhere in items.json of build 1.93.1.62; no field says who may wear an item
ITEM_KEYS_1_93_1_62 = frozenset((
    'actionId areaShape areaSize baseParameters bindType color definition description '
    'doubleBonusPosition effect en equipEffects es femaleGfxId fr gfxId graphicParameters id '
    'isEpic isRelic item itemSetId itemTypeId level maximumShardSlotNumber minimumShardSlotNumber '
    'params properties pt rarity shardLevelRequirement shardLevelingCurve shardsParameters '
    'slotColorPattern subEffects sublimationParameters title useCostAp useCostMp useCostWp '
    'useCriticalEffects useEffects useParameters useRangeMax useRangeMin useTestFreeCell useTestLos '
    'useTestNoBorderCell useTestOnlyLine useWorldTarget').split())

ITEM_LEVEL_KEYS = {
    'top': {'definition', 'title', 'description'},
    'definition': {'item', 'useEffects', 'useCriticalEffects', 'equipEffects'},
    'item': {'id', 'level', 'baseParameters', 'useParameters', 'graphicParameters', 'properties',
             'sublimationParameters', 'shardsParameters'},
    'baseParameters': {'itemTypeId', 'itemSetId', 'rarity', 'bindType', 'minimumShardSlotNumber',
                       'maximumShardSlotNumber'},
}


class RealWakfuDataCase(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from wakfu_mirror import current_build_dir
        folder = current_build_dir()
        self.folder = folder and Path(folder)
        if (not self.folder or not (self.folder / 'items.json').exists()
                or not os.path.exists(get_items_db_path('wakfu'))):
            self.skipTest(MIRROR_NEEDED)
        self.db_path = get_items_db_path('wakfu')

    def items(self):
        with open(self.folder / 'items.json', encoding='utf-8') as handle:
            return json.load(handle)


class TheWakfuItemDataHoldsNothingNobodyReviewedTests(RealWakfuDataCase):
    def test_every_property_on_live_gear_is_named_or_reviewed(self):
        import sqlite3
        with open(self.folder / 'itemProperties.json', encoding='utf-8') as handle:
            named = {entry['id'] for entry in json.load(handle)}
        connection = sqlite3.connect('file:%s?mode=ro' % self.db_path, uri=True)
        try:
            live = {ident for (ident,) in connection.execute('SELECT id FROM items WHERE removed = 0')}
        finally:
            connection.close()
        counts = collections.Counter()
        for entry in self.items():
            definition = entry['definition']['item']
            if definition['id'] in live:
                counts.update(set(definition['properties']))
        unnamed = {number: count for number, count in counts.items() if number not in named}
        self.assertEqual(REVIEWED_UNNAMED_PROPERTIES, unnamed,
                         'a property no one has read, or a changed count: review what it does')

    def test_items_json_carries_no_equip_criteria_field(self):
        entries = self.items()
        keys = set()

        def walk(node):
            if isinstance(node, dict):
                keys.update(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(entries)
        self.assertEqual(ITEM_KEYS_1_93_1_62, keys, 'new or missing item fields: read them')
        seen = collections.defaultdict(set)
        for entry in entries:
            seen['top'].update(entry)
            seen['definition'].update(entry['definition'])
            seen['item'].update(entry['definition']['item'])
            seen['baseParameters'].update(entry['definition']['item']['baseParameters'])
        self.assertEqual(ITEM_LEVEL_KEYS, dict(seen))


class TheRealClassTurnSolveIsLegalTests(RealWakfuDataCase):
    def test_the_real_class_turn_solve_passes_the_checker(self):
        from fashionistapulp import wakfu_legality, wakfu_solve
        from fashionistapulp.structure import get_structure
        from fashionistapulp.wakfu_exclusions import default_exclusions
        structure = get_structure('wakfu')
        # Ankama class id 8 is the Iop
        result = wakfu_solve.solve_build(structure, level=245, elements=('fire',), reach='melee',
                                         class_id=8, seconds=90)
        self.assertIsNotNone(result.worn)
        self.assertEqual([], wakfu_legality.violations(
            structure, 245, result.worn, forbidden=default_exclusions(structure),
            minimums=wakfu_solve.make_role(('fire',), 'melee').minimums()))
        self.assertIn(result.status, ('proven', 'time limit'))
        self.assertLess(result.seconds, 95)
        self.assertIsNotNone(result.turn)
