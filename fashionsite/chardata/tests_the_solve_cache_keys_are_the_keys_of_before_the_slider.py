# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A solve's cache keys are the ones computed before the power slider existed, so every remembered solve is kept."""
from django.test import SimpleTestCase

from fashionistapulp.model import ModelInput
from fashionistapulp.structure import set_current_game_version

KEYS_BEFORE_THE_SLIDER = {
    'dofus3': 2754017923935570279,
    'retro': -3802799395468776746,
    'touch': -3055892054964991217,
    'beta': -4155786234228864496,
    'dofus2': -5998094555109807797,
}


def sample():
    return ModelInput(200, {'vit': 100, 'str': 250}, {'ap': 11, 'mp': 6, 'adv_mins': {'hp': 3000}},
                      {'Hat': 1234}, {55, 66}, {'str': 10, 'vit': 1, 'ap': 400},
                      {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True},
                      'Iop', 995, ['Shield'], {}, item_terms={77: 12.5}, crit_hinges=((30, 4.0),))


class TheSolveKeysAreTheKeysOfBeforeTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_an_input_without_a_gap_keeps_the_key_of_before_on_every_version(self):
        for version, key in KEYS_BEFORE_THE_SLIDER.items():
            with self.subTest(version=version):
                set_current_game_version(version)
                self.assertEqual(key, sample().cache_key())
