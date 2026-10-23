from chardata.tests_wakfu_runes_enter_every_total_and_gate import MELEE, RED, ARuneCase
from fashionistapulp import wakfu_legality


class TheCheckerReadsTheRunesOfTheSetItIsGivenTests(ARuneCase):
    def test_a_set_holding_too_many_runes_is_refused_without_the_runes_argument(self):
        _build, worn = self.solve_runes({'melee_dmg': 1})
        worn.runes = dict(worn.runes, HEAD=[(RED, MELEE, 1)] * 5)
        found = wakfu_legality.violations(self.structure, 100, worn)
        self.assertEqual([wakfu_legality.RUNE_SOCKET], [rule for rule, _text in found])

    def test_the_runes_of_the_set_count_in_the_totals_when_none_are_passed(self):
        build, worn = self.solve_runes({'melee_dmg': 1})
        total = build.totals(worn)['melee_dmg']
        self.assertEqual([], wakfu_legality.violations(
            self.structure, 100, worn, minimums={'melee_dmg': total}))
        found = wakfu_legality.violations(self.structure, 100, worn,
                                          minimums={'melee_dmg': total + 1})
        self.assertEqual(['minimum'], [rule for rule, _text in found])

    def test_runes_passed_explicitly_replace_the_runes_of_the_set(self):
        _build, worn = self.solve_runes({'melee_dmg': 1})
        found = wakfu_legality.violations(self.structure, 100, worn, runes={})
        self.assertEqual([], found)

    def test_a_socket_of_colour_zero_is_reported_once(self):
        _build, worn = self.solve_runes({'hp': 1})
        found = wakfu_legality.violations(self.structure, 100, worn,
                                          runes={'HEAD': [(0, MELEE, 1)]})
        self.assertEqual([wakfu_legality.RUNE_SOCKET], [rule for rule, _text in found])
