import collections
import json
import os
import sqlite3
import tempfile

from django.test import SimpleTestCase

from fashionistapulp import wakfu_client_spells as client

CONDITIONAL = ('a conditional bonus row sits in a state or a multiplier group the walk'
               ' does not price')
CARRIED = 'the damage comes through a state, a spell it casts or a glyph'

VALUES_MISSING = dict.fromkeys(
    (623, 935, 1541, 1542, 2044, 4708, 4712, 4713, 4715, 4775, 4779, 4818, 5032, 5041, 5594,
     6463, 6464, 6472, 6476, 6478, 6905, 6906, 6916, 6970), CONDITIONAL)
NO_ROW = dict.fromkeys(
    (763, 783, 919, 933, 2061, 2067, 4792, 4815, 5122, 5592, 6279, 6282, 6937, 6940, 7187,
     7195), CARRIED)
#: Spells whose range text differs from the client range, with both readings
RANGE_DIFFERS = {4716: ((2, 4), (1.0, 4.0)), 5047: ((1, 1), (1.0, 2.0))}
#: (class, id) of the damage spells only the client holds
CLIENT_ONLY = [(2, 7327), (4, 8508), (6, 2079), (7, 5454), (11, 5195), (14, 7095),
               (16, 6936), (18, 4686)]
FULGUR = 4775
LEVELS = (1, 20, 50, 100, 150, 200, 245)


class TheWakfuClientSpellReaderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        cls.path = path
        cls.book = None
        if os.path.exists(path):
            cls.book = client.ClientSpellBook(path)
            if not cls.book.conn.execute('SELECT COUNT(*) FROM client_spells').fetchone()[0]:
                cls.book.close()
                cls.book = None

    @classmethod
    def tearDownClass(cls):
        if cls.book is not None:
            cls.book.close()
        super().tearDownClass()

    def setUp(self):
        if self.book is None:
            self.skipTest('no Wakfu database with the client spell table; run update_data_wakfu.py')

    def damage_spells(self):
        return [spell for breed in self.book.breeds()
                for spell in self.book.class_spells(breed) if spell.damage_rows()]

    def test_fulgur_reads_the_figures_the_game_shows(self):
        spell = self.book.spell(FULGUR)
        self.assertEqual((spell.breed, spell.ap, spell.mp, spell.wp, spell.range,
                          spell.unlock_level), (8, 3, 0, 0, (1, 3), 3))
        rows = spell.damage_rows()
        self.assertEqual(len(rows), 4)
        self.assertEqual({row.element for row in rows}, {'fire'})
        for row in rows:
            self.assertEqual([row.value(level) for level in (1, 100, 245)], [3, 35, 83])
            critical = spell.critical_of(row)
            self.assertEqual(critical.branch, client.CRITICAL)
            self.assertEqual([critical.value(level) for level in (1, 100, 245)], [3, 44, 104])
            self.assertEqual(row.signature, critical.signature)
            self.assertTrue(row.conditional)
            self.assertFalse(row.is_area)

    def test_the_client_curve_is_read_one_level_below_the_displayed_one(self):
        row = self.book.spell(FULGUR).damage_rows()[0]
        self.assertEqual(row.value(100), int(3 + row.params[1] * 99))
        self.assertEqual(row.value(100), 35)
        self.assertEqual(int(3 + row.params[1] * 100), 36)

    def test_every_harvest_damage_row_equals_the_client_at_every_sampled_level(self):
        checked = collections.Counter()
        for spell_id, (status, matches) in client.harvest_check(self.book).items():
            for match in matches:
                if match.status not in (client.AGREE, client.ELEMENT_DIFFERS):
                    continue
                for level in LEVELS:
                    (value,) = self.book.conn.execute(
                        "SELECT value FROM spell_effects WHERE spell = ? AND level = ?"
                        " AND position = ? AND kind = 'damage'",
                        (spell_id, level, match.position)).fetchone()
                    self.assertEqual(match.row.value(level), value,
                                     (spell_id, match.position, level))
                    checked[level] += 1
        self.assertEqual(set(checked), set(LEVELS))
        self.assertGreater(min(checked.values()), 300)

    def test_the_harvest_agrees_except_for_the_named_spells(self):
        check = client.harvest_check(self.book)
        self.assertEqual(len(check), 285)
        gaps = client.gap_list(self.book)
        self.assertEqual({spell_id for spell_id, reason in gaps.items()
                          if reason == client.VALUES_MISSING}, set(VALUES_MISSING))
        self.assertEqual({spell_id for spell_id, reason in gaps.items()
                          if reason == client.NO_ROW}, set(NO_ROW))
        self.assertEqual(len(gaps), len(VALUES_MISSING) + len(NO_ROW))
        self.assertEqual(len(check) - len(gaps), 245)
        statuses = [match.status for _, matches in check.values() for match in matches]
        self.assertNotIn(client.ELEMENT_DIFFERS, statuses)

    def test_the_heal_rows_follow_the_same_level_rule(self):
        check = client.harvest_check(self.book, 'healing')
        self.assertEqual(len(check), 47)
        self.assertEqual(sum(1 for status, _ in check.values() if status == client.AGREE), 38)
        for spell_id, (status, matches) in check.items():
            for match in matches:
                if match.status != client.AGREE:
                    continue
                for level in (1, 100, 245):
                    (value,) = self.book.conn.execute(
                        "SELECT value FROM spell_effects WHERE spell = ? AND level = ?"
                        " AND position = ? AND kind = 'healing'",
                        (spell_id, level, match.position)).fetchone()
                    self.assertEqual(match.row.value(level), value, (spell_id, level))

    def test_the_damage_spells_only_the_client_holds(self):
        harvest = set(client.harvest_spells(self.book.conn))
        spells = self.damage_spells()
        self.assertEqual(len(spells), 277)
        self.assertEqual(sorted((spell.breed, spell.id) for spell in spells
                                if spell.id not in harvest), CLIENT_ONLY)

    def test_rows_count_as_the_client_tree_has_them(self):
        rows = [row for spell in self.damage_spells() for row in spell.damage_rows()]
        self.assertEqual(len(rows), 701)
        self.assertEqual(sum(1 for row in rows if not row.conditional), 122)
        self.assertEqual(sum(1 for row in rows if row.is_area), 193)

    def test_the_critical_is_not_a_quarter_more_than_the_base(self):
        spell = self.book.spell(FULGUR)
        base = spell.damage_rows()[0]
        self.assertEqual(int(base.value(245) * 1.25), 103)
        self.assertEqual(spell.critical_of(base).value(245), 104)

    def test_costs_agree_with_the_encyclopedia_and_two_ranges_differ(self):
        shared = self.book.conn.execute(
            'SELECT COUNT(*) FROM spells s JOIN client_spells c ON c.id = s.id').fetchone()[0]
        self.assertEqual(shared, 714)
        self.assertEqual(client.costs_differ(self.book),
                         {spell_id: [('range',) + pair] for spell_id, pair in RANGE_DIFFERS.items()})

    def test_a_spell_is_castable_from_its_unlock_level(self):
        spells = self.damage_spells()
        fulgur = self.book.spell(FULGUR)
        self.assertFalse(fulgur.castable_at(2))
        self.assertTrue(fulgur.castable_at(3))
        unlocked = {level: sum(1 for spell in spells if spell.castable_at(level))
                    for level in (1, 20, 25, 51, 91, 245)}
        self.assertEqual(unlocked, {1: 54, 20: 211, 25: 265, 51: 272, 91: 277, 245: 277})
        late = [spell for spell in spells if spell.unlock_level > 20]
        self.assertEqual(len(late), 66)
        self.assertTrue(all(not spell.castable_at(20) for spell in late))


