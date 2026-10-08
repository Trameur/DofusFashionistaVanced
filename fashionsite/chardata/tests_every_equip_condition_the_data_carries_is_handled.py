# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every kind of equip condition a version's pieces carry is one the code knows, and the database holds what the criteria say."""

import contextlib
import io
import os
import sqlite3
import unittest

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

PULP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'fashionistapulp', 'fashionistapulp')

BASES = {
    'dofus3': 'items.db',
    'beta': 'items_beta.db',
    'dofus2': 'items_dofus2.db',
    'touch': 'items_touch.db',
    'retro': 'items_retro.db',
}

# Below this many criteria a read found nothing
FLOOR = 100


def _criteria():
    return itemscraper_module('item_criteria')


def _connect(version):
    path = os.path.join(PULP, BASES[version])
    if not os.path.exists(path):
        raise unittest.SkipTest('%s is absent' % BASES[version])
    return sqlite3.connect('file:%s?mode=ro' % path, uri=True)


def _rows(connection, query):
    return connection.execute(query).fetchall()


def _table_exists(connection, name):
    return bool(connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,)).fetchone())


def _read(version):
    """({item id: parsed criteria}, {item id: criteria that does not parse}) of every piece that carries some."""
    criteria = _criteria()
    connection = _connect(version)
    try:
        rows = _rows(connection, 'SELECT item, criteria FROM item_criteria')
    finally:
        connection.close()
    trees, unread = {}, {}
    for item, text in rows:
        try:
            trees[item] = criteria.parse(text)
        except criteria.CriteriaError:
            unread[item] = text
    return trees, unread


def _trees(version):
    return _read(version)[0]


def _is_group(node):
    return isinstance(node[1], list)


def _parts_read_loosely(criteria, version, tree):
    """Parts the kind-by-kind reading would relax: an OR over two enforced kinds, or a top-level-only kind nested."""
    top_level_only = {criteria.LEVEL, criteria.SET_BONUS, criteria.SETS_EQUIPPED,
                      criteria.NOT_WORN_WITH, criteria.SPELL_RANK}
    read_in_an_or = {criteria.STAT, criteria.CLASS, criteria.UNUSABLE}
    table = criteria.KINDS[version]

    def kind(atom):
        return table.get((atom[0], atom[1]))

    top = tree[1] if _is_group(tree) and tree[0] == 'and' else [tree]
    loose = [atom for node in top if _is_group(node)
             for atom in criteria.atoms(node) if kind(atom) in top_level_only]

    def walk(node):
        if not _is_group(node):
            return
        if node[0] == 'or':
            kinds = {kind(atom) for atom in criteria.atoms(node)} & criteria.ENFORCED
            if len(kinds) > 1 or kinds - read_in_an_or:
                loose.append(node)
        for child in node[1]:
            walk(child)

    walk(tree)
    return loose


def _class_names(version):
    if version == 'touch':
        return dict(itemscraper_module('get_spells_touch').CLASS_ID_TO_NAME)
    if version == 'retro':
        return dict(itemscraper_module('get_spells_retro').CLASS_ID_TO_NAME)
    return dict(itemscraper_module('store_spell_reference').CLASS_ID_TO_NAME)


