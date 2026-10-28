from django.test import SimpleTestCase

from chardata.tests_wakfu_build_solves_on_the_damage_model import (
    CAPE, HELMET, Catalogue, Piece, ids, piece)


class Lockable(Piece):
    removed = False


PIECES = tuple(Lockable(*one) for one in (
    piece(1, HELMET, hp=10), piece(2, HELMET, hp=100), piece(3, HELMET, hp=50),
    piece(4, CAPE, hp=20), piece(5, CAPE, hp=30)))


class LockableCatalogue(Catalogue):
    def get_item_by_id(self, ident):
        return next((one for one in self.pieces if one.id == ident), None)


def build_with(pruned, locked=((1, 'HEAD'),)):
    from fashionistapulp.wakfu_model import WakfuBuild
    return WakfuBuild(LockableCatalogue(*PIECES), 50, {'hp': 1}, locked=locked,
                      prune_locked_positions=pruned)


def placed(build, position):
    return sorted(item.id for item, place in build._placements if place == position)


class ALockedPositionHoldsOnlyItsLockWhenPrunedTests(SimpleTestCase):
    def test_a_pruned_build_offers_only_the_locked_piece_in_its_position(self):
        build = build_with(True)
        build.build()
        self.assertEqual([(1, 'HEAD')], [(item.id, place) for item, place in build._placements
                                         if place == 'HEAD'])

    def test_a_pruned_build_reaches_the_objective_of_the_full_build(self):
        full, pruned = build_with(False), build_with(True)
        worn_full = full.build().solve()
        worn_pruned = pruned.build().solve()
        self.assertEqual({1, 5}, ids(worn_full))
        self.assertEqual(ids(worn_full), ids(worn_pruned))
        self.assertAlmostEqual(full.objective_of(worn_full), pruned.objective_of(worn_pruned))

    def test_a_position_no_lock_names_keeps_every_candidate(self):
        build = build_with(True)
        build.build()
        self.assertEqual([4, 5], placed(build, 'BACK'))

    def test_a_build_that_is_not_pruned_keeps_every_candidate_of_a_locked_position(self):
        build = build_with(False)
        build.build()
        self.assertEqual([1, 2, 3], placed(build, 'HEAD'))

    def test_a_lock_with_no_position_prunes_nothing(self):
        build = build_with(True, locked=((1, None),))
        build.build()
        self.assertEqual([1, 2, 3], placed(build, 'HEAD'))
        self.assertEqual([4, 5], placed(build, 'BACK'))
