# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A resource ban forbids what an independent SQL walk of the recipe tables says, crafted equipment included."""
import pickle
import sqlite3
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import resource_ban
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
CRIMSON_PEBBLE = '12737:resources'
MINOR_LOCKER = 12622
LOCKER = 12623

_PAIRS = """
WITH RECURSIVE reach(root, item, depth) AS (
    SELECT id, id, 0 FROM items
    UNION
    SELECT reach.root, sub.id, reach.depth + 1
    FROM reach
    JOIN item_recipes r ON r.item = reach.item
         AND r.ingredient_subtype IN ('equipment', 'mounts')
    JOIN items sub ON sub.ankama_id = r.ingredient_ankama_id
         AND sub.ankama_type = r.ingredient_subtype
    WHERE reach.depth < 8
)
SELECT DISTINCT r.ingredient_ankama_id || ':' || r.ingredient_subtype, reach.root
FROM reach
JOIN item_recipes r ON r.item = reach.item
WHERE r.ingredient_subtype NOT IN ('equipment', 'mounts', 'pets', 'pet', 'mount')
"""


def _sql_answer(version):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        answer = {}
        for key, root in conn.execute(_PAIRS):
            answer.setdefault(key, set()).add(root)
        with_recipe = {row[0] for row in conn.execute(
            'SELECT DISTINCT item FROM item_recipes')}
        direct = {}
        for item, ankama_id, subtype in conn.execute(
                'SELECT item, ingredient_ankama_id, ingredient_subtype FROM item_recipes'):
            direct.setdefault('%d:%s' % (ankama_id, subtype), set()).add(item)
    finally:
        conn.close()
    return answer, with_recipe, direct


def _char(version, keys):
    return SimpleNamespace(id=1, game_version=version,
                           options=pickle.dumps({resource_ban.OPTION_KEY: list(keys)}))


class TheExpansionMatchesAnIndependentSqlWalkTests(SimpleTestCase):

    def test_the_map_of_each_version_is_the_sql_answer(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                answer, _with_recipe, _direct = _sql_answer(version)
                built = resource_ban._items_by_resource(version)
                self.assertEqual(set(answer), set(built))
                self.assertEqual(
                    [], [key for key in answer if set(built[key]) != answer[key]])

    def test_a_ban_forbids_the_sql_answer_for_the_keys_it_names(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                answer, _with_recipe, _direct = _sql_answer(version)
                structure = get_structure(version)
                keys = sorted(answer, key=lambda key: (-len(answer[key]), key))[:5]
                expected = set()
                for key in keys:
                    expected |= answer[key]
                expected = {item_id for item_id in expected
                            if getattr(structure.get_item_by_id(item_id), 'id', None) == item_id}
                self.assertTrue(expected)
                self.assertEqual(
                    expected,
                    resource_ban.items_the_ban_forbids(_char(version, keys), structure))

    def test_an_item_without_a_recipe_is_never_forbidden(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                answer, with_recipe, _direct = _sql_answer(version)
                structure = get_structure(version)
                keys = sorted(answer, key=lambda key: (-len(answer[key]), key))
                forbidden = set()
                for start in range(0, len(keys), resource_ban.MAX_BANNED_RESOURCES):
                    forbidden |= resource_ban.items_the_ban_forbids(
                        _char(version, keys[start:start + resource_ban.MAX_BANNED_RESOURCES]),
                        structure)
                self.assertTrue(forbidden)
                self.assertEqual(set(), forbidden - with_recipe)
                pets = {item.id for item in structure.get_available_items_list()
                        if item.type == structure.get_type_id_by_name('Pet')}
                self.assertTrue(pets)
                self.assertEqual(set(), pets & forbidden)

    def test_the_crimson_pebble_reaches_the_locker_through_the_minor_locker(self):
        _answer, _with_recipe, direct = _sql_answer('dofus3')
        self.assertIn(MINOR_LOCKER, direct[CRIMSON_PEBBLE])
        self.assertNotIn(LOCKER, direct[CRIMSON_PEBBLE])
        forbidden = resource_ban.items_the_ban_forbids(
            _char('dofus3', [CRIMSON_PEBBLE]), get_structure('dofus3'))
        self.assertIn(MINOR_LOCKER, forbidden)
        self.assertIn(LOCKER, forbidden)
