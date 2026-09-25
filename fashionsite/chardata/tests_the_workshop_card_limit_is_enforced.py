# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A soft cap of 500 cards per version, enforced on every add path."""

import pickle
import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char, WorkshopItem
from chardata.workshop_view import MAX_CARDS_PER_VERSION
from fashionistapulp.dofus_constants import TYPE_NAME_TO_SLOT
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure


def _many_item_ids(game_version, count, exclude_ids=frozenset()):
    structure = get_structure(game_version)
    ids = []
    for item in structure.get_concatenated_items_lists():
        if getattr(item, 'removed', False) or item.id in exclude_ids:
            continue
        ids.append(item.id)
        if len(ids) >= count:
            break
    return ids


def _fill_cards(user, game_version, count, exclude_ids=frozenset()):
    WorkshopItem.objects.bulk_create([
        WorkshopItem(user=user, item_id=item_id, game_version=game_version, quantity=1)
        for item_id in _many_item_ids(game_version, count, exclude_ids)
    ])


class TheAddToWorkshopCapTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'capped-1', 'capped-1@test.local', 'pw-4242xy')
        self.client.force_login(self.user)
        _fill_cards(self.user, 'dofus3', MAX_CARDS_PER_VERSION)

    def test_a_brand_new_card_is_refused_at_the_cap(self):
        existing_ids = set(WorkshopItem.objects.filter(
            user=self.user, game_version='dofus3').values_list('item_id', flat=True))
        structure = get_structure('dofus3')
        new_item = next(item for item in structure.get_concatenated_items_lists()
                        if item.id not in existing_ids)

        resp = self.client.post('/workshop/add/', {'item_id': new_item.id})
        self.assertEqual(400, resp.status_code)
        self.assertFalse(WorkshopItem.objects.filter(
            user=self.user, item_id=new_item.id, game_version='dofus3').exists())
        self.assertEqual(
            MAX_CARDS_PER_VERSION,
            WorkshopItem.objects.filter(user=self.user, game_version='dofus3').count())

    def test_an_existing_card_can_still_be_incremented_at_the_cap(self):
        wi = WorkshopItem.objects.filter(user=self.user, game_version='dofus3').first()
        resp = self.client.post('/workshop/add/', {'item_id': wi.item_id})
        self.assertEqual(200, resp.status_code)
        wi.refresh_from_db()
        self.assertEqual(2, wi.quantity)

    def test_a_different_version_has_its_own_headroom(self):
        structure = get_structure('touch')
        new_item = next(iter(structure.get_concatenated_items_lists()))
        resp = self.client.post('/touch/workshop/add/', {'item_id': new_item.id})
        self.assertEqual(200, resp.status_code)


class TheBulkAddPathsRespectTheCapTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'capped-2', 'capped-2@test.local', 'pw-4242xy')
        self.client.force_login(self.user)

    def _headroom(self, remaining):
        _fill_cards(self.user, 'dofus3', MAX_CARDS_PER_VERSION - remaining)

    def test_addsolution_stops_at_the_cap_and_says_so(self):
        self._headroom(2)
        structure = get_structure('dofus3')
        existing_ids = set(WorkshopItem.objects.filter(
            user=self.user, game_version='dofus3').values_list('item_id', flat=True))

        seen_slots = set()
        picked = []
        for item in structure.get_concatenated_items_lists():
            if item.id in existing_ids:
                continue
            type_name = structure.get_type_name_by_id(item.type)
            slot = TYPE_NAME_TO_SLOT.get(type_name)
            if slot is None or slot in seen_slots:
                continue
            seen_slots.add(slot)
            picked.append(item.id)
            if len(picked) >= 3:
                break
        self.assertEqual(3, len(picked))

        input_ = {'options': {'ap_exo': False, 'mp_exo': False},
                  'origin': 'generated', 'char_level': 200,
                  'base_stats_by_attr': {}, 'locked_equips': {}}
        minimal = ModelResultMinimal.from_item_id_list(picked, input_, {})
        char = Char.objects.create(
            name='Cap test', char_name='cap-test', char_class='Iop',
            char_build='Damage', level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=b'', options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=pickle.dumps(minimal), owner=self.user,
            link_shared=False, game_version='dofus3')

        resp = self.client.post(
            '/workshop/addsolution/%d/' % char.id, {'mode': 'missing'})
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual(2, body['added'])
        self.assertTrue(body.get('limited'))
        self.assertIn(str(MAX_CARDS_PER_VERSION), body['message'])
        self.assertEqual(
            MAX_CARDS_PER_VERSION,
            WorkshopItem.objects.filter(user=self.user, game_version='dofus3').count())

    def test_addset_stops_at_the_cap_and_says_so(self):
        structure = get_structure('dofus3')
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            recipe_ids = {row[0] for row in
                          conn.execute('SELECT DISTINCT item FROM item_recipes')}
        finally:
            conn.close()

        found = None
        for set_id, item_set in structure.sets_dict.items():
            ids = []
            seen = set()
            for raw_id in getattr(item_set, 'items', None) or []:
                item = structure.get_item_by_id(raw_id)
                if item is None or item.ankama_id in seen:
                    continue
                seen.add(item.ankama_id)
                ids.append(item.id)
            craftable = [i for i in ids if i in recipe_ids]
            if len(craftable) >= 2:
                found = (set_id, craftable)
                break
        self.assertIsNotNone(found, 'no set with 2+ craftable items to test against')
        set_id, craftable = found

        _fill_cards(self.user, 'dofus3', MAX_CARDS_PER_VERSION - 1,
                   exclude_ids=set(craftable))

        resp = self.client.post('/workshop/addset/%d/' % set_id)
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual(1, body['added'])
        self.assertTrue(body.get('limited'))
        self.assertEqual(
            MAX_CARDS_PER_VERSION,
            WorkshopItem.objects.filter(user=self.user, game_version='dofus3').count())
