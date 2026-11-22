# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An overed piece, an exo carrier and a TemporiX model take no transcendence rune."""

from fashionistapulp.model import Model
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.transcendence_terms import TRANSCENDENCE_VERSIONS

from chardata.dracorune_fixtures import BetaModelTestCase, SmallModel, piece, stat_id
from chardata.transcendence_fixtures import plain_input, trans_columns, trans_input


class AnOveredPieceAnExoCarrierAndTemporixTakeNoTranscendenceRuneTests(BetaModelTestCase):

    def test_an_overed_piece_and_an_exo_carrier_are_no_candidate(self):
        exo, overed, plain = (piece(name, {}) for name in ('Hat', 'Cloak', 'Amulet'))
        model = SmallModel([exo, overed, plain],
                           stat_overrides={exo.id: {stat_id('ap'): 1},
                                           overed.id: {stat_id('vit'): 50}})
        model.setup(trans_input({'vit': 1}, 7))
        self.assertEqual({plain.id}, set(model.transcendence_candidates))
        members = {item_id for ids in model.transcendence_classes.values() for item_id in ids}
        self.assertEqual({plain.id}, members)

    def test_temporix_writes_no_transcendence_column(self):
        for version in TRANSCENDENCE_VERSIONS:
            set_current_game_version(version)
            model = Model(temporix=True)
            with self.subTest(version=version):
                self.assertEqual({}, model.transcendence_candidates)
                model.setup(plain_input(7))
                self.assertEqual([], trans_columns(model))
