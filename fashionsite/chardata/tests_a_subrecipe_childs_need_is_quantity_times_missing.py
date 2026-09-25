# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A sub-recipe child's need is its own quantity times what is still missing
of the intermediate, and owning the intermediate fully brings it to 0."""

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.models import WorkshopItem
from chardata.recipe_util import expand_subrecipes
from fashionistapulp.fashionista_config import get_items_db_path


def _a_chained_craftable_ingredient(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        has_own_recipe = {row[0] for row in conn.execute(
            "SELECT DISTINCT i.ankama_id FROM items i "
            "JOIN item_recipes r ON r.item = i.id WHERE i.ankama_type = 'equipment'")}
        used_as_ingredient = {row[0] for row in conn.execute(
            "SELECT DISTINCT ingredient_ankama_id FROM item_recipes "
            "WHERE ingredient_subtype = 'equipment'")}
        chained = sorted(has_own_recipe & used_as_ingredient)
        if not chained:
            return None
        intermediate = chained[0]
        parent_item, quantity = conn.execute(
            "SELECT item, quantity FROM item_recipes "
            "WHERE ingredient_ankama_id = ? AND ingredient_subtype = 'equipment' LIMIT 1",
            (intermediate,)).fetchone()
        own_rows = conn.execute(
            "SELECT ingredient_ankama_id, ingredient_subtype, quantity "
            "FROM item_recipes WHERE item = "
            "(SELECT id FROM items WHERE ankama_id = ? AND ankama_type = 'equipment') "
            "ORDER BY position", (intermediate,)).fetchall()
    finally:
        conn.close()
    return parent_item, quantity, intermediate, own_rows


class WorkshopJsSubrecipeFormulaTests(SimpleTestCase):
    """subrecipeChildNeed, run for real under node."""

    def _run(self, expression):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        js_path = os.path.join(os.path.dirname(__file__), 'static', 'chardata',
                               'workshop.js')
        with open(js_path, encoding='utf-8') as handle:
            source = handle.read()
        driver = r"""
var vm = require('vm');
global.window = {};
global.document = {getElementById: function () { return null; }};
vm.runInThisContext(source);
var w = window.FashionWorkshop;
console.log(JSON.stringify(EXPR));
"""
        driver = driver.replace('EXPR', expression)
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('var source = %s;\n%s' % (json.dumps(source), driver))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_an_unowned_intermediate_needs_the_full_quantity(self):
        self.assertEqual(24, self._run('w.subrecipeChildNeed(3, 8, 0)'))

    def test_a_partly_owned_intermediate_scales_down(self):
        self.assertEqual(9, self._run('w.subrecipeChildNeed(3, 8, 5)'))

    def test_a_fully_owned_intermediate_needs_nothing(self):
        self.assertEqual(0, self._run('w.subrecipeChildNeed(3, 8, 8)'))

    def test_an_overstocked_intermediate_never_goes_negative(self):
        self.assertEqual(0, self._run('w.subrecipeChildNeed(3, 8, 99)'))


class TheSubrecipeExpansionMatchesTheRecipeTableTests(TestCase):

    def test_a_dofus3_chains_children_match_the_intermediates_own_recipe(self):
        chain = _a_chained_craftable_ingredient('dofus3')
        self.assertIsNotNone(chain, 'no equipment-in-equipment chain to test against')
        _parent_item, _quantity, intermediate, own_rows = chain

        expansion = expand_subrecipes(
            [(intermediate, 'equipment')], 'dofus3', 'en')
        result = expansion['%d:equipment' % intermediate]

        self.assertTrue(result['found'])
        self.assertEqual(len(own_rows), len(result['children']))
        for (ankama_id, subtype, quantity), child in zip(own_rows, result['children']):
            self.assertEqual(ankama_id, child['ankama_id'])
            self.assertEqual(subtype, child['subtype'])
            self.assertEqual(quantity, child['quantity'])

    def test_a_stale_key_with_no_recipe_of_its_own_is_not_found(self):
        expansion = expand_subrecipes([(999999999, 'resources')], 'dofus3', 'en')
        self.assertEqual(
            {'found': False, 'children': []},
            expansion['999999999:resources'])


class TheEndpointAgreesWithTheChainAndAddsTheIntermediateTests(TestCase):

    def setUp(self):
        chain = _a_chained_craftable_ingredient('dofus3')
        self.assertIsNotNone(chain, 'no equipment-in-equipment chain to test against')
        self.parent_item, self.quantity, self.intermediate, self.own_rows = chain
        self.user = User.objects.create_user(
            'subrecipe-chain', 'subrecipe-chain@test.local', 'pw-8821nq')
        WorkshopItem.objects.create(
            user=self.user, item_id=self.parent_item, game_version='dofus3', quantity=1)
        self.client.force_login(self.user)

    def test_the_endpoint_returns_the_intermediates_own_recipe(self):
        key = '%d:equipment' % self.intermediate
        resp = self.client.get('/workshop/subrecipe/?keys=%s&depth=1' % key)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertTrue(data['success'])
        result = data['subrecipes'][key]
        self.assertTrue(result['found'])
        self.assertEqual(len(self.own_rows), len(result['children']))
        for (ankama_id, subtype, quantity), child in zip(self.own_rows, result['children']):
            self.assertEqual(ankama_id, child['ankama_id'])
            self.assertEqual(subtype, child['subtype'])
            self.assertEqual(quantity, child['quantity'])

    def test_adding_the_intermediate_as_its_own_card_succeeds(self):
        # The row's own craftable_item_id is what the "Add as its own card"
        # button posts to /workshop/add/: resolve it the same way build_row does.
        from chardata.recipe_util import workshop_breakdown
        breakdown = workshop_breakdown([(self.parent_item, 1)], 'en', 'dofus3')
        row = next(r for r in breakdown['items'][self.parent_item]
                  if r['ankama_id'] == self.intermediate)
        self.assertIsNotNone(row['craftable_item_id'])

        add_resp = self.client.post(
            '/workshop/add/',
            {'item_id': row['craftable_item_id'], 'quantity': 1})
        self.assertEqual(200, add_resp.status_code)
        self.assertTrue(add_resp.json()['success'])
        self.assertTrue(WorkshopItem.objects.filter(
            user=self.user, item_id=row['craftable_item_id'],
            game_version='dofus3').exists())
