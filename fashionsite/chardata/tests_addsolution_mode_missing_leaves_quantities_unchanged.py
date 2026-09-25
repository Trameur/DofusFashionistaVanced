# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""POST workshop/addsolution/<char_id>/?mode=missing|increment."""

import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char, WorkshopItem
from fashionistapulp.dofus_constants import TYPE_NAME_TO_SLOT
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure


def _three_items_in_distinct_slots(game_version='dofus3'):
    structure = get_structure(game_version)
    seen_slots = set()
    picked = []
    for item in structure.get_concatenated_items_lists():
        type_name = structure.get_type_name_by_id(item.type)
        slot = TYPE_NAME_TO_SLOT.get(type_name)
        if slot is None or slot in seen_slots:
            continue
        seen_slots.add(slot)
        picked.append(item.id)
        if len(picked) >= 3:
            break
    return picked


def _minimal_solution_blob(item_ids):
    input_ = {'options': {'ap_exo': False, 'mp_exo': False},
              'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    minimal = ModelResultMinimal.from_item_id_list(item_ids, input_, {})
    return pickle.dumps(minimal)


class AddSolutionModeTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'solution-crafter', 'sc@test.local', 'pw-4242xy')
        self.client.force_login(self.user)
        self.item_ids = _three_items_in_distinct_slots()
        self.assertEqual(3, len(self.item_ids))
        self.char = Char.objects.create(
            name='Bulk add build', char_name='bulk-add-build',
            char_class='Iop', char_build='Damage', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_minimal_solution_blob(self.item_ids),
            owner=self.user, link_shared=False, game_version='dofus3')

    def test_default_mode_is_increment_like_before(self):
        resp = self.client.post('/workshop/addsolution/%d/' % self.char.id)
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual('increment', body['mode'])
        self.assertEqual(3, body['added'])

        resp = self.client.post('/workshop/addsolution/%d/' % self.char.id)
        self.assertEqual(3, resp.json()['added'])
        for item_id in self.item_ids:
            wi = WorkshopItem.objects.get(
                user=self.user, item_id=item_id, game_version='dofus3')
            self.assertEqual(2, wi.quantity)

    def test_mode_missing_only_adds_absent_items(self):
        resp = self.client.post(
            '/workshop/addsolution/%d/' % self.char.id, {'mode': 'missing'})
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual('missing', body['mode'])
        self.assertEqual(3, body['added'])
        for item_id in self.item_ids:
            wi = WorkshopItem.objects.get(
                user=self.user, item_id=item_id, game_version='dofus3')
            self.assertEqual(1, wi.quantity)

    def test_mode_missing_twice_changes_nothing(self):
        self.client.post(
            '/workshop/addsolution/%d/' % self.char.id, {'mode': 'missing'})
        before = {
            wi.item_id: wi.quantity for wi in WorkshopItem.objects.filter(
                user=self.user, game_version='dofus3')
        }

        resp = self.client.post(
            '/workshop/addsolution/%d/' % self.char.id, {'mode': 'missing'})
        self.assertEqual(200, resp.status_code)
        self.assertEqual(0, resp.json()['added'])

        after = {
            wi.item_id: wi.quantity for wi in WorkshopItem.objects.filter(
                user=self.user, game_version='dofus3')
        }
        self.assertEqual(before, after)

    def test_mode_missing_never_touches_an_item_added_another_way(self):
        WorkshopItem.objects.create(
            user=self.user, item_id=self.item_ids[0], game_version='dofus3',
            quantity=7)
        resp = self.client.post(
            '/workshop/addsolution/%d/' % self.char.id, {'mode': 'missing'})
        self.assertEqual(200, resp.status_code)
        self.assertEqual(2, resp.json()['added'])

        wi = WorkshopItem.objects.get(
            user=self.user, item_id=self.item_ids[0], game_version='dofus3')
        self.assertEqual(7, wi.quantity)

    def test_an_unrecognised_mode_falls_back_to_increment(self):
        resp = self.client.post(
            '/workshop/addsolution/%d/' % self.char.id, {'mode': 'bogus'})
        self.assertEqual(200, resp.status_code)
        self.assertEqual('increment', resp.json()['mode'])