class TheTurnReadsTheClientSpellTableTests(SimpleTestCase):
    """SpellBook on the real tables: the client's figures, the encyclopedia's structure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp import wakfu_turn
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.wakfu_turn = wakfu_turn
        cls.path = get_items_db_path('wakfu')
        cls.book = None
        if os.path.exists(cls.path):
            cls.book = wakfu_turn.SpellBook(cls.path)
            if not cls.book.client():
                cls.book.close()
                cls.book = None

    @classmethod
    def tearDownClass(cls):
        if cls.book is not None:
            cls.book.close()
        super().tearDownClass()

    def setUp(self):
        if self.book is None:
            self.skipTest('no Wakfu database with the client spell table; run update_data_wakfu.py')

    def spells(self, level):
        return [spell for breed in self.book.client().breeds()
                for spell in self.book.spells(breed, level)]

    def test_at_mastery_zero_every_client_row_is_the_clients_base_and_critical_at_245(self):
        checked = collections.Counter()
        for spell in self.spells(245):
            own = self.book.client().spell(spell.id)
            normal = collections.Counter(row.value(245) for row in own.damage_rows())
            critical = collections.Counter(
                row.value(245) for row in own.damage_rows(client.CRITICAL))
            for row in spell.rows:
                if row.value_read != 'client':
                    continue
                with self.subTest(spell=spell.id, row=row.position):
                    self.assertIn(row.base, normal)
                    checked['base'] += 1
                    if row.critical_read == 'client':
                        self.assertIn(row.critical, critical)
                        checked['critical'] += 1
        self.assertGreater(checked['base'], 300)
        self.assertGreater(checked['critical'], 300)

    def test_a_client_critical_is_the_text_critical_at_245(self):
        checked = 0
        for spell in self.spells(245):
            clauses, aligned, _needs = self.book.clauses(spell.id)
            for row in spell.rows:
                if row.critical_read != 'client' or aligned is None:
                    continue
                told = clauses[aligned[row.position]][2]
                if told is None:
                    continue
                with self.subTest(spell=spell.id, row=row.position):
                    self.assertEqual(told, row.critical)
                checked += 1
        self.assertGreater(checked, 300)

    def test_the_critical_is_not_the_quarter_more_the_encyclopedia_rounds_away(self):
        spell, = [one for one in self.book.spells(8, 245) if one.id == FULGUR]
        first, second = spell.rows
        self.assertEqual((83, 104, 'client'), (first.base, first.critical, first.critical_read))
        self.assertEqual(103, int(first.base * 1.25))
        self.assertEqual((55, 'harvest'), (second.base, second.value_read))

    def test_the_level_rule_holds_through_the_turn_at_each_sampled_level(self):
        for level in (3, 20, 100, 245):
            with self.subTest(level=level):
                compared = 0
                for spell in self.spells(level):
                    for row in spell.rows:
                        if row.value_read != 'client':
                            continue
                        (value,) = self.book.conn.execute(
                            "SELECT value FROM spell_effects WHERE spell = ? AND level = ?"
                            " AND position = ? AND kind = 'damage'",
                            (spell.id, level, row.position)).fetchone()
                        self.assertEqual(value, row.base, (spell.id, row.position))
                        compared += 1
                self.assertGreater(compared, 50)
        fulgur = {level: self.book.spells(8, level) for level in (3, 100, 245)}
        self.assertEqual([3, 35, 83], [[spell for spell in fulgur[level] if spell.id == FULGUR][0]
                                       .rows[0].base for level in (3, 100, 245)])

    def test_a_spell_is_not_castable_below_its_unlock_level(self):
        counts = {}
        for level in (20, 25, 51, 91, 245):
            every = self.spells(level)
            for spell in every:
                self.assertLessEqual(spell.unlock, level)
            counts[level] = len(every)
        self.assertEqual({20: 213, 25: 267, 51: 275, 91: 279, 245: 279}, counts)
        iop = {spell.id for spell in self.book.spells(8, 20)}
        late = [own for own in self.book.client().class_spells(8)
                if own.damage_rows() and own.unlock_level > 20 and (own.ap or own.wp or own.mp)]
        self.assertTrue(late)
        self.assertEqual(set(), iop & {own.id for own in late})

    def test_the_old_assumption_lets_every_spell_in_at_every_level(self):
        from unittest import mock
        from fashionistapulp.wakfu_value_rules import RULES
        every = len(self.spells(245))
        with mock.patch.dict(RULES, {'spells_castable_at_every_level': RULES[
                'spells_castable_at_every_level']._replace(value=True)}):
            self.assertEqual(every, len(self.spells(20)))
        self.assertLess(len(self.spells(20)), every)

    def test_costs_and_range_are_the_clients(self):
        for spell in self.spells(245):
            own = self.book.client().spell(spell.id)
            self.assertEqual((int(own.ap), int(own.wp), int(own.mp), int(own.range[0]),
                              int(own.range[1])),
                             (spell.ap, spell.wp, spell.mp, spell.low, spell.high), spell.id)
        by_id = {spell.id: spell for spell in self.spells(245)}
        for spell_id, (_harvest, (low, high)) in RANGE_DIFFERS.items():
            if spell_id in by_id:
                self.assertEqual((int(low), int(high)),
                                 (by_id[spell_id].low, by_id[spell_id].high))
        self.assertIn(4716, by_id)

    def test_the_forty_gap_spells_keep_the_encyclopedia_figures_and_are_named(self):
        named = {}
        for spell in self.spells(245):
            if spell.gap:
                named[spell.id] = spell.gap
                self.assertIn(spell.id, {**VALUES_MISSING, **NO_ROW})
                if spell.gap == client.NO_ROW and spell.rows:
                    self.assertEqual({'harvest'}, {row.value_read for row in spell.rows})
        self.assertEqual(client.VALUES_MISSING, named[FULGUR])
        every = {**VALUES_MISSING, **NO_ROW}
        self.assertEqual(40, len(every))
        for spell_id in every:
            status, _matches = self.book.client_status(spell_id)
            self.assertEqual(client.VALUES_MISSING if spell_id in VALUES_MISSING
                             else client.NO_ROW, status)
        notes = [detail for _ids, key, detail in self.wakfu_turn.best_turn(
            [one for one in self.book.spells(8, 245) if one.id == FULGUR],
            self.wakfu_turn.wakfu_value.DamageDealer(('fire',), 'melee'),
            {'ap': 6, 'mp': 3, 'wp': 6}).unmodelled if key == self.wakfu_turn.GAP]
        self.assertEqual(['encyclopedia figures kept: %s' % client.VALUES_MISSING], notes)

    def test_the_spells_only_the_client_holds_add_no_damage_the_model_cannot_gate(self):
        added = {}
        for breed, spell_id in CLIENT_ONLY:
            names = self.book.names(breed)
            self.assertIn(spell_id, names)
            added.update((spell.id, spell) for spell in self.book.spells(breed, 245)
                         if spell.id == spell_id)
        # Only two of the eight cost anything; the rest are passives and triggers
        self.assertEqual({2079, 7327}, set(added))
        for spell in added.values():
            self.assertEqual((), spell.rows)
            self.assertTrue(spell.skipped)
            self.assertEqual(self.book.client().spell(spell.id).unlock_level, spell.unlock)

    def test_two_rows_of_one_curve_take_the_case_with_no_state_held(self):
        by_id = {spell.id: spell for spell in self.spells(200)}
        self.assertEqual(66, by_id[5562].rows[0].critical)
        spell, = [one for one in self.book.spells(19, 245) if one.id == 5594]
        self.assertEqual((316, 392), (spell.rows[0].base, spell.rows[0].critical))
        iop = {one.id: one for one in self.book.spells(8, 245)}
        self.assertEqual(('client', 104), (iop[4789].rows[0].critical_read,
                                           iop[4789].rows[0].critical))

    def test_the_area_flag_follows_the_clients_area(self):
        areas = [row.area for spell in self.spells(245) for row in spell.rows]
        self.assertGreater(sum(areas), 50)
        self.assertFalse(all(areas))

    def test_a_database_without_client_spells_reads_the_encyclopedia_alone(self):
        from .tests_wakfu_turn_counts_rows_under_the_roles_conditions import InventedSpells
        invented = InventedSpells()
        self.addCleanup(invented.remove)
        book = invented.book()
        self.addCleanup(book.close)
        self.assertIsNone(book.client())
        spells = book.spells(invented.CLASS, 245)
        self.assertTrue(spells)
        for spell in spells:
            self.assertEqual((1, None), (spell.unlock, spell.gap))
            self.assertEqual({'harvest'}, {row.value_read for row in spell.rows})

    def test_the_rules_the_turn_reads_name_their_status(self):
        from fashionistapulp.wakfu_value_rules import FACT, RULES
        self.assertEqual((1, FACT), (RULES['client_spell_level_offset'].value,
                                     RULES['client_spell_level_offset'].status))
        self.assertEqual((False, FACT), (RULES['spells_castable_at_every_level'].value,
                                         RULES['spells_castable_at_every_level'].status))


class TheWakfuClientSpellWalkTests(SimpleTestCase):
    """The walk on a small table written here."""

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        self.addCleanup(os.remove, self.path)
        conn = sqlite3.connect(self.path)
        conn.execute('CREATE TABLE client_spells (id, breed, ap, mp, wp, range_min, range_max,'
                     ' element, unlock_level, max_level)')
        conn.execute('CREATE TABLE client_spell_effects (spell, position, effect)')
        conn.execute('CREATE TABLE effect_groups (group_id, position, effect)')
        conn.execute('CREATE TABLE effects (id, action, container_type, container,'
                     ' root_container_type, normal_or_critical, area_shape, area_size,'
                     ' params, criterion)')
        conn.execute('INSERT INTO client_spells VALUES (1, 5, 3, 1, 0, 1, 4, 2, 7, 245)')

        def effect(identifier, action, branch, params, criterion='', shape=1, size='[]'):
            conn.execute("INSERT INTO effects VALUES (?, ?, 'SPELL', 1, 'SPELL', ?, ?, ?, ?, ?)",
                         (identifier, action, branch, shape, size, json.dumps(params),
                          criterion))

        effect(10, 330, 'NORMAL', [])
        effect(11, 2, 'NORMAL', [10.0, 1.0], 'IsEnemy()\r\nand HasState(5, 1, "caster")', 3, '[2]')
        effect(12, 3, 'NORMAL', [4.0, 0.5])
        effect(20, 330, 'CRITICAL', [])
        effect(21, 2, 'CRITICAL', [12.5, 1.25], 'IsEnemy()\r\nand HasState(5, 1, "caster")')
        effect(22, 3, 'CRITICAL', [5.0, 0.625])
        for position, root in enumerate((10, 20)):
            conn.execute('INSERT INTO client_spell_effects VALUES (1, ?, ?)', (position, root))
        for group, position, member in ((10, 0, 11), (10, 1, 12), (20, 0, 21), (20, 1, 22)):
            conn.execute('INSERT INTO effect_groups VALUES (?, ?, ?)', (group, position, member))
        conn.commit()
        conn.close()
        self.book = client.ClientSpellBook(self.path)
        self.addCleanup(self.book.close)

    def test_branches_criteria_area_and_pairs_come_down_the_groups(self):
        spell = self.book.spell(1)
        fire, earth = spell.damage_rows()
        self.assertEqual((fire.element, fire.branch, fire.depth), ('fire', 'NORMAL', 1))
        self.assertEqual(fire.criteria, ('IsEnemy() and HasState(5, 1, "caster")',))
        self.assertTrue(fire.is_area)
        self.assertEqual(fire.area_size, (2,))
        self.assertFalse(earth.is_area)
        self.assertFalse(earth.conditional)
        self.assertEqual(spell.critical_of(fire).value(11), 25)
        self.assertEqual(spell.critical_of(earth).value(11), 11)
        self.assertEqual(len(spell.damage_rows('CRITICAL')), 2)

    def test_the_value_is_read_one_level_below_and_floored(self):
        fire, earth = self.book.spell(1).damage_rows()
        self.assertEqual([fire.value(level) for level in (1, 2, 11)], [10, 11, 20])
        self.assertEqual([earth.value(level) for level in (1, 2, 3, 4)], [4, 4, 5, 5])

    def test_the_spell_is_castable_from_its_unlock_level(self):
        spell = self.book.spell(1)
        self.assertFalse(spell.castable_at(6))
        self.assertTrue(spell.castable_at(7))
        self.assertEqual((spell.ap, spell.mp, spell.wp, spell.range), (3, 1, 0, (1, 4)))

    def test_an_unknown_spell_raises(self):
        with self.assertRaises(KeyError):
            self.book.spell(99)
