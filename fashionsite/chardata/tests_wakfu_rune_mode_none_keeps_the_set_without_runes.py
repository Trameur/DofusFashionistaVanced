import types

from chardata.tests_wakfu_runes_enter_every_total_and_gate import LEVEL, MELEE, ARuneCase
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    InventedItemsCase, ids)
from fashionistapulp import wakfu_runes, wakfu_value

WEIGHTS = {'melee_dmg': 1, 'hp': 1}


def worth(weights, totals):
    return sum(number * totals[key] for key, number in weights.items())


class TheRuneModeNoneKeepsTheSetWithoutRunesTests(ARuneCase):
    def test_none_and_the_default_build_no_rune_column_and_give_the_same_set(self):
        sets = []
        for runes in (None, 'none'):
            build = self.build(WEIGHTS, runes=runes)
            worn = build.build().solve()
            self.assertEqual([], self.rune_columns(build), runes)
            self.assertEqual({}, worn.runes, runes)
            sets.append((ids(worn), build.totals(worn)))
        self.assertEqual(sets[0], sets[1])
        from fashionistapulp.wakfu_model import WakfuBuild
        plain = WakfuBuild(self.structure, LEVEL, WEIGHTS)
        worn = plain.build().solve()
        self.assertEqual(sets[0], (ids(worn), plain.totals(worn)))

    def test_the_set_of_the_none_mode_carries_its_mode_and_no_socket(self):
        _build, worn = self.solve_runes(WEIGHTS, runes='none')
        self.assertEqual('none', worn.rune_mode)
        self.assertEqual({}, worn.runes)
        _build, optimistic = self.solve_runes(WEIGHTS)
        self.assertEqual('optimistic', optimistic.rune_mode)

    def test_a_tier_cap_of_zero_is_the_none_mode(self):
        build = self.build(WEIGHTS, rune_tier=0)
        worn = build.build().solve()
        self.assertEqual([], self.rune_columns(build))
        self.assertEqual({}, worn.runes)
        self.assertEqual('none', worn.rune_mode)

    def test_the_optimistic_mode_is_worth_at_least_the_none_mode_on_the_same_case(self):
        none_build, none_worn = self.solve_runes(WEIGHTS, runes='none')
        build, worn = self.solve_runes(WEIGHTS)
        self.assertGreaterEqual(worth(WEIGHTS, build.totals(worn)),
                                worth(WEIGHTS, none_build.totals(none_worn)))
        self.assertGreater(build.totals(worn)['melee_dmg'],
                           none_build.totals(none_worn)['melee_dmg'])

    def test_a_mode_the_solver_does_not_have_is_refused(self):
        for runes in ('pessimistic', '', 3, True):
            with self.subTest(runes=runes):
                with self.assertRaises(ValueError):
                    self.build(WEIGHTS, runes=runes)

    def test_a_tier_the_rune_table_does_not_have_is_refused(self):
        for tier in (-1, 5, 2.5, True, '3'):
            with self.subTest(tier=tier):
                with self.assertRaises(ValueError):
                    self.build(WEIGHTS, rune_tier=tier)
        self.assertEqual(4, self.build(WEIGHTS, rune_tier=4).rune_tier)

    def test_the_solve_api_says_when_the_runes_are_left_out_and_when_they_are_counted(self):
        from fashionistapulp import wakfu_solve
        kept = wakfu_solve.solve_weights(self.structure, level=LEVEL, weights=WEIGHTS,
                                         allow_legacy=True, seconds=60)
        self.assertNotIn('runes', ' '.join(kept.not_counted))
        self.assertEqual('optimistic', kept.rune_mode)
        self.assertTrue(kept.runes)
        left = wakfu_solve.solve_weights(self.structure, level=LEVEL, weights=WEIGHTS,
                                         allow_legacy=True, seconds=60, runes='none')
        self.assertIn('runes (left out by the mode)', left.not_counted)
        self.assertEqual({}, dict(left.runes))
        self.assertEqual('none', left.rune_mode)
        for bad in ({'runes': 'sometimes'}, {'rune_tier': 99}, {'rune_tier': -1}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    wakfu_solve.solve_weights(self.structure, level=LEVEL, weights=WEIGHTS,
                                              allow_legacy=True, seconds=60, **bad)

    def test_a_cap_is_kept_on_the_result_and_every_socket_obeys_it(self):
        from fashionistapulp import wakfu_solve
        capped = wakfu_solve.solve_weights(self.structure, level=LEVEL, weights=WEIGHTS,
                                           allow_legacy=True, seconds=60, rune_tier=1)
        self.assertEqual(1, capped.rune_tier)
        self.assertEqual({1}, {socket.tier for sockets in capped.runes.values()
                               for socket in sockets if socket.rune is not None})

    def test_a_damage_solve_counts_the_runes_by_default(self):
        from fashionistapulp import wakfu_solve
        result = wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',),
                                         reach='melee', seconds=60, allow_legacy=True)
        self.assertEqual('optimistic', result.rune_mode)
        self.assertTrue(any(socket.rune == MELEE for sockets in result.runes.values()
                            for socket in sockets))
        none = wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',),
                                       reach='melee', seconds=60, allow_legacy=True,
                                       runes='none', sublimations='none')
        self.assertEqual({}, dict(none.runes))
        self.assertGreaterEqual(result.value, none.value)


