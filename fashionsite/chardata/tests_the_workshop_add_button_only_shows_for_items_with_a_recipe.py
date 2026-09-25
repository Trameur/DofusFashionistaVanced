# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The 'Add to workshop' control on an item page follows has_recipe and login."""

import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.official_site import get_item_link
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure


def _item_with_and_without_a_recipe(game_version='dofus3'):
    structure = get_structure(game_version)
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        recipe_ids = {row[0] for row in
                      conn.execute('SELECT DISTINCT item FROM item_recipes')}
    finally:
        conn.close()

    with_recipe = without_recipe = None
    for item in structure.get_concatenated_items_lists():
        if getattr(item, 'removed', False) or not item.ankama_id:
            continue
        if item.id in recipe_ids and with_recipe is None:
            with_recipe = item
        elif item.id not in recipe_ids and without_recipe is None:
            without_recipe = item
        if with_recipe is not None and without_recipe is not None:
            break
    return with_recipe, without_recipe


class WorkshopAddButtonOnItemPageTests(TestCase):

    def setUp(self):
        self.with_recipe, self.without_recipe = _item_with_and_without_a_recipe()
        self.assertIsNotNone(self.with_recipe, 'no recipe item to test against')
        self.assertIsNotNone(self.without_recipe, 'no recipe-less item to test against')
        self.user = User.objects.create_user(
            'workshopaddbtn-1', 'workshopaddbtn-1@test.local', 'pw-8827lk')

    def test_a_logged_in_reader_sees_the_add_control_for_a_recipe_item(self):
        self.client.force_login(self.user)
        url = get_item_link(self.with_recipe.ankama_type,
                            self.with_recipe.ankama_id, self.with_recipe.name,
                            'dofus3')
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertContains(resp, 'id="enc-workshop-add-form"')
        self.assertContains(resp, 'workshop/add/')

    def test_a_logged_in_reader_sees_no_add_control_without_a_recipe(self):
        self.client.force_login(self.user)
        url = get_item_link(self.without_recipe.ankama_type,
                            self.without_recipe.ankama_id,
                            self.without_recipe.name, 'dofus3')
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertNotContains(resp, 'id="enc-workshop-add-form"')

    def test_a_guest_sees_a_sign_in_link_instead_of_the_form(self):
        url = get_item_link(self.with_recipe.ankama_type,
                            self.with_recipe.ankama_id, self.with_recipe.name,
                            'dofus3')
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertNotContains(resp, 'id="enc-workshop-add-form"')
        self.assertContains(resp, 'login_page')

    def test_a_guest_gets_no_add_control_either_without_a_recipe(self):
        url = get_item_link(self.without_recipe.ankama_type,
                            self.without_recipe.ankama_id,
                            self.without_recipe.name, 'dofus3')
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertNotContains(resp, 'id="enc-workshop-add-form"')


class WorkshopAddSetButtonOnSetPageTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'workshopaddsetbtn-1', 'workshopaddsetbtn-1@test.local', 'pw-2261qw')

    def test_a_logged_in_reader_sees_the_add_set_button(self):
        from chardata.official_site import get_set_link
        structure = get_structure('dofus3')
        set_id, item_set = next(iter(structure.sets_dict.items()))
        set_name = item_set.localized_names.get('en') or item_set.name
        url = get_set_link(set_id, set_name, 'dofus3')
        self.client.force_login(self.user)
        resp = self.client.get(url, follow=True)
        self.assertEqual(200, resp.status_code)
        self.assertContains(resp, 'id="enc-workshop-add-set-btn"')

    def test_a_guest_sees_a_sign_in_link_instead(self):
        from chardata.official_site import get_set_link
        structure = get_structure('dofus3')
        set_id, item_set = next(iter(structure.sets_dict.items()))
        set_name = item_set.localized_names.get('en') or item_set.name
        url = get_set_link(set_id, set_name, 'dofus3')
        resp = self.client.get(url, follow=True)
        self.assertEqual(200, resp.status_code)
        self.assertNotContains(resp, 'id="enc-workshop-add-set-btn"')
        self.assertContains(resp, 'login_page')
