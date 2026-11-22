# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece the build locks is never forbidden by a resource ban, and the solver still wears it."""
import pickle
import unittest
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import resource_ban
from chardata.coaching_view import create_build
from chardata.fashion_action import _model_input
from chardata.min_stats import set_min_stats
from chardata.options import get_options, set_options, set_setup_choices
from chardata.stats_weights import set_stats_weights
from fashionistapulp.model import Model
from fashionistapulp.structure import get_structure, set_current_game_version

GELANO_RESOURCE = '757:resources'
RETRO_PET_ROWS = (10000065, 10000066)
WEIGHTS = {'ap': 1000, 'mp': 800, 'vit': 1}


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


class _ABuild(TestCase):

    version = 'dofus3'
    char_class = 'Feca'
    level = 60

    def setUp(self):
        set_current_game_version(self.version)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.structure = get_structure(self.version)
        owner = User.objects.create_user('lockban', 'lb@test.local', 'pw-lock-ban-1')
        self.request = RequestFactory().get('/')
        self.request.user = owner
        self.request.game_version = self.version
        self.char = create_build(self.request, self.char_class, self.level, {'cha'},
                                 self.version)
        set_min_stats(self.char, {})
        set_stats_weights(self.char, dict(WEIGHTS))

    def lock(self, slot, item_id):
        self.char.inclusions = pickle.dumps({slot: item_id})
        self.char.save()

    def ban(self, keys):
        set_setup_choices(self.char, {resource_ban.OPTION_KEY: list(keys)})

    def model_input(self):
        return _model_input(self.request, self.char, dict(WEIGHTS))

    def worn(self, model_input):
        model = Model()
        model.setup(model_input)
        model.run(1)
        return set(model.get_result_minimal().item_per_slot.values())


@unittest.skipUnless(_solver_available(), 'no pulp solver available')
class ALockedGelanoSurvivesTheBanOfItsResourceTests(_ABuild):

    def setUp(self):
        super().setUp()
        self.exo_gelano = self.structure.get_item_by_name('Gelano (#1)')
        self.plain_gelano = self.structure.get_item_by_name('Gelano (#2)')
        options = get_options(self.char)
        options['ap_exo'] = False
        options['mp_exo'] = 'gelano'
        set_options(self.char, options)

    def test_the_ban_forbids_the_gelano_rows_when_nothing_is_locked(self):
        self.ban([GELANO_RESOURCE])
        forbidden = self.model_input().forbidden_equips
        self.assertIn(self.plain_gelano.id, forbidden)

    def test_neither_gelano_row_is_forbidden_once_the_exo_row_is_locked(self):
        self.ban([GELANO_RESOURCE])
        self.lock('ring1', self.exo_gelano.id)
        forbidden = self.model_input().forbidden_equips
        self.assertNotIn(self.exo_gelano.id, forbidden)
        self.assertNotIn(self.plain_gelano.id, forbidden)

    def test_a_lock_stored_as_text_is_spared_as_well(self):
        self.ban([GELANO_RESOURCE])
        self.lock('ring1', str(self.plain_gelano.id))
        forbidden = self.model_input().forbidden_equips
        self.assertNotIn(self.plain_gelano.id, forbidden)
        self.assertNotIn(self.exo_gelano.id, forbidden)

    def test_the_solver_wears_the_locked_gelano_under_the_ban(self):
        self.ban([GELANO_RESOURCE])
        self.lock('ring1', self.exo_gelano.id)
        self.assertIn(self.exo_gelano.id, self.worn(self.model_input()))

    def test_the_solver_wears_the_locked_plain_gelano_row_as_well(self):
        self.ban([GELANO_RESOURCE])
        self.lock('ring1', self.plain_gelano.id)
        model_input = self.model_input()
        self.assertNotIn(self.plain_gelano.id, model_input.forbidden_equips)
        self.assertNotIn(self.exo_gelano.id, model_input.forbidden_equips)
        self.assertTrue({self.exo_gelano.id, self.plain_gelano.id} & self.worn(model_input))


@unittest.skipUnless(_solver_available(), 'no pulp solver available')
class ALockedRetroPetSurvivesTheBanOfAnotherRowOfItTests(_ABuild):
    """No Retro pet row has a recipe, so the map is given one that reaches the sibling row."""

    version = 'retro'
    char_class = 'Ecaflip'
    level = 100

    def _the_sibling_row_is_banned(self):
        real = resource_ban._items_by_resource('retro')
        key = sorted(real)[0]
        patched = dict(real)
        patched[key] = frozenset(real[key] | {RETRO_PET_ROWS[1]})
        return key, mock.patch.dict(resource_ban._resource_map_cache, {'retro': patched})

    def test_the_rows_are_one_pet(self):
        self.assertEqual(set(RETRO_PET_ROWS),
                         set(self.structure.get_rows_of_the_same_item(RETRO_PET_ROWS[0])))

    def test_the_ban_forbids_the_sibling_row_when_nothing_is_locked(self):
        key, patch = self._the_sibling_row_is_banned()
        with patch:
            self.ban([key])
            self.assertIn(RETRO_PET_ROWS[1], self.model_input().forbidden_equips)

    def test_neither_pet_row_is_forbidden_once_one_is_locked(self):
        key, patch = self._the_sibling_row_is_banned()
        with patch:
            self.ban([key])
            self.lock('pet', RETRO_PET_ROWS[0])
            forbidden = self.model_input().forbidden_equips
        self.assertFalse(set(RETRO_PET_ROWS) & forbidden)

    def test_the_solver_wears_the_locked_pet_under_the_ban(self):
        key, patch = self._the_sibling_row_is_banned()
        with patch:
            self.ban([key])
            self.lock('pet', RETRO_PET_ROWS[0])
            model_input = self.model_input()
        self.assertIn(RETRO_PET_ROWS[0], self.worn(model_input))
