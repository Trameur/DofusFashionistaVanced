from django.test import SimpleTestCase

from chardata.wakfu_invented_sublimations import (
    EPIC_RARITY, RELIC_RARITY, Piece, Structure, block, socket_row, state, use_block)
from fashionistapulp import wakfu_legality, wakfu_sublimations

RELIC, EPIC, NORMAL, OTHER_RELIC, OTHER_EPIC = 14186, 24130, 100, 14187, 24131
SUBLIMATIONS = {RELIC: (1, 1, 'relic', ()), OTHER_RELIC: (1, 1, 'relic', ()),
                EPIC: (1, 1, 'epic', ()), OTHER_EPIC: (1, 1, 'epic', ()),
                NORMAL: (1, 1, 'normal', ())}
# The legacy epic item of the database: the epic flag, and rarity 0
LEGACY_EPIC = 18691


def pieces():
    return {
        'relic': Piece(20, 1, rarity=RELIC_RARITY),
        'epic': Piece(21, 2, rarity=EPIC_RARITY),
        'other relic': Piece(22, 3, rarity=RELIC_RARITY),
        'other epic': Piece(23, 4, rarity=EPIC_RARITY),
        'legacy': Piece(LEGACY_EPIC, 5, rarity=0, flags=['epic']),
        'plain': Piece(25, 1, rarity=3),
    }


class ASpecialSublimationNeedsItsRarityTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block(states={1: state()}, sublimations=SUBLIMATIONS))
        self.pieces = pieces()
        self.structure = Structure(list(self.pieces.values()))

    def rules(self, worn, specials=None, sublimations=None):
        worn = {position: self.pieces[name] for position, name in worn.items()}
        runes = {position: socket_row() for position in worn}
        found = wakfu_legality.violations(
            self.structure, 100, worn, class_id=1, specials=specials,
            sublimations=sublimations, runes=runes)
        return [rule for rule, _text in found]

    def test_an_epic_sublimation_on_an_epic_piece_is_legal(self):
        self.assertEqual([], self.rules({'NECK': 'epic'}, specials={'NECK': EPIC}))

    def test_an_epic_sublimation_on_the_legacy_item_with_the_epic_flag_is_flagged(self):
        self.assertEqual([wakfu_legality.SUBLIMATION_RARITY],
                         self.rules({'LEGS': 'legacy'}, specials={'LEGS': EPIC}))

    def test_an_epic_sublimation_on_a_relic_or_a_plain_piece_is_flagged(self):
        for name, position in (('relic', 'HEAD'), ('plain', 'HEAD')):
            with self.subTest(piece=name):
                self.assertEqual([wakfu_legality.SUBLIMATION_RARITY],
                                 self.rules({position: name}, specials={position: EPIC}))

    def test_a_relic_sublimation_on_an_epic_or_a_plain_piece_is_flagged(self):
        self.assertEqual([wakfu_legality.SUBLIMATION_RARITY],
                         self.rules({'NECK': 'epic'}, specials={'NECK': RELIC}))
        self.assertEqual([wakfu_legality.SUBLIMATION_RARITY],
                         self.rules({'HEAD': 'plain'}, specials={'HEAD': RELIC}))

    def test_a_relic_sublimation_on_a_relic_piece_is_legal(self):
        self.assertEqual([], self.rules({'HEAD': 'relic'}, specials={'HEAD': RELIC}))

    def test_one_relic_and_one_epic_sublimation_make_a_legal_set(self):
        self.assertEqual([], self.rules({'HEAD': 'relic', 'NECK': 'epic'},
                                        specials={'HEAD': RELIC, 'NECK': EPIC}))

    def test_two_epic_sublimations_are_flagged_even_on_epic_pieces(self):
        self.assertEqual([wakfu_legality.EPIC_SUBLIMATION], self.rules(
            {'NECK': 'epic', 'BACK': 'other epic'},
            specials={'NECK': EPIC, 'BACK': OTHER_EPIC}))

    def test_two_relic_sublimations_are_flagged_even_on_relic_pieces(self):
        self.assertEqual([wakfu_legality.RELIC_SUBLIMATION], self.rules(
            {'HEAD': 'relic', 'CHEST': 'other relic'},
            specials={'HEAD': RELIC, 'CHEST': OTHER_RELIC}))

    def test_a_relic_piece_holds_a_normal_and_a_relic_sublimation(self):
        self.assertEqual([], self.rules({'HEAD': 'relic'}, specials={'HEAD': RELIC},
                                        sublimations={'HEAD': NORMAL}))

    def test_two_special_sublimations_on_one_piece_are_flagged(self):
        found = self.rules({'HEAD': 'relic'}, specials={'HEAD': [RELIC, OTHER_RELIC]})
        self.assertIn(wakfu_legality.SUBLIMATION_PER_ITEM, found)

    def test_a_special_given_as_a_normal_sublimation_is_flagged(self):
        self.assertEqual([wakfu_legality.SUBLIMATION_UNKNOWN],
                         self.rules({'HEAD': 'relic'}, sublimations={'HEAD': RELIC}))

    def test_a_normal_sublimation_given_as_a_special_is_flagged(self):
        self.assertEqual([wakfu_legality.SUBLIMATION_UNKNOWN],
                         self.rules({'HEAD': 'relic'}, specials={'HEAD': NORMAL}))


class TheKindOfAPieceFollowsItsRarityAndNothingElseTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block())

    def test_the_rarity_of_the_block_decides(self):
        kinds = {name: wakfu_sublimations.special_kind(piece)
                 for name, piece in pieces().items()}
        self.assertEqual({'relic': 'relic', 'epic': 'epic', 'other relic': 'relic',
                          'other epic': 'epic', 'legacy': None, 'plain': None}, kinds)

    def test_a_piece_flagged_epic_at_another_rarity_takes_no_epic_sublimation(self):
        legacy = pieces()['legacy']
        self.assertIn('epic', legacy.flags)
        self.assertIsNone(wakfu_sublimations.special_kind(legacy))

    def test_the_rarities_are_read_from_the_block_not_typed(self):
        found = use_block(self, block())
        found.RARITY_RELIC, found.RARITY_EPIC = 11, 12
        self.assertEqual(('relic', 'epic', None), (
            wakfu_sublimations.special_kind(Piece(1, 1, rarity=11)),
            wakfu_sublimations.special_kind(Piece(2, 1, rarity=12)),
            wakfu_sublimations.special_kind(Piece(3, 1, rarity=5))))
