# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An infinite roll posted to the inventory is dropped like any unreadable value, and the rolls beside it are kept."""
import json

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.inventory_view import parse_custom_stats
from chardata.models import InventoryFolder, InventoryItem
from fashionistapulp.structure import get_structure

INFINITE = ('1e999', '-1e999')


class AnInfiniteRollPostedToTheInventoryIsDroppedTests(TestCase):

    def setUp(self):
        self.structure = get_structure('dofus3')
        self.item = next(item for item in self.structure.get_items_list() if item.stats)
        owner = User.objects.create_user('roller', 'roller@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        folder = InventoryFolder.objects.create(user=owner, name='mine', game_version='dofus3')
        self.row = InventoryItem.objects.create(folder=folder, item_id=self.item.id,
                                                custom_stats='{"cha": 100}')

    def test_the_parser_drops_the_infinite_roll_and_keeps_its_neighbour(self):
        for posted in INFINITE:
            with self.subTest(posted=posted):
                raw = '{"vit": %s, "cha": 50}' % posted
                self.assertEqual({'cha': 50}, parse_custom_stats(raw, self.structure))

    def test_the_update_route_stores_the_rolls_without_the_infinite_one(self):
        for posted in INFINITE:
            with self.subTest(posted=posted):
                response = self.client.post('/inventory/update/', {
                    'id': self.row.id, 'stats': '{"vit": %s, "cha": 50}' % posted})
                self.assertEqual(200, response.status_code)
                self.row.refresh_from_db()
                self.assertEqual({'cha': 50}, json.loads(self.row.custom_stats))