class EveryConditionKindIsHandledTests(SimpleTestCase):

    def test_every_criteria_string_stored_parses(self):
        for version in BASES:
            with self.subTest(version=version):
                self.assertEqual({}, _read(version)[1])

    def test_no_stored_criteria_mixes_kinds_the_reading_splits_apart(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                loose = {item: parts for item, tree in _trees(version).items()
                         for parts in [_parts_read_loosely(criteria, version, tree)]
                         if parts}
                self.assertEqual({}, loose)

    def test_a_class_and_a_stat_in_one_or_are_reported(self):
        criteria = _criteria()
        for text, reported in (('(CS>20&PG=1)|CI>20', True),
                               ('CS>10&(PL<6&CI>3)', True),
                               ('CS>350&(CI>350|CC>350)', False),
                               ('CI>150&CV>150&(PG=2|PG=5)', False),
                               ('CS>20|PX=A', False)):
            with self.subTest(criteria=text):
                self.assertEqual(reported, bool(_parts_read_loosely(
                    criteria, 'dofus3', criteria.parse(text))))

    def test_criteria_that_do_not_parse_leave_a_warning_and_no_tree(self):
        criteria = _criteria()
        with self.assertRaises(criteria.CriteriaError):
            criteria.parse('CS>20&CI>20|CA>20')
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertIsNone(criteria.read('CS>20&CI>20|CA>20', 42))
        self.assertIn('warning', printed.getvalue())
        self.assertIn('42', printed.getvalue())

    def test_each_version_lists_every_kind_its_pieces_carry(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                trees = _trees(version)
                self.assertGreaterEqual(len(trees), FLOOR)
                unknown = sorted({kind for tree in trees.values()
                                  for kind, handled in criteria.kinds(version, tree).items()
                                  if handled is None})
                self.assertEqual([], unknown)

    def test_dofus3_reads_the_server_gates_of_the_beta_pieces_as_the_beta_does(self):
        criteria = _criteria()
        gated = [tree for tree in _trees('beta').values()
                 if {('SC', '='), ('ST', '=')} & set(criteria.kinds('beta', tree))]
        self.assertTrue(gated)
        for tree in gated:
            self.assertEqual(criteria.kinds('beta', tree), criteria.kinds('dofus3', tree))

    def test_a_kind_the_registry_drops_is_reported(self):
        criteria = _criteria()
        tree = criteria.parse('PG=3&Zz>2')
        self.assertEqual({('PG', '='): criteria.CLASS, ('Zz', '>'): None},
                         criteria.kinds('dofus3', tree))

    def test_every_handled_kind_is_enforced_or_named_as_left_open(self):
        criteria = _criteria()
        open_kinds = {
            criteria.ALIGNMENT, criteria.PVP_RANK, criteria.JOB, criteria.KAMAS,
            criteria.MARRIED, criteria.EMOTE,
            criteria.SUBSCRIPTION, criteria.ACCOUNT_RIGHTS, criteria.QUEST,
            criteria.SERVER, criteria.DATE, criteria.MAP, criteria.SUBAREA,
            criteria.INVENTORY, criteria.WORN_WITH, criteria.UNKNOWN}
        for version, kinds in criteria.KINDS.items():
            with self.subTest(version=version):
                self.assertLessEqual(set(kinds.values()),
                                     criteria.ENFORCED | open_kinds)


class TheDatabaseHoldsWhatTheCriteriaSayTests(SimpleTestCase):

    def test_the_classes_stored_are_the_ones_the_criteria_allow(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                names = _class_names(version)
                expected = {}
                for item, tree in _trees(version).items():
                    allowed = criteria.allowed_classes(tree, names)
                    if allowed is not None:
                        expected[item] = set(allowed)
                connection = _connect(version)
                try:
                    stored = {}
                    if _table_exists(connection, 'item_class_conditions'):
                        for item, char_class in _rows(
                                connection, 'SELECT item, class FROM item_class_conditions'):
                            stored.setdefault(item, set()).add(char_class)
                finally:
                    connection.close()
                self.assertTrue(expected)
                self.assertEqual(expected, stored)

    def test_the_unusable_pieces_are_the_ones_the_criteria_forbid(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                expected = {item for item, tree in _trees(version).items()
                            if criteria.is_unusable(tree)}
                connection = _connect(version)
                try:
                    stored = {item for (item,) in _rows(
                        connection, 'SELECT item FROM unusable_items')}
                finally:
                    connection.close()
                self.assertTrue(expected)
                self.assertEqual(expected, stored)

    def test_the_highest_levels_are_the_ones_the_criteria_set(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                expected = {}
                for item, tree in _trees(version).items():
                    highest = criteria.level_bounds(tree)[1]
                    if highest is not None:
                        expected[item] = highest
                connection = _connect(version)
                try:
                    stored = dict(_rows(connection,
                                        'SELECT item, value FROM max_level_to_equip'))
                finally:
                    connection.close()
                self.assertTrue(expected)
                self.assertEqual(expected, stored)

    def test_the_stat_gates_are_the_ones_the_criteria_set(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                trees = _trees(version)
                connection = _connect(version)
                try:
                    stat_ids = {name: stat_id for stat_id, name in _rows(
                        connection, 'SELECT id, name FROM stats')}
                    stored_min = set(_rows(connection,
                                           'SELECT item, stat, value FROM min_stat_to_equip'))
                    stored_max = set(_rows(connection,
                                           'SELECT item, stat, value FROM max_stat_to_equip'))
                    stored_or = {}
                    for item, branch, stat, is_max, value in _rows(
                            connection, 'SELECT item, branch, stat, is_max, value'
                                        ' FROM item_or_conditions'):
                        stored_or.setdefault(item, {}).setdefault(branch, set()).add(
                            (stat, bool(is_max), value))
                finally:
                    connection.close()

                def gate(text):
                    name, operator, value = text.strip().rsplit(' ', 2)
                    return stat_ids[name], operator, int(value)

                expected_min, expected_max, expected_or = set(), set(), {}
                for item, tree in trees.items():
                    for condition in criteria.stat_conditions(tree):
                        if '|' in condition:
                            branches = set()
                            for branch in condition.split('|'):
                                gates = set()
                                for text in branch.split('&'):
                                    stat, operator, value = gate(text)
                                    gates.add((stat, operator == '<',
                                               value - 1 if operator == '<' else value + 1))
                                branches.add(frozenset(gates))
                            expected_or[item] = branches
                            continue
                        stat, operator, value = gate(condition)
                        if operator in '>=':
                            expected_min.add((item, stat, value + 1 if operator == '>' else value))
                        if operator in '<=':
                            expected_max.add((item, stat, value - 1 if operator == '<' else value))
                self.assertGreaterEqual(len(expected_min), FLOOR)
                self.assertEqual(expected_min, stored_min)
                self.assertEqual(expected_max, stored_max)
                self.assertEqual(expected_or, {
                    item: {frozenset(gates) for gates in branches.values()}
                    for item, branches in stored_or.items()})

    def test_the_set_bonus_caps_are_the_ones_the_criteria_set(self):
        criteria = _criteria()
        cap_ids = {'Set bonus < 2': 3, 'Set bonus < 3': 1, 'Sets equipped < 2': 4}
        for version in BASES:
            with self.subTest(version=version):
                expected = set()
                for item, tree in _trees(version).items():
                    for cap in (criteria.set_bonus_caps(tree)
                                + criteria.sets_equipped_caps(tree)):
                        expected.add((item, cap_ids[cap]))
                connection = _connect(version)
                try:
                    stored = set(_rows(connection,
                                       'SELECT item, condition_id FROM item_weird_conditions'
                                       ' WHERE condition_id IN (1, 3, 4)'))
                finally:
                    connection.close()
                self.assertEqual(expected, stored)
                if version != 'retro':
                    self.assertTrue(expected)

    def test_the_pieces_not_worn_together_are_the_ones_the_criteria_name(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                connection = _connect(version)
                try:
                    by_ankama = {}
                    for item, ankama_id in _rows(
                            connection, "SELECT id, ankama_id FROM items"
                                        " WHERE ankama_type != 'mounts'"):
                        by_ankama.setdefault(ankama_id, set()).add(item)
                    stored = set(_rows(connection,
                                       'SELECT item, other FROM items_not_worn_together'))
                finally:
                    connection.close()
                expected = set()
                for item, tree in _trees(version).items():
                    if criteria.KINDS[version].get(('PO', 'X')) != criteria.NOT_WORN_WITH:
                        continue
                    for other in criteria.not_worn_with(tree):
                        expected.update((item, other_id)
                                        for other_id in by_ankama.get(other, ()))
                self.assertEqual(expected, stored)
                if version == 'dofus2':
                    self.assertTrue(expected)

    def test_the_spell_ranks_are_stored_for_every_piece_that_asks_one(self):
        trees = _trees('touch')
        asking = {item for item, tree in trees.items()
                  if any(code == 'Pt' for code, _op, _value
                         in _criteria().atoms(tree))}
        connection = _connect('touch')
        try:
            stored = {item for (item,) in _rows(
                connection, 'SELECT DISTINCT item FROM item_spell_conditions')}
        finally:
            connection.close()
        self.assertTrue(asking)
        self.assertEqual(asking, stored)


class RealPiecesAreReadAsTheGameWritesThemTests(SimpleTestCase):

    def _classes(self, version, ankama_id):
        connection = _connect(version)
        try:
            return sorted(char_class for (char_class,) in _rows(
                connection, 'SELECT class FROM item_class_conditions WHERE item IN'
                            ' (SELECT id FROM items WHERE ankama_id = %d)' % ankama_id))
        finally:
            connection.close()

    def test_the_enutrofion_is_an_enutrof_ring_on_dofus2_touch_and_retro_only(self):
        for version, classes in (('dofus3', []), ('beta', []), ('dofus2', ['Enutrof']),
                                 ('touch', ['Enutrof']), ('retro', ['Enutrof'])):
            with self.subTest(version=version):
                self.assertEqual(classes, self._classes(version, 1499))

    def test_the_yingnitiate_sword_is_an_ecaflip_sword_in_every_version_that_has_it(self):
        for version in ('dofus3', 'beta', 'dofus2', 'retro'):
            with self.subTest(version=version):
                self.assertEqual(['Ecaflip'], self._classes(version, 6839))

    def test_a_retro_hat_barred_to_the_sadida_is_offered_to_the_eleven_others(self):
        classes = self._classes('retro', 700)
        self.assertEqual(11, len(classes))
        self.assertNotIn('Sadida', classes)

    def test_a_retro_hammer_for_two_classes_names_both(self):
        self.assertEqual(['Osamodas', 'Xelor'], self._classes('retro', 7156))

    def test_a_criteria_string_reads_into_its_parts(self):
        criteria = _criteria()
        tree = criteria.parse('CI>150&CV>150&(PG=2|PG=5)')
        self.assertEqual(['Intelligence > 150', 'Vitality > 150'],
                         criteria.stat_conditions(tree))
        self.assertEqual(['Osamodas', 'Xelor'], criteria.allowed_classes(
            tree, {2: 'Osamodas', 5: 'Xelor', 8: 'Iop'}))
        self.assertTrue(criteria.is_unusable(criteria.parse('PN~Silaisie&BI=1')))
        self.assertFalse(criteria.is_unusable(criteria.parse('BI=1|PX=A')))
        self.assertEqual((None, 5), criteria.level_bounds(criteria.parse('PL<6')))
        self.assertEqual(['Strength > 350', 'Intelligence > 350 | Chance > 350'],
                         criteria.stat_conditions(criteria.parse(
                             'CS>350&(CI>350|CC>350)')))
        self.assertEqual([], criteria.stat_conditions(criteria.parse('CS>100|PX=A')))
        self.assertEqual([27548, 27549], criteria.not_worn_with(
            criteria.parse('POX27548&POX27549')))
