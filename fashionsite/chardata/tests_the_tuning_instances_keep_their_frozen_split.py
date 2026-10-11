# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The five instances of a cell, and which tune and which hold out, are a frozen function of the cell alone."""
import inspect
from collections import Counter
from itertools import combinations
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.management.commands import tune_weights
from chardata.weight_table import BANDS, SCENARIOS, grid_element_sets
from fashionistapulp.dofus_constants import CHARACTER_CLASSES, MAIN_STATS

#: moves only with GENERATOR_VERSION: change the plan, bump the version, pin the new digest
PINNED_SPLIT_DIGEST = 'fffd8f5a36e7f66105a9654c95a32dcbe480dae3'
PLAN = [('door', 'high', 'dev_a'), ('meta', 'mid', 'dev_a'), ('meta', 'high', 'dev_b'), ('door', 'mid', 'dev_b'),
        ('door', 'low', 'test')]


def _all_instances():
    return [instance for cell in tuning.lot1_cells() for instance in tuning.instances_for(cell)]


class TheSplitIsPinnedTests(SimpleTestCase):

    def test_the_digest_of_every_instance_is_the_pinned_one(self):
        self.assertEqual(PINNED_SPLIT_DIGEST, tuning.split_digest(_all_instances()))

    def test_the_generator_version_the_digest_belongs_to(self):
        self.assertEqual(1, tuning.GENERATOR_VERSION)

    def test_the_digest_does_not_depend_on_the_order_of_the_instances(self):
        instances = _all_instances()
        self.assertEqual(tuning.split_digest(instances), tuning.split_digest(instances[::-1]))
        self.assertEqual(tuning.split_digest(instances), tuning.split_digest(sorted(instances, key=str)))

    def test_moving_one_instance_to_the_other_fold_moves_the_digest(self):
        instances = _all_instances()
        moved = [instances[0]._replace(split='dev_b')] + instances[1:]
        self.assertNotEqual(tuning.split_digest(instances), tuning.split_digest(moved))

    def test_changing_a_tier_or_a_minimum_moves_the_digest(self):
        instances = _all_instances()
        for field, value in (('tier', 'low'), ('minimums', 'meta'), ('band', '230')):
            changed = [instances[0]._replace(**{field: value})] + instances[1:]
            with self.subTest(field=field):
                self.assertNotEqual(tuning.split_digest(instances), tuning.split_digest(changed))

    def test_dropping_an_instance_moves_the_digest(self):
        instances = _all_instances()
        self.assertNotEqual(tuning.split_digest(instances), tuning.split_digest(instances[1:]))


