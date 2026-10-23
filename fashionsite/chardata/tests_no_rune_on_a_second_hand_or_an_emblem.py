import os
import sqlite3
from pathlib import Path

from django.test import SimpleTestCase

from chardata.tests_wakfu_runes_enter_every_total_and_gate import MELEE, RED, ARuneCase
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import DAGGER, EMBLEM_A, GREAT
from fashionistapulp import wakfu_legality

NO_SOCKET_POSITIONS = ('SECOND_WEAPON', 'ACCESSORY')


class NoRuneOnASecondHandOrAnEmblemTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.db = get_items_db_path('wakfu')

    def setUp(self):
        if not os.path.exists(self.db):
            self.skipTest('no Wakfu database')
        self.conn = sqlite3.connect('file:%s?mode=ro' % Path(self.db).as_posix(), uri=True)
        self.addCleanup(self.conn.close)
        if self.conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'item_shard_slots'"
                             ).fetchone() is None:
            self.skipTest('the database holds no socket table')

    def test_every_item_of_a_second_hand_or_emblem_type_has_no_socket(self):
        for position in NO_SOCKET_POSITIONS:
            rows = self.conn.execute(
                'SELECT s.item, s.maximum FROM items i'
                ' JOIN item_type_position p ON p.item_type = i.type'
                ' LEFT JOIN item_shard_slots s ON s.item = i.id'
                ' WHERE p.position = ? AND i.removed = 0', (position,)).fetchall()
            self.assertGreater(len(rows), 100, position)
            self.assertEqual([], [row for row in rows if row[1] != 0][:5], position)

    def test_the_catalogue_reads_the_same_socket_range_from_the_database(self):
        from fashionistapulp.structure import get_structure
        structure = get_structure('wakfu')
        for item_id, minimum, maximum in self.conn.execute(
                'SELECT item, minimum, maximum FROM item_shard_slots'
                ' ORDER BY item LIMIT 200'):
            self.assertEqual((minimum, maximum), structure.get_item_by_id(item_id).shard_slots)


class NoRuneOnASecondHandOrAnEmblemInTheModelTests(ARuneCase):
    WEIGHTS = {'melee_dmg': 1, 'hp': 1}

    def test_no_rune_column_names_a_second_hand_or_an_emblem(self):
        build = self.build(self.WEIGHTS, forbidden=[GREAT])
        build.build()
        self.assertTrue(build.rune_colour_terms('HEAD', RED))
        self.assertEqual([], [term for position in NO_SOCKET_POSITIONS
                              for term in build.rune_colour_terms(position, RED)])
        for name in build.problem.variable_names():
            for position in NO_SOCKET_POSITIONS:
                self.assertNotIn('_%s_' % position, name)

    def test_a_set_with_a_second_hand_and_an_emblem_holds_no_socket_on_them(self):
        _build, worn = self.solve_runes(self.WEIGHTS, forbidden=[GREAT], locked=[(DAGGER, None)])
        self.assertEqual(DAGGER, worn['SECOND_WEAPON'].id)
        for position in NO_SOCKET_POSITIONS:
            self.assertIn(position, worn)
            self.assertNotIn(position, worn.runes)

    def test_the_checker_flags_a_rune_on_a_second_hand_and_on_an_emblem(self):
        _build, worn = self.solve_runes(self.WEIGHTS, forbidden=[GREAT], locked=[(DAGGER, None)])
        self.assertEqual(DAGGER, worn['SECOND_WEAPON'].id)
        self.assertEqual(EMBLEM_A, worn['ACCESSORY'].id)
        for position in NO_SOCKET_POSITIONS:
            with self.subTest(position=position):
                found = wakfu_legality.violations(self.structure, 100, worn,
                                                  runes={position: [(RED, MELEE, 1)]})
                self.assertEqual([wakfu_legality.RUNE_SOCKET], [rule for rule, _t in found])
        found = wakfu_legality.violations(
            self.structure, 100, worn, runes={'HEAD': [(RED, MELEE, 1)] * 5})
        self.assertEqual([wakfu_legality.RUNE_SOCKET], [rule for rule, _t in found])

    def test_the_checker_flags_a_rune_where_no_piece_is_worn(self):
        _build, worn = self.solve_runes(self.WEIGHTS)
        self.assertNotIn('SECOND_WEAPON', worn)
        found = wakfu_legality.violations(self.structure, 100, worn,
                                          runes={'SECOND_WEAPON': [(RED, MELEE, 1)]})
        self.assertEqual([wakfu_legality.RUNE_SOCKET], [rule for rule, _t in found])
