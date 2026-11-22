# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A card posts the id of the piece it shows, and a lock on an id the version lacks is not kept or solved."""
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.lock_forbid import get_all_exclusions_ids, get_inclusions_dict
from chardata.models import Char
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version

_UNKNOWN_ID = 999999999

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'range_exo': False, 'mp_exo': False, 'dofus': True,
            'trophies': True, 'dragoturkey': True, 'seemyool': True,
            'rhineetle': True, 'prysmaradite': False, 'dofuses': {},
            'dofusnotforchar': set()}


class _ABuild(TestCase):

    VERSION = 'touch'
    LEVEL = 60
    PREFIX = '/touch'

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(self.VERSION)
        self.structure = get_structure(self.VERSION)
        self.owner = User.objects.create_user('cardid', 'ci@test.local', 'pw-card-id-1')
        self.char = Char.objects.create(
            name='Cards', char_name='cards', char_class='Iop', char_build='build',
            level=self.LEVEL, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'', owner=self.owner,
            link_shared=False, game_version=self.VERSION)
        self.client.force_login(self.owner)

    def _post(self, route, data, status=200):
        response = self.client.post('%s/%s/%d/' % (self.PREFIX, route, self.char.pk), data)
        self.assertEqual(status, response.status_code, response.content)
        self.char.refresh_from_db()


class TwoTouchPiecesSharingANameTests(_ABuild):

    def test_locking_the_card_of_the_level_60_cape_locks_that_cape(self):
        self._post('setitemlocked', {'slot': 'hat', 'equip': 'Caracape',
                                     'item_id': 2532, 'locked': 'true'})

        self.assertEqual(2532, get_inclusions_dict(self.char)['hat'])

    def test_forbidding_the_card_of_the_level_60_cape_forbids_that_cape(self):
        self._post('setitemforbidden', {'slot': 'hat', 'equip': 'Caracape',
                                        'item_id': 2532, 'forbidden': 'true'})

        excluded = get_all_exclusions_ids(self.char)
        self.assertIn(2532, excluded)
        self.assertNotIn(19624, excluded)

    def test_an_id_that_is_not_the_cards_piece_falls_back_to_the_name(self):
        by_name = self.structure.get_item_by_name('Caracape').id
        for posted in (_UNKNOWN_ID, 'x', '', self.structure.get_item_by_name('Caracap').id):
            with self.subTest(posted=posted):
                self._post('setitemforbidden', {'slot': 'hat', 'equip': 'Caracape',
                                                'item_id': posted, 'forbidden': 'false'})
                self._post('setitemforbidden', {'slot': 'hat', 'equip': 'Caracape',
                                                'item_id': posted, 'forbidden': 'true'})
                self.assertIn(by_name, get_all_exclusions_ids(self.char))
                self.assertNotIn(2532, get_all_exclusions_ids(self.char))
                self._post('setitemforbidden', {'slot': 'hat', 'equip': 'Caracape',
                                                'forbidden': 'false'})

    def test_a_card_posted_without_an_id_still_resolves_by_name(self):
        self._post('setitemforbidden', {'slot': 'hat', 'equip': 'Caracape',
                                        'forbidden': 'true'})

        self.assertIn(self.structure.get_item_by_name('Caracape').id,
                      get_all_exclusions_ids(self.char))


class TwoRetroRingsSharingANameTests(_ABuild):

    VERSION = 'retro'
    LEVEL = 200
    PREFIX = '/retro'

    def test_locking_the_card_of_the_second_ring_locks_that_ring(self):
        self._post('setitemlocked', {'slot': 'ring1', 'equip': 'Small Chance Ring',
                                     'item_id': 109, 'locked': 'true'})

        self.assertEqual(109, get_inclusions_dict(self.char)['ring1'])


class TheCardOfAnOrPieceTests(_ABuild):

    VERSION = 'dofus3'
    LEVEL = 60
    PREFIX = ''

    def test_the_id_of_a_row_of_an_or_name_is_kept_for_that_name(self):
        exo = self.structure.get_item_by_name('Gelano (#1)')

        self._post('setitemlocked', {'slot': 'ring1', 'equip': exo.or_name,
                                     'item_id': exo.id, 'locked': 'true'})

        self.assertEqual(exo.id, get_inclusions_dict(self.char)['ring1'])


class AnIdTheVersionLacksIsNotLockedTests(_ABuild):

    VERSION = 'dofus3'
    PREFIX = ''

    def test_the_same_unknown_id_in_both_rings_is_not_stored(self):
        self._post('inclusionspost', {'ring1': _UNKNOWN_ID, 'ring2': _UNKNOWN_ID})

        stored = get_inclusions_dict(self.char)
        self.assertEqual('', stored.get('ring1', ''))
        self.assertEqual('', stored.get('ring2', ''))


class TheModelSkipsALockOnAnUnknownIdTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_same_unknown_id_locked_twice_does_not_stop_the_setup(self):
        set_current_game_version('dofus3')
        model = Model()
        locked = {'ring1': _UNKNOWN_ID, 'ring2': _UNKNOWN_ID}

        model.setup(ModelInput(60, dict(_BASE), {}, locked, set(),
                               {'ap': 1000, 'mp': 800, 'vit': 1}, dict(_OPTIONS),
                               'Feca', 0))