class TheFivePerCellTests(SimpleTestCase):

    def test_the_plan_is_two_dev_folds_of_two_and_one_held_out(self):
        self.assertEqual(PLAN, list(tuning.INSTANCE_PLAN))
        self.assertEqual({'dev_a': 2, 'dev_b': 2, 'test': 1}, Counter(split for _m, _t, split in tuning.INSTANCE_PLAN))
        self.assertEqual(('dev_a', 'dev_b'), tuning.DEV_SPLITS)

    def test_a_cell_has_its_five_instances_in_the_order_of_the_plan(self):
        cell = tuning.Cell('Iop', ('str',), 'plain', BANDS[0])
        instances = tuning.instances_for(cell)
        self.assertEqual(PLAN, [(i.minimums, i.tier, i.split) for i in instances])
        for instance in instances:
            self.assertEqual((cell.char_class, cell.elements, cell.scenario, cell.band),
                             (instance.char_class, instance.elements, instance.scenario, instance.band))

    def test_each_fold_has_a_door_instance_and_a_meta_instance_at_different_tiers(self):
        for split in tuning.DEV_SPLITS:
            rows = [(minimums, tier) for minimums, tier, planned in PLAN if planned == split]
            with self.subTest(split=split):
                self.assertEqual({'door', 'meta'}, {minimums for minimums, _tier in rows})
                self.assertEqual(2, len({tier for _minimums, tier in rows}))

    def test_the_held_out_instance_is_a_door_on_the_cheapest_tier(self):
        self.assertEqual(('door', 'low'), PLAN[4][:2])

    def test_the_first_instance_is_the_door_the_tiers_are_cut_from(self):
        self.assertEqual(('door', 'high', 'dev_a'), PLAN[0])
        self.assertEqual(0, tuning.TIER_FORBIDDEN['high'])

    def test_the_instance_key_names_the_cell_the_minimums_and_the_tier(self):
        instance = tuning.instances_for(tuning.Cell('Iop', ('str', 'int'), 'tank', BANDS[0]))[1]
        self.assertEqual('Iop/str+int/tank/200/meta/mid', tuning.instance_key(instance))

    def test_the_instance_keys_of_the_grid_are_all_different(self):
        keys = [tuning.instance_key(instance) for instance in _all_instances()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_the_meta_minimums_are_twelve_ap_and_six_mp(self):
        self.assertEqual({'AP': 12, 'MP': 6}, tuning.META_MINIMUMS)


class TheGridTests(SimpleTestCase):

    def test_the_grid_is_every_class_every_one_or_two_elements_and_every_scenario(self):
        cells = tuning.lot1_cells()
        self.assertEqual(len(CHARACTER_CLASSES) * 10 * len(SCENARIOS), len(cells))
        self.assertEqual(570, len(cells))
        self.assertEqual(10, len(grid_element_sets()))
        self.assertEqual({1: 4, 2: 6}, dict(Counter(len(played) for played in grid_element_sets())))
        duos = {played for played in grid_element_sets() if len(played) == 2}
        self.assertEqual(set(combinations(MAIN_STATS, 2)), duos)

    def test_the_grid_is_at_level_200_only(self):
        self.assertEqual({'200'}, {cell.band for cell in tuning.lot1_cells()})
        self.assertEqual(('200',), BANDS)

    def test_the_cells_are_grouped_by_class_number_of_elements_and_scenario(self):
        groups = tuning.groups_of(tuning.lot1_cells())
        self.assertEqual(len(CHARACTER_CLASSES) * 2 * len(SCENARIOS), len(groups))
        self.assertEqual({4, 6}, {len(group) for group in groups})
        for group in groups:
            self.assertEqual(1, len({(cell.char_class, len(cell.elements), cell.scenario) for cell in group}))

    def test_a_filter_keeps_only_the_cells_it_names(self):
        cells = tuning.lot1_cells(['Iop'], ['str', 'str+int'], ['plain'])
        self.assertEqual([('Iop', ('str',), 'plain'), ('Iop', ('str', 'int'), 'plain')],
                         [(cell.char_class, cell.elements, cell.scenario) for cell in cells])

    def test_a_cell_is_parsed_from_its_name(self):
        cell = tuning.parse_cell('Cra/int+agi/glasscannon')
        self.assertEqual(('Cra', ('int', 'agi'), 'glasscannon', '200'), tuple(cell))
        for text in ('Nobody/str/plain', 'Cra/str+str/plain', 'Cra/str/boss', 'Cra/agi+int/plain'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    tuning.parse_cell(text)


class TheInstancesReadOnlyDoorInputsTests(SimpleTestCase):

    def test_an_instance_holds_nothing_but_the_inputs_of_a_door(self):
        self.assertEqual(('char_class', 'elements', 'scenario', 'band', 'minimums', 'tier', 'split'),
                         tuning.Instance._fields)

    def test_the_minimums_and_the_tiers_are_the_ones_the_door_knows(self):
        self.assertEqual({'door', 'meta'}, {minimums for minimums, _tier, _split in tuning.INSTANCE_PLAN})
        self.assertEqual(set(tuning.TIER_FORBIDDEN), {tier for _minimums, tier, _split in tuning.INSTANCE_PLAN})

    def test_the_door_of_each_scenario_is_a_style_and_a_priority_of_the_setup_page(self):
        from chardata.presets import PRIORITY_BY_KEY, STYLE_BY_KEY
        for scenario in SCENARIOS:
            style, priority = tuning.SCENARIO_DOOR[scenario]
            self.assertIn(priority, PRIORITY_BY_KEY)
            self.assertTrue(style is None or style in STYLE_BY_KEY)
        for priority in tuning.GUARDED_PRIORITY.values():
            self.assertIn(priority, PRIORITY_BY_KEY)

    def test_no_reference_build_enters_the_tuner(self):
        for module in (tuning, tune_weights):
            source = inspect.getsource(module).lower()
            for word in ('huz', 'reference build', 'bench'):
                with self.subTest(module=module.__name__, word=word):
                    self.assertNotIn(word, source)

    def test_the_door_runner_builds_from_the_instance_alone(self):
        source = inspect.getsource(tuning.DoorRunner._build)
        for name in ('instance.char_class', 'instance.elements', 'instance.scenario', 'instance.minimums'):
            self.assertIn(name, source)
        for word in ('stats_weight', 'set_stats_weights', 'inclusions'):
            self.assertNotIn(word, source)

    def test_the_smoke_instances_are_two_cells_of_the_spec(self):
        self.assertEqual((('Iop', ('str',), 'glasscannon', 'door', 'high'), ('Cra', ('agi',), 'plain', 'meta', 'high')),
                         tuning.SMOKE_INSTANCES)
        self.assertEqual(2, tuning.DRY_ROUNDS)


class TheTiersTakeAwayTheHeaviestPiecesTests(SimpleTestCase):

    def test_high_forbids_nothing_mid_three_and_low_six(self):
        engine = SimpleNamespace(contributions={index: 100 - index for index in range(10)})
        self.assertEqual(set(), tuning.forbid_for('high', engine))
        self.assertEqual({0, 1, 2}, tuning.forbid_for('mid', engine))
        self.assertEqual({0, 1, 2, 3, 4, 5}, tuning.forbid_for('low', engine))

    def test_the_heaviest_by_contribution_not_by_id(self):
        engine = SimpleNamespace(contributions={5: 10.0, 1: 90.0, 9: 70.0, 3: 80.0, 2: 5.0, 4: 1.0, 6: 2.0, 7: 3.0})
        self.assertEqual({1, 3, 9}, tuning.forbid_for('mid', engine))

    def test_a_tie_goes_to_the_lower_id(self):
        engine = SimpleNamespace(contributions={4: 10.0, 2: 10.0, 3: 10.0, 1: 10.0})
        self.assertEqual({1, 2, 3}, tuning.forbid_for('mid', engine))

    def test_a_set_with_fewer_pieces_than_the_tier_forbids_all_of_them(self):
        engine = SimpleNamespace(contributions={1: 5.0, 2: 3.0})
        self.assertEqual({1, 2}, tuning.forbid_for('low', engine))

    def test_the_numbers_of_pieces_are_the_specs(self):
        self.assertEqual({'high': 0, 'mid': 3, 'low': 6}, tuning.TIER_FORBIDDEN)


class TheScenariosAreFixedTests(SimpleTestCase):

    def test_the_lambdas_are_the_chosen_ones(self):
        self.assertEqual({'plain': (0.25, 0.25, 0.4), 'glasscannon': (0.15, 0.15, 0.29), 'tank': (0.8, 1.0, 1.2)},
                         {name: (ends['lo'], ends['fit'], ends['hi']) for name, ends in tuning.SCENARIO_LAMBDA.items()})

    def test_each_scenario_has_a_lambda_and_a_door(self):
        self.assertEqual(set(SCENARIOS), set(tuning.SCENARIO_LAMBDA))
        self.assertEqual(set(SCENARIOS), set(tuning.SCENARIO_DOOR))
        self.assertEqual({'glasscannon', 'tank'}, set(tuning.GUARDED_PRIORITY))
