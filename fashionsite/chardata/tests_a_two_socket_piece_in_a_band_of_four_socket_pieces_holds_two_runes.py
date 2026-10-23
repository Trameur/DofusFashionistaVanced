from chardata.tests_wakfu_runes_enter_every_total_and_gate import (
    MELEE, NARROW_BOOTS, ARuneCase, socketed)
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import BOOTS, item

WIDE_BOOTS = 1404


class ATwoSocketPieceInABandOfFourSocketPiecesHoldsTwoRunesTests(ARuneCase):
    """Both pairs of boots are level 70, so they share the one band and its column bound."""

    WEIGHTS = {'melee_dmg': 1, 'hp': 1}

    @classmethod
    def catalogue(cls):
        return super().catalogue() + [
            socketed(item(NARROW_BOOTS, BOOTS, 'Narrow Boots', level=70, hp=500)),
            socketed(item(WIDE_BOOTS, BOOTS, 'Wide Boots', level=70, hp=500))]

    def filled(self, worn):
        return [socket for socket in worn.runes['LEGS'] if socket.rune is not None]

    def test_the_narrow_pair_holds_two_runes_while_the_band_column_allows_four(self):
        build, worn = self.solve_runes(self.WEIGHTS, locked=[(NARROW_BOOTS, None)])
        self.assertEqual(NARROW_BOOTS, worn['LEGS'].id)
        limits = {band: number for (position, band), number in build._rune_limits.items()
                  if position == 'LEGS'}
        self.assertEqual({4}, set(limits.values()))
        self.assertEqual(2, len(self.filled(worn)))
        self.assertEqual({MELEE}, {socket.rune for socket in self.filled(worn)})

    def test_the_wide_pair_holds_four_runes_in_the_same_band(self):
        _build, worn = self.solve_runes(self.WEIGHTS, locked=[(WIDE_BOOTS, None)])
        self.assertEqual(WIDE_BOOTS, worn['LEGS'].id)
        self.assertEqual(4, len(self.filled(worn)))
