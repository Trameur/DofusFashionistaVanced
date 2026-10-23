from chardata.tests_wakfu_runes_enter_every_total_and_gate import (
    DODGE, MELEE, NOTHING, ARuneCase, socketed)
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import BOOTS, item

DODGE_BOOTS = 1420


class ARuneNothingPricesStaysOutTests(ARuneCase):
    @classmethod
    def catalogue(cls):
        return super().catalogue() + [
            socketed(item(DODGE_BOOTS, BOOTS, 'Dodge Boots', hp=1, dodge=20))]

    def filled(self, worn):
        return {socket.rune for socket in self.socket_values(worn)}

    def test_with_weights_on_melee_only_no_socket_holds_a_rune_of_another_stat(self):
        build, worn = self.solve_runes({'melee_dmg': 1}, forbidden=[DODGE_BOOTS])
        self.assertEqual({MELEE}, self.filled(worn))
        self.assertEqual({MELEE}, {ident for _place, ident, _band in build._rune_columns})

    def test_with_no_weight_a_rune_stays_in_the_box_and_every_socket_is_empty(self):
        _build, worn = self.solve_runes({'hp': 1})
        self.assertEqual(set(), self.filled(worn))
        self.assertTrue(worn.runes)

    def test_a_rune_a_row_reads_is_offered_but_stays_out_when_the_gear_meets_the_row(self):
        build, worn = self.solve_runes({'melee_dmg': 1}, minimums={'dodge': 10},
                                       locked=[(DODGE_BOOTS, None)])
        self.assertIn(DODGE, {ident for _place, ident, _band in build._rune_columns})
        self.assertEqual({MELEE}, self.filled(worn))
        self.assertGreaterEqual(build.totals(worn)['dodge'], 10)

    def test_a_rune_the_game_gives_no_characteristic_is_never_offered(self):
        self.assertIsNone(self.structure.shards[NOTHING].stat)
        build, worn = self.solve_runes({'melee_dmg': 1, 'hp': 1, 'dodge': 1},
                                       minimums={'dodge': 5})
        self.assertNotIn(NOTHING, {ident for _place, ident, _band in build._rune_columns})
        self.assertNotIn(NOTHING, self.filled(worn))

    def test_a_socket_holds_the_rune_the_weights_pay_most_for(self):
        _build, worn = self.solve_runes({'melee_dmg': 1, 'dodge': 5}, forbidden=[DODGE_BOOTS])
        self.assertEqual({DODGE}, self.filled(worn))
        _build, worn = self.solve_runes({'melee_dmg': 5, 'dodge': 1}, forbidden=[DODGE_BOOTS])
        self.assertEqual({MELEE}, self.filled(worn))