class TwoRoundsThatDifferOnlyByTheirRunesAreNotSettledTests(ARuneCase):
    def round(self, runes):
        _build, worn = self.solve_runes(WEIGHTS)
        worn.runes = runes
        return wakfu_value.ModelRound({}, None, worn, {}, 0.0)

    def test_the_key_of_a_round_holds_the_runes_with_their_tier_and_count(self):
        _build, worn = self.solve_runes(WEIGHTS)
        round_ = wakfu_value.ModelRound({}, None, worn, {}, 0.0)
        ids_, points, runes = round_.key[:3]
        self.assertEqual(round_.ids, ids_)
        self.assertEqual(len(worn.runes), len({position for position, _r, _t, _c in runes}))
        self.assertTrue(all(count == 4 for _p, _r, _t, count in runes))

    def test_two_rounds_with_the_same_pieces_and_other_runes_have_other_keys(self):
        socket = wakfu_runes.Socket
        one = self.round({'HEAD': (socket(0, 1, MELEE, 2, 6, True, 3),)})
        same = self.round({'HEAD': (socket(0, 1, MELEE, 2, 6, True, 3),)})
        other_tier = self.round({'HEAD': (socket(0, 1, MELEE, 1, 2, True, 1),)})
        other_count = self.round({'HEAD': (socket(0, 1, MELEE, 2, 6, True, 3),
                                           socket(1, 1, MELEE, 2, 6, True, 3))})
        empty = self.round({'HEAD': (socket(0, None, None, None, 0, False, 0),)})
        self.assertEqual(one.key, same.key)
        self.assertEqual(4, len({one.key, other_tier.key, other_count.key, empty.key}))
        self.assertEqual(one.ids, other_tier.ids)


class ADatabaseWithoutRuneTablesSolvesWithoutRunesTests(InventedItemsCase):
    def test_the_optimistic_mode_finds_nothing_to_place_and_says_so(self):
        from fashionistapulp import wakfu_solve
        self.assertEqual({}, self.structure.shards)
        result = wakfu_solve.solve_weights(self.structure, level=LEVEL, weights={'hp': 1},
                                           allow_legacy=True, seconds=60)
        self.assertEqual({}, dict(result.runes))
        self.assertIn('runes (the database holds no rune table)', result.not_counted)
        build, worn = self.solve({'hp': 1})
        self.assertEqual({}, worn.runes)

    def test_a_tier_cap_needs_no_rune_table_to_be_a_whole_number(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        self.assertEqual(3, WakfuBuild(self.structure, LEVEL, {'hp': 1}, runes='optimistic',
                                       rune_tier=3).rune_tier)
        with self.assertRaises(ValueError):
            WakfuBuild(self.structure, LEVEL, {'hp': 1}, runes='optimistic', rune_tier=-2)
