from django.test import SimpleTestCase

from fashionistapulp import wakfu_legality, wakfu_sublimations
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, SublimationModelCase, block, use_block)
from chardata.wakfu_invented_sublimations import Structure

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None

BETA = 2
GENERIC = -2


def passive(breed, unlock, ferocity):
    return {'name': 'Passive %d' % ferocity, 'breed': breed, 'unlock': unlock, 'family': 'A',
            'lines': [('A', 'ferocity', ferocity, 0, ())], 'conditions': [],
            'conversions': [], 'uncounted': []}


PASSIVES = {701: passive(ALPHA, 10, 5), 702: passive(BETA, 10, 6),
            703: passive(GENERIC, 30, 9), 704: passive(GENERIC, 90, 40)}


class AGenericPassiveIsOpenToEveryClassTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block(passives=PASSIVES, generic=GENERIC))

    def test_each_class_takes_its_own_passives_and_the_generic_ones_in_unlock_order(self):
        self.assertEqual([701, 703], wakfu_sublimations.passives_of(ALPHA, 50))
        self.assertEqual([702, 703], wakfu_sublimations.passives_of(BETA, 50))

    def test_a_generic_passive_waits_for_its_unlock_level(self):
        self.assertEqual([701], wakfu_sublimations.passives_of(ALPHA, 29))
        self.assertEqual([701, 703, 704], wakfu_sublimations.passives_of(ALPHA, 90))

    def test_the_legality_check_accepts_a_generic_passive_for_any_class_and_no_other(self):
        structure = Structure([], bases={ALPHA: {}, BETA: {}})
        for class_id in (ALPHA, BETA):
            found = wakfu_legality.violations(structure, 50, {}, class_id=class_id,
                                              passives=[703])
            self.assertEqual([], [rule for rule, _text in found])
        found = wakfu_legality.violations(structure, 50, {}, class_id=ALPHA, passives=[702])
        self.assertEqual([wakfu_legality.PASSIVE_CLASS], [rule for rule, _text in found])

    def test_a_block_with_no_generic_breed_keeps_the_class_passives_only(self):
        use_block(self, block(passives=PASSIVES))
        self.assertEqual([701], wakfu_sublimations.passives_of(ALPHA, 90))


class TheModelPicksAGenericPassiveTests(SublimationModelCase):
    def test_a_generic_passive_takes_a_slot_like_a_class_one(self):
        passives = {701: passive(ALPHA, 10, 5), 703: passive(GENERIC, 10, 9),
                    704: passive(ALPHA, 10, 7)}
        use_block(self, block(passives=passives, generic=GENERIC))
        build, worn = self.sublimate({'ferocity': 1, 'hp': 0.001}, sublimations=None,
                                     passives='solve', level=30)
        self.assertEqual([703, 704], sorted(worn.passives))
        self.assertEqual([], self.rules_broken(worn, level=30))
        self.assert_objective_is_read_back(build, worn)


class TheLiveBlockHoldsTheGenericPassivesTheClientHasTests(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def test_the_generic_passives_are_in_the_block_and_open_to_every_class(self):
        generic = {ident for ident, entry in live.PASSIVES.items()
                   if entry['breed'] == live.GENERIC_BREED}
        self.assertTrue(generic)
        classes = {entry['breed'] for entry in live.PASSIVES.values()} - {live.GENERIC_BREED}
        for class_id in sorted(classes):
            with self.subTest(breed=class_id):
                self.assertLessEqual(generic, set(wakfu_sublimations.passives_of(class_id, 245)))

    def test_a_generic_passive_with_lines_gives_them_in_the_fight(self):
        counted = [ident for ident, entry in live.PASSIVES.items()
                   if entry['breed'] == live.GENERIC_BREED and entry['lines']]
        self.assertTrue(counted)
        for ident in counted:
            entry = live.PASSIVES[ident]
            with self.subTest(passive=entry['name']):
                lines, _reports = wakfu_sublimations.fight_lines(
                    [(wakfu_sublimations.PASSIVE, ident)], {}, 245, None)
                expected = {}
                for _family, key, p0, p1, _guards in entry['lines']:
                    expected[key] = expected.get(key, 0) + wakfu_sublimations.value_at(
                        p0, p1, 245)
                self.assertEqual({key: value for key, value in expected.items() if value},
                                 lines)
