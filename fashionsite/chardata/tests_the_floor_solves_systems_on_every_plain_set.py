from chardata.tests_a_solve_that_picks_systems_is_worth_at_least_its_plain_set import (
    FloorCase)
from chardata.tests_wakfu_build_solves_on_the_damage_model import outfit

# Worth 9 and 8, the plain best first
TWO_SETS = [outfit(1, ap=3), outfit(2, ap=2)]
# Worth 11 on the first set, 15 on the second
LOCKED = [outfit(1, ap=5), outfit(2, ap=9)]


class TheFloorSolvesSystemsOnEveryPlainSetTests(FloorCase):
    def test_the_floor_is_the_best_locked_solve_over_every_plain_set(self):
        result = self.run_solve({'plain': TWO_SETS, 'locked': LOCKED,
                                 'joint': [outfit(3, ap=-1)]})
        self.assertEqual(15.0, result.rounds[0].value)
        self.assertEqual(frozenset({2}), result.rounds[0].ids)

    def test_the_first_systems_round_solves_at_the_totals_of_the_plain_set_the_floor_came_from(self):
        self.run_solve({'plain': TWO_SETS, 'locked': LOCKED, 'joint': [outfit(3, ap=-1)]})
        joint = next(build for build in self.solved if build.kind == 'joint')
        # AP 6 + 2 of the second plain set, not the plain best's 6 + 3
        self.assertEqual(8, joint.weights['point_ap'])

    def test_the_seeds_run_best_plain_value_first_then_descending(self):
        # Worth 7, 8 and 9 in the order the plain rounds find them
        self.run_solve({'plain': [outfit(1, ap=1), outfit(2, ap=2), outfit(3, ap=3)],
                        'locked': [outfit(1, ap=5), outfit(2, ap=5), outfit(3, ap=5)]})
        locked = [build.locked[0][0] for build in self.solved if build.kind == 'locked']
        self.assertEqual([3, 2, 1], locked[:3])

    def test_each_locked_solve_pins_the_pieces_of_its_own_plain_set(self):
        self.run_solve({'plain': TWO_SETS, 'locked': LOCKED, 'joint': [outfit(3, ap=-1)]})
        locked = [build.locked for build in self.solved if build.kind == 'locked']
        self.assertEqual([[(1, 'HEAD')], [(2, 'HEAD')]], [list(one) for one in locked])

    def test_a_plain_set_the_best_one_repeats_is_solved_once(self):
        self.run_solve({'plain': [outfit(1, ap=3), outfit(1, ap=3)], 'locked': LOCKED,
                        'joint': [outfit(3, ap=-1)]})
        self.assertEqual(1, self.kinds().count('locked'))

    def test_a_seed_after_the_first_needs_floor_seconds_left(self):
        from fashionistapulp import wakfu_value
        floor = wakfu_value.FLOOR_SECONDS
        for left, seeds in ((floor - 1, 1), (floor + 1, 2)):
            with self.subTest(left=left):
                # Two plain solves and the one that finds nothing, then the first locked solve
                self.run_solve({'plain': list(TWO_SETS), 'locked': list(LOCKED)},
                               deadline=100.0, clock=[0.0],
                               after=[0.0, 0.0, 0.0, 100.0 - left])
                self.assertEqual(seeds, self.kinds().count('locked'))

    def test_the_floor_locked_solves_are_pruned(self):
        self.run_solve({'plain': TWO_SETS, 'locked': LOCKED, 'joint': [outfit(3, ap=-1)]})
        locked = [build for build in self.solved if build.kind == 'locked']
        self.assertEqual(2, len(locked))
        self.assertTrue(all(build.pruned for build in locked))
