from django.test import SimpleTestCase

from chardata.wakfu_invented_sublimations import Structure, block, use_block
from fashionistapulp import wakfu_legality, wakfu_sublimations

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None

LEVELS = (9, 10, 29, 30, 50, 99, 100, 149, 150, 200, 245)
SLOTS = (0, 1, 1, 2, 3, 3, 4, 4, 5, 6, 6)


def passive(breed, unlock):
    return {'name': 'Passive', 'breed': breed, 'unlock': unlock, 'family': 'J', 'lines': [],
            'conditions': [], 'conversions': [], 'uncounted': []}


def rules(structure, level, class_id, passives):
    found = wakfu_legality.violations(structure, level, {}, class_id=class_id,
                                      passives=passives)
    return [rule for rule, _text in found]


class TheLiveBlockOpensTheSlotsAtTheLevelsTheClientGivesTests(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def test_the_slots_open_at_the_game_levels(self):
        self.assertEqual(SLOTS, tuple(wakfu_sublimations.slots_open(level) for level in LEVELS))

    def test_a_class_at_level_forty_holds_at_most_two_of_its_own_passives(self):
        breeds = {entry['breed'] for entry in live.PASSIVES.values()}
        self.assertTrue(breeds)
        structure = Structure([], bases={breed: {} for breed in breeds})
        for breed in sorted(breeds):
            unlocked = wakfu_sublimations.passives_of(breed, 40)
            with self.subTest(breed=breed):
                self.assertTrue(unlocked)
                self.assertTrue(all(live.PASSIVES[ident]['unlock'] <= 40
                                    and live.PASSIVES[ident]['breed'] == breed
                                    for ident in unlocked))
                self.assertEqual([], rules(structure, 40, breed, unlocked[:2]))
                if len(unlocked) > 2:
                    self.assertEqual([wakfu_legality.PASSIVE_SLOTS],
                                     rules(structure, 40, breed, unlocked[:3]))

    def test_the_passives_of_a_class_come_in_unlock_order(self):
        for breed in {entry['breed'] for entry in live.PASSIVES.values()}:
            unlocks = [live.PASSIVES[ident]['unlock']
                       for ident in wakfu_sublimations.passives_of(breed, 245)]
            self.assertEqual(sorted(unlocks), unlocks, breed)

    def test_no_passive_is_open_before_its_unlock_level(self):
        for breed in {entry['breed'] for entry in live.PASSIVES.values()}:
            for ident in wakfu_sublimations.passives_of(breed, 20):
                self.assertLessEqual(live.PASSIVES[ident]['unlock'], 20)

    def test_a_class_with_every_passive_open_lists_every_passive_it_has(self):
        for breed in {entry['breed'] for entry in live.PASSIVES.values()}:
            own = {ident for ident, entry in live.PASSIVES.items() if entry['breed'] == breed}
            self.assertEqual(own, set(wakfu_sublimations.passives_of(breed, 245)))


class TheSlotsComeFromTheBlockAndTheCheckerReadsThemTests(SimpleTestCase):
    def setUp(self):
        self.structure = Structure([], bases={1: {}, 2: {}})
        self.block = use_block(self, block(passives={
            10: passive(1, 10), 11: passive(1, 30), 12: passive(1, 30), 20: passive(2, 10)}))

    def test_the_slots_are_counted_from_the_levels_the_block_lists(self):
        self.block.PASSIVE_SLOT_LEVELS = (5, 6, 700)
        self.assertEqual((0, 1, 2, 2), tuple(
            wakfu_sublimations.slots_open(level) for level in (4, 5, 6, 699)))
        self.assertEqual(3, wakfu_sublimations.slots_open(700))

    def test_a_passive_of_another_class_is_flagged(self):
        self.assertEqual([wakfu_legality.PASSIVE_CLASS], rules(self.structure, 100, 1, [20]))

    def test_a_passive_in_a_build_with_no_class_is_flagged(self):
        self.assertEqual([wakfu_legality.PASSIVE_CLASS], rules(self.structure, 100, None, [10]))

    def test_a_passive_above_the_level_is_flagged(self):
        self.assertEqual([wakfu_legality.PASSIVE_LEVEL], rules(self.structure, 20, 1, [11]))

    def test_more_passives_than_open_slots_are_flagged(self):
        self.assertEqual([wakfu_legality.PASSIVE_SLOTS],
                         rules(self.structure, 30, 1, [10, 11, 12]))
        self.assertEqual([], rules(self.structure, 30, 1, [10, 11]))

    def test_a_passive_chosen_twice_is_flagged(self):
        self.assertEqual([wakfu_legality.PASSIVE_TWICE], rules(self.structure, 30, 1, [10, 10]))

    def test_a_passive_the_tables_do_not_hold_is_flagged(self):
        self.assertEqual([wakfu_legality.PASSIVE_UNKNOWN], rules(self.structure, 30, 1, [999]))

    def test_the_passives_of_a_class_are_the_unlocked_ones_in_order(self):
        self.assertEqual([10, 11, 12], wakfu_sublimations.passives_of(1, 30))
        self.assertEqual([10], wakfu_sublimations.passives_of(1, 29))
        self.assertEqual([], wakfu_sublimations.passives_of(3, 245))

    def test_a_set_with_no_passive_argument_is_checked_as_before(self):
        found = wakfu_legality.violations(self.structure, 100, {}, class_id=1)
        self.assertEqual([], found)
