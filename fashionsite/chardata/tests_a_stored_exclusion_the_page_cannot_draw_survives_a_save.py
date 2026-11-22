# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A stored exclusion is drawn on the forbid page or kept by a save, never dropped because the page could not draw its row."""
import json
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.lock_forbid import get_all_exclusions_ids
from chardata.models import Char
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.game_versions import GAME_VERSIONS
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import (GELANO_IDS, get_structure,
                                       set_current_game_version)

_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'shields': True}
_AP_MP_GELANO = GELANO_IDS['Gelano (#1)']
_NO_SUCH_ITEM = 987654321


class TheForbidPageOnDofus3Tests(TestCase):

    VERSION = 'dofus3'
    LEVEL = 200

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(self.VERSION)
        self.structure = get_structure(self.VERSION)
        self.prefix = '/' + GAME_VERSIONS[self.VERSION].prefix if GAME_VERSIONS[self.VERSION].prefix else ''
        self.owner = User.objects.create_user('exclgelano', 'eg@test.local', 'pw-excl-gelano-1')
        self.char = Char.objects.create(
            name='Gelano', char_name='gelano', char_class='Iop', char_build='build',
            level=self.LEVEL, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'', owner=self.owner,
            link_shared=False, game_version=self.VERSION)
        self.client.force_login(self.owner)
        self.gelano_rows = [row.id for row in self.structure.get_available_or_items()[
            self.structure.get_item_by_id(_AP_MP_GELANO).or_name]]
        self.all_items = self.structure.get_all_unique_items_ids_with_type()

    def _store(self, item_ids):
        self.char.exclusions = pickle.dumps(item_ids)
        self.char.save()

    def _page_state(self):
        page = self.client.get('%s/exclusions/%d/' % (self.prefix, self.char.pk))
        self.assertEqual(200, page.status_code)
        return json.loads(page.context['exclusions'])

    def _drawn(self, state):
        return [entry['id'] for entry in state if entry['id'] in self.all_items]

    def _save(self, item_ids):
        saved = self.client.post('%s/exclusionspost/%d/' % (self.prefix, self.char.pk),
                                 {'exclusions': json.dumps([str(i) for i in item_ids])})
        self.assertEqual(200, saved.status_code, saved.content)
        self.char.refresh_from_db()
        return json.loads(saved.content)

    def _gelano_rows_the_solver_opens(self, item_ids, mp_exo):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100, 'Pods': 1000})
        model = Model()
        model.setup(ModelInput(self.LEVEL, base, {}, {}, set(item_ids), {'vit': 1},
                               dict(_OPTIONS, mp_exo=mp_exo), 'Iop', 995))
        constraints = model.restrictions.forbidden_items_constraints
        return {row for row in self.gelano_rows
                if row in constraints and -constraints[row].constant > 0}

    def _every_gelano_row_is_forbidden(self):
        stored = get_all_exclusions_ids(self.char)
        for mp_exo in (False, 'gelano'):
            with self.subTest(mp_exo=mp_exo):
                self.assertEqual(set(), self._gelano_rows_the_solver_opens(stored, mp_exo))

    def test_the_page_state_shows_the_gelano_on_a_row_the_page_draws(self):
        self._store([_AP_MP_GELANO])

        state = self._page_state()

        self.assertEqual(1, len(state))
        self.assertIn(state[0]['id'], self.all_items)
        self.assertIn('Gelano', state[0]['name'])

    def test_posting_back_the_drawn_ids_keeps_every_gelano_row_forbidden(self):
        self._store([_AP_MP_GELANO])
        self._every_gelano_row_is_forbidden()

        self._save(self._drawn(self._page_state()))

        self._every_gelano_row_is_forbidden()

    def test_the_save_answer_equals_the_page_state(self):
        self._store([_AP_MP_GELANO])

        answer = self._save(self._drawn(self._page_state()))

        self.assertTrue(answer)
        self.assertEqual(self._page_state(), answer)

    def test_a_gelano_stored_on_two_rows_is_drawn_once(self):
        self._store([_AP_MP_GELANO] + [row for row in self.gelano_rows if row != _AP_MP_GELANO])

        self.assertEqual(1, len(self._page_state()))

    def test_unforbidding_the_gelano_from_the_page_removes_it(self):
        self._store([_AP_MP_GELANO])

        answer = self._save([])

        self.assertEqual([], answer)
        for mp_exo in (False, 'gelano'):
            with self.subTest(mp_exo=mp_exo):
                self.assertEqual(1, len(self._gelano_rows_the_solver_opens(
                    get_all_exclusions_ids(self.char), mp_exo)))

    def test_a_stored_id_the_page_cannot_draw_survives_a_save(self):
        self.assertIsNone(self.structure.get_item_by_id(_NO_SUCH_ITEM))
        self._store([_NO_SUCH_ITEM, _AP_MP_GELANO])

        self._save(self._drawn(self._page_state()))

        self.assertIn(_NO_SUCH_ITEM, get_all_exclusions_ids(self.char))
        self._every_gelano_row_is_forbidden()

    def test_a_stored_id_the_page_cannot_draw_is_not_drawn_twice_after_a_save(self):
        self._store([_NO_SUCH_ITEM])

        self._save([])
        self._save([])

        self.assertEqual([_NO_SUCH_ITEM], get_all_exclusions_ids(self.char))


class TheForbidPageOnDofus2Tests(TheForbidPageOnDofus3Tests):
    VERSION = 'dofus2'


class TheForbidPageOnRetroTests(TheForbidPageOnDofus3Tests):
    VERSION = 'retro'


class TheForbidPageOnBetaTests(TheForbidPageOnDofus3Tests):
    VERSION = 'beta'


class TheForbidPageOnTouchTests(TheForbidPageOnDofus3Tests):
    VERSION = 'touch'
    LEVEL = 60
